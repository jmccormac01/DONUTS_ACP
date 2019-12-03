"""
ACP + DONUTS Autoguiding

Usage:
    $> python acp_ag.py INSTRUMENT

where INSTRUMENT can be:
    nites, io, europa, callisto, ganymede, saintex, artemis
"""
import time
import os
import sys
from contextlib import contextmanager
from shutil import copyfile
from datetime import (
    date,
    timedelta,
    datetime)
from math import (
    radians,
    sin,
    cos)
from collections import defaultdict
import argparse as ap
import glob as g
import numpy as np
import win32com.client
import pymysql
from astropy.io import fits
import astropy.units as u
from astropy.time import Time
from astropy.coordinates import (
    EarthLocation,
    AltAz,
    get_sun
    )
from PID import PID
from donuts import Donuts

# pylint: disable = invalid-name
# pylint: disable = redefined-outer-name
# pylint: disable = line-too-long
# pylint: disable = no-member
# pylint: disable = wildcard-import
# pylint: disable = unused-wildcard-import

# autoguider status flags
ag_new_day, ag_new_start, ag_new_field, ag_new_filter, ag_no_change = range(5)

# get command line arguments
def argParse():
    """
    Parse command line arguments

    Parameters
    ----------
    None

    Returns
    -------
    argparse argument object

    Raises
    ------
    None
    """
    p = ap.ArgumentParser()
    p.add_argument('instrument',
                   help='select an instrument',
                   choices=['io', 'callisto', 'europa',
                            'ganymede', 'saintex', 'nites',
                            'artemis', 'rcos20'])
    return p.parse_args()

def getSunAlt(observatory):
    """
    Get the Sun's elevation as an emergency check

    Parameters
    ----------
    observatory : astropy.coordinates.EarthLocation
        Location of the current observatory

    Returns
    -------
    alt : float
        Altitude of the Sun

    Raises
    ------
    None
    """
    now = Time(datetime.utcnow(), format='datetime', scale='utc')
    altazframe = AltAz(obstime=now, location=observatory)
    sunaltaz = get_sun(now).transform_to(altazframe)
    return sunaltaz.alt.value

def strtime(dt):
    """
    Return a string formatted datetime in the iso format

    Parameters
    ----------
    dt : datetime object
        datetime object to convert to iso formatted string

    Returns
    -------
    datetime : string
        iso formatted string

    Raises
    ------
    None
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S')

# apply guide corrections
def guide(x, y, images_to_stabilise, gem=False):
    """
    Generic autoguiding command with built-in PID control loop
    guide() will track recent autoguider corrections and ignore
    abnormally large offsets. It will also handle orientation
    and scale conversions as per the telescope specific config
    file.

    During the initial field stabilisation period the limits are
    relaxed slightly and large pull in errors are not appended
    to the steady state outlier rejection buffer

    Parameters
    ----------
    x : float
        Guide correction to make in X direction
    y : float
        Guide correction to make in Y direction
    images_to_stabilise : int
        Number of images before field is stabilised
        If -ve, field has stabilised
        If +ve allow for bigger shifts and do not append
        ag values to buffers
    gem : boolean
        Are we using a German Equatorial Mount?
        Default = False
        If so, the side of the pier matters for correction
        directions. Ping the mount for pierside before applying
        a correction. If this turns out to be slow, we can do so
        only when in the HA range for a pier flip

    Returns
    -------
    success : boolean
        was the correction applied? Proxy for telescope connected
    pidx : float
        X correction actually sent to the mount, post PID
    pidy : float
        Y correction actually sent to the mount, post PID
    sigma_x : float
        Stddev of X buffer
    sigma_y : float
        Stddev of Y buffer

    Raises
    ------
    None
    """


    connected = myScope.Connected
    if str(connected) == 'True':
        # get telescope declination to scale RA corrections
        dec = myScope.Declination
        dec_rads = radians(dec)
        cos_dec = cos(dec_rads)
        # pop the earliest buffer value if > 30 measurements
        while len(BUFF_X) > GUIDE_BUFFER_LENGTH:
            BUFF_X.pop(0)
        while len(BUFF_Y) > GUIDE_BUFFER_LENGTH:
            BUFF_Y.pop(0)
        assert len(BUFF_X) == len(BUFF_Y)
        if images_to_stabilise < 0:
            CURRENT_MAX_SHIFT = MAX_ERROR_PIXELS
            # kill anything that is > sigma_buffer sigma buffer stats
            if len(BUFF_X) < GUIDE_BUFFER_LENGTH and len(BUFF_Y) < GUIDE_BUFFER_LENGTH:
                logMessageToDb(args.instrument, 'Filling AG stats buffer...')
                sigma_x = 0.0
                sigma_y = 0.0
            else:
                sigma_x = np.std(BUFF_X)
                sigma_y = np.std(BUFF_Y)
                if abs(x) > SIGMA_BUFFER * sigma_x or abs(y) > SIGMA_BUFFER * sigma_y:
                    logMessageToDb(args.instrument,
                                   'Guide error > {} sigma * buffer errors, ignoring...'.format(SIGMA_BUFFER))
                    # store the original values in the buffer, even if correction
                    # was too big, this will allow small outliers to be caught
                    BUFF_X.append(x)
                    BUFF_Y.append(y)
                    return True, 0.0, 0.0, sigma_x, sigma_y
                else:
                    pass
        else:
            logMessageToDb(args.instrument, 'Ignoring AG buffer during stabilisation')
            CURRENT_MAX_SHIFT = MAX_ERROR_STABIL_PIXELS
            sigma_x = 0.0
            sigma_y = 0.0

        # update the PID controllers, run them in parallel
        pidx = PIDx.update(x) * -1
        pidy = PIDy.update(y) * -1

        # check if we are stabilising and allow for the max shift
        if images_to_stabilise > 0:
            if pidx >= CURRENT_MAX_SHIFT:
                pidx = CURRENT_MAX_SHIFT
            elif pidx <= -CURRENT_MAX_SHIFT:
                pidx = -CURRENT_MAX_SHIFT
            if pidy >= CURRENT_MAX_SHIFT:
                pidy = CURRENT_MAX_SHIFT
            elif pidy <= -CURRENT_MAX_SHIFT:
                pidy = -CURRENT_MAX_SHIFT
        logMessageToDb(args.instrument, "PID: {0:.2f}  {1:.2f}".format(float(pidx), float(pidy)))

        # make another check that the post PID values are not > Max allowed
        # using >= allows for the stabilising runs to get through
        # abs() on -ve duration otherwise throws back an error
        if pidy > 0 and pidy <= CURRENT_MAX_SHIFT:
            guide_time_y = pidy * PIX2TIME['+y']
            if RA_AXIS == 'y':
                guide_time_y = guide_time_y/cos_dec
            myScope.PulseGuide(DIRECTIONS['+y'], guide_time_y)
        if pidy < 0 and pidy >= -CURRENT_MAX_SHIFT:
            guide_time_y = abs(pidy * PIX2TIME['-y'])
            if RA_AXIS == 'y':
                guide_time_y = guide_time_y/cos_dec
            myScope.PulseGuide(DIRECTIONS['-y'], guide_time_y)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.01)
        if pidx > 0 and pidx <= CURRENT_MAX_SHIFT:
            guide_time_x = pidx * PIX2TIME['+x']
            if RA_AXIS == 'x':
                guide_time_x = guide_time_x/cos_dec
            myScope.PulseGuide(DIRECTIONS['+x'], guide_time_x)
        if pidx < 0 and pidx >= -CURRENT_MAX_SHIFT:
            guide_time_x = abs(pidx * PIX2TIME['-x'])
            if RA_AXIS == 'x':
                guide_time_x = guide_time_x/cos_dec
            myScope.PulseGuide(DIRECTIONS['-x'], guide_time_x)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.01)
        logMessageToDb(args.instrument, "Guide correction Applied")
        # store the original values in the buffer
        # only if we are not stabilising
        if images_to_stabilise < 0:
            BUFF_X.append(x)
            BUFF_Y.append(y)
        return True, pidx, pidy, sigma_x, sigma_y
    else:
        logMessageToDb(args.instrument, "Telescope NOT connected!")
        logMessageToDb(args.instrument, "Please connect Telescope via ACP!")
        logMessageToDb(args.instrument, "Ignoring corrections!")
        return False, 0.0, 0.0, 0.0, 0.0

# log guide corrections to file
def logShiftsToFile(logfile, loglist, header=False):
    """
    Log the guide corrections to disc. This log is
    typically located with the data files for each night

    Parameters
    ----------
    logfile : string
        Path to the logfile
    log_list : array like
        List of items to log, see order of items below:
        night : string
            Date of the night
        ref : string
            Name of the current reference image
        check : string
            Name of the current guide image
        stabilised : string
            Telescope stabilised yet? (y | n)
        shift_x : float
            Raw shift measured in X direction
        shift_y : float
            Raw shift measured in Y direction
        pre_pid_X : float
            X correction sent to the PID loop
        pre_pid_y : float
            Y correction sent to the PID loop
        post_pid_X : float
            X correction sent to the mount, post PID loop
        post_pid_y : float
            Y correction sent to the mount, post PID loop
        std_buff_x : float
            Sttdev of X AG value buffer
        std_buff_y : float
            Sttdev of Y AG value buffer
        culled_max_shift_x : string
            Culled X measurement if > max allowed shift (y | n)
        culled_max_shift_y : string
            Culled Y measurement if > max allowed shift (y | n)
    header : boolean
        Flag to set writing the log file header. This is done
        at the start of the night only

    Returns
    -------
    None

    Raises
    ------
    None
    """
    if header:
        line = "night  ref  check  stable  shift_x  shift_y  pre_pid_x  pre_pid_y  " \
               "post_pid_x  post_pid_y  std_buff_x  std_buff_y  culled_x  culled_y"
    else:
        line = "  ".join(loglist)
    with open(logfile, "a") as outfile:
        outfile.write("{}\n".format(line))

@contextmanager
def openDb(host, user, db, passwd):
    """
    Open a connection to ops database

    Parameters
    ----------
    host : string
        Database hostname
    user : string
        Database username
    db : string
        Database name

    Yields
    -------
    cur : pymysql.cursor
        Cursor to interact with pymysql database

    Raises
    ------
    None
    """
    with pymysql.connect(host=host, user=user,
                         db=db, password=passwd) as cur:
        yield cur

def logShiftsToDb(qry_args):
    """
    Log the autguiding information to the database

    Parameters
    ----------
    qry_args : array like
        Tuple of items to log in the database.
        See itemised list in logShiftsToFile docstring

    Returns
    -------
    None

    Raises
    ------
    None
    """
    qry = """
        INSERT INTO autoguider_log_new
        (night, reference, comparison, stabilised, shift_x, shift_y,
         pre_pid_x, pre_pid_y, post_pid_x, post_pid_y, std_buff_x,
         std_buff_y, culled_max_shift_x, culled_max_shift_y)
        VALUES
        (%s, %s, %s, %s, %s, %s, %s,
         %s, %s, %s, %s, %s, %s, %s)
        """
    with openDb(DB_HOST, DB_USER, DB_DATABASE, DB_PASS) as cur:
        cur.execute(qry, qry_args)

def logMessageToDb(telescope, message):
    """
    Log outout messages to the database

    Parameters
    ----------
    telescope : str
        Name of the instrument being autoguided
    message : str
        Output message to log

    Returns
    -------
    None

    Raises
    ------
    None
    """
    qry = """
        INSERT INTO autoguider_info_log
        (telescope, message)
        VALUES
        (%s, %s)
        """
    qry_args = (telescope, message)
    with openDb(DB_HOST, DB_USER, DB_DATABASE, DB_PASS) as cur:
        cur.execute(qry, qry_args)


# get evening or morning
def getAmOrPm():
    """
    Determine if it is morning or afteroon

    This function uses now instead of utcnow because
    it is the local time which determines if we are
    starting or ending the curent night.

    A local time > midday is the evening
    A local time < midday is the morning of the day after
    This is not true for UTC in all places

    Parameters
    ----------
    None

    Returns
    -------
    token : int
        0 if evening
        1 if morning

    Raises
    ------
    None
    """
    now = datetime.now()
    if now.hour >= 12:
        token = 0
    else:
        token = 1
    return token

# get tonights directory
def getDataDir(data_subdir):
    """
    Get tonight's data directory

    Parameters
    ----------
    None

    Returns
    -------
    data_loc : string
        Path to tonight's data directory

    Raises
    ------
    None
    """
    token = getAmOrPm()
    d = date.today()-timedelta(days=token)
    night = "{:d}{:02d}{:02d}".format(d.year, d.month, d.day)
    night_str = "{:d}-{:02d}-{:02d}".format(d.year, d.month, d.day)
    data_loc = "{}\\{}".format(BASE_DIR, night)
    # adds capability for data to live in folders
    # inside the nightly folder, as for saintex
    if data_subdir != "":
        data_loc = data_loc + "\\{}".format(data_subdir)
    if os.path.exists(data_loc):
        return data_loc, night_str
    else:
        return None, night_str

# wait for the newest image
def waitForImage(data_subdir, current_field, n_images, current_filter,
                 current_data_dir, observatory):
    """
    Wait for new images. Several things can happen:
        1. A new image comes in of new field and filter (new start)
        2. A new image comes in but of a new field (new field)
        3. A new image comes in but with a different filter (new filter)
        4. No change occurs and same field and filter apply (no_change)
        5. A new day's data directory is detected, or sun_alt > 0 (new_day)

    Parameters
    ----------
    data_subdir : string
        subdirectory of data folder for raw data
    current_field : string
        name of the current target
    n_images : int
        number of images previously acquired
    current_filter : string
        name of the current filter
    current_data_dir : string
        path to current data directory
    observatory : astropy.EarthLocation
        location of the observing site

    Returns
    -------
    ag_status : int
        flag showing the current return status, see table above
    newest_image : string
        filenname of the newest image
    newest_field : string
        name of the newest field
    newest_filter : string
        name of the newest filter

    Raises
    ------
    None
    """
    while 1:
        # check for new data directory, i.e. tomorrow
        new_data_dir, _ = getDataDir(data_subdir)
        if new_data_dir != current_data_dir:
            return ag_new_day, None, None, None
        # secondary check, check the sun altitude, quit if > 0
        sunalt = getSunAlt(observatory)
        if sunalt > SUNALT_LIMIT:
            return ag_new_day, None, None, None
        # check for new images
        t = g.glob('*{}'.format(IMAGE_EXTENSION))
        if len(t) > n_images:
            # get newest image
            try:
                newest_image = max(t, key=os.path.getctime)
            except ValueError:
                # if the intial list is empty, just cycle back and try again
                continue
            # open the newest image and check the field and filter
            try:
                with fits.open(newest_image) as fitsfile:
                    newest_filter = fitsfile[0].header[FILTER_KEYWORD]
                    newest_field = fitsfile[0].header[FIELD_KEYWORD]
            except FileNotFoundError:
                # if the file cannot be accessed (not completely written to disc yet)
                # cycle back and try again
                logMessageToDb(args.instrument,
                               'Problem accessing fits file {}, skipping...'.format(newest_image))
                continue
            except OSError:
                # this catches the missing header END card
                logMessageToDb(args.instrument,
                               'Problem accessing fits file {}, skipping...'.format(newest_image))
                continue
            # new start? if so, return the newest image info
            if current_field == "" and current_filter == "":
                return ag_new_start, newest_image, newest_field, newest_filter
            # check that the field is the same
            if current_field != "" and current_field != newest_field:
                return ag_new_field, newest_image, newest_field, newest_filter
            # check that the field is the same but filter has changed
            if current_field != "" and current_field == newest_field and current_filter != newest_filter:
                return ag_new_filter, newest_image, newest_field, newest_filter
            # check the field and filters are the same
            if current_field != "" and current_field == newest_field and current_filter == newest_filter:
                return ag_no_change, newest_image, newest_field, newest_filter
        # if no new images, wait for a bit
        else:
            time.sleep(0.1)

def rotateAxes(x, y, theta):
    """
    Take a correction in X and Y and rotate it
    by the known position angle of the camera

    This function accounts for non-orthogonalty
    between a camera's X/Y axes and the RA/Dec
    axes of the sky

    x' = x*cos(theta) + y*sin(theta)
    y' = -x*sin(theta) + y*cos(theta)

    Parameters
    -----------

    Returns
    -------

    Raises
    ------
    """
    x_new = x*cos(radians(theta)) + y*sin(radians(theta))
    y_new = -x*sin(radians(theta)) + y*cos(radians(theta))
    return x_new, y_new

def splitObjectIdIntoPidCoeffs(filename):
    """
    Take the special filename and pull out the coeff values

    Name should have the format:
        PXX.xx-IYY.yy-DZZ.zz

    If not, None is returned and this will force the
    PID coeffs back to the configured value

    Parameters
    ----------
    filename : string
        name of the file to extract PID coeffs from

    Returns
    -------
    p : float
        proportional coeff
    i : float
        integral coeff
    d : float
        derivative coeff

    Raises
    ------
    None
    """
    sp = os.path.split(filename)[1].split('-')
    if sp[0].startswith('P') and sp[1].startswith('I') and sp[2].startswith('D'):
        p = sp[0]
        i = sp[1]
        d = sp[2]
        p = round(float(p[1:]), 2)
        i = round(float(i[1:]), 2)
        d = round(float(d[1:]), 2)
    else:
        p, i, d = None, None, None
    return p, i, d

def getReferenceImage(field, filt):
    """
    Look in the database for the current
    field/filter reference image

    Parameters
    ----------
    field : string
        name of the current field
    filt : string
        name of the current filter

    Returns
    -------
    ref_image : string
        path to the reference image
        returns None if no reference image found

    Raises
    ------
    None
    """
    tnow = datetime.utcnow().isoformat().split('.')[0].replace('T', ' ')
    qry = """
        SELECT ref_image
        FROM autoguider_ref
        WHERE field = %s
        AND filter = %s
        AND valid_from < %s
        AND valid_until IS NULL
        """
    qry_args = (field, filt, tnow)
    with openDb(DB_HOST, DB_USER, DB_DATABASE, DB_PASS) as cur:
        cur.execute(qry, qry_args)
    result = cur.fetchone()
    if not result:
        ref_image = None
    else:
        ref_image = "{}\\{}".format(AUTOGUIDER_REF_DIR, result[0])
    return ref_image

def setReferenceImage(field, filt, ref_image, telescope):
    """
    Set a new image as a reference in the database

    Parameters
    ----------
    field : string
        name of the current field
    filt : string
        name of the current filter
    ref_image : string
        name of the image to set as reference
    telescope : string
        name of the telescope

    Returns
    -------

    Raises
    ------
    """
    tnow = datetime.utcnow().isoformat().split('.')[0].replace('T', ' ')
    qry = """
        INSERT INTO autoguider_ref
        (field, telescope, ref_image,
         filter, valid_from)
        VALUES
        (%s, %s, %s, %s, %s)
        """
    qry_args = (field, telescope, ref_image, filt, tnow)
    with openDb(DB_HOST, DB_USER, DB_DATABASE, DB_PASS) as cur:
        cur.execute(qry, qry_args)
    # copy the file to the autoguider_ref location
    #os.system('cp {} {}'.format(ref_image, AUTOGUIDER_REF_DIR))
    copyfile(ref_image, "{}/{}".format(AUTOGUIDER_REF_DIR, ref_image))

def stopAg(pypath, donutspath):
    """
    Call the donuts_process_handler to stop this guiding job
    """
    cmd = "{} {}\\donuts_process.py stop".format(pypath, donutspath)
    os.system(cmd)

if __name__ == "__main__":
    # read the command line args
    args = argParse()
    if args.instrument == 'nites':
        from nites import *
    elif args.instrument == 'io':
        from speculoos_io import *
    elif args.instrument == 'callisto':
        from speculoos_callisto import *
    elif args.instrument == 'europa':
        from speculoos_europa import *
    elif args.instrument == 'ganymede':
        from speculoos_ganymede import *
    elif args.instrument == 'saintex':
        from saintex import *
    elif args.instrument == 'artemis':
        from speculoos_artemis import *
    elif args.instrument == 'rcos20':
        from rcos20 import *
    else:
        sys.exit(1)

    # set up observatory location from coords in telescope file
    observatory = EarthLocation(lat=OLAT*u.deg, lon=OLON*u.deg, height=ELEV*u.m)

    # dictionaries to hold reference images for different fields/filters
    ref_track = defaultdict(dict)

    # outer loop to loop over field and night changes etc
    while 1:
        # initialise the PID controllers for X and Y
        PIDx = PID(PID_COEFFS['x']['p'], PID_COEFFS['x']['i'], PID_COEFFS['x']['d'])
        PIDy = PID(PID_COEFFS['y']['p'], PID_COEFFS['y']['i'], PID_COEFFS['y']['d'])
        PIDx.setPoint(PID_COEFFS['set_x'])
        PIDy.setPoint(PID_COEFFS['set_y'])

        # ag correction buffers - used for outlier rejection
        BUFF_X, BUFF_Y = [], []

        # look for tonight's directory
        data_loc = None
        sleep_time = 10
        # loop while waiting on data directory & scope to be connected
        while not data_loc:
            data_loc, night = getDataDir(DATA_SUBDIR)
            if data_loc:
                logMessageToDb(args.instrument,
                               "Found data directory: {}".format(data_loc))
                os.chdir(data_loc)
                break
            if not data_loc:
                logMessageToDb(args.instrument,
                               "[{}] No data directory yet...".format(strtime(datetime.utcnow())))
                sleep_time = 30
            time.sleep(sleep_time)

        # connect to ACP only after the data directory is found
        logMessageToDb(args.instrument, "Checking for the telescope...")
        myScope = win32com.client.Dispatch("ACP.Telescope")
        connected = myScope.Connected
        if not connected:
            logMessageToDb(args.instrument,
                           'Data directory exists but the telescope is not connected, quitting!')
            sys.exit(1)

        # if we get to here we assume we have found the data directory
        # and that the scope is connected
        # get a list of the images in the directory
        templist = g.glob('*{}'.format(IMAGE_EXTENSION))
        # add the logfile header row
        logShiftsToFile(LOGFILE, [], header=True)
        # check for any data in there
        n_images = len(templist)
        # if no images appear before the end of the night
        # just die quietly
        if n_images == 0:
            ag_status, last_file, _, _ = waitForImage(DATA_SUBDIR, "", n_images,
                                                      "", data_loc, observatory)
            if ag_status == ag_new_day:
                logMessageToDb(args.instrument,
                               "New day detected, ending process...")
                stopAg(PYTHONPATH, DONUTSPATH)
        else:
            last_file = max(templist, key=os.path.getctime)

        # check we can access the last file
        try:
            with fits.open(last_file) as ff:
                # current field and filter?
                current_filter = ff[0].header[FILTER_KEYWORD]
                current_field = ff[0].header[FIELD_KEYWORD]
                # Look for a reference image for this field/filter
                ref_file = getReferenceImage(current_field, current_filter)
                # if there is no reference image, set this one as it and continue
                # set the previous reference image
                if not ref_file:
                    setReferenceImage(current_field, current_filter, last_file, args.instrument)
                    ref_file = "{}\\{}".format(AUTOGUIDER_REF_DIR, last_file)
        except IOError:
            logMessageToDb(args.instrument, "Problem opening {}...".format(last_file))
            logMessageToDb(args.instrument, "Breaking back to check for new day...")
            continue

        # finally, load up the reference file for this field/filter
        logMessageToDb(args.instrument, "Ref_File: {}".format(ref_file))
        ref_track[current_field][current_filter] = ref_file
        # set up the reference image with donuts
        donuts_ref = Donuts(ref_file)
        # number of images alloed during initial pull in
        # -ve numbers mean ag should have stabilised
        images_to_stabilise = IMAGES_TO_STABILISE
        stabilised = 'n'

        # Now wait on new images
        while 1:
            ag_status, check_file, current_field, current_filter = waitForImage(DATA_SUBDIR,
                                                                                current_field,
                                                                                n_images,
                                                                                current_filter,
                                                                                data_loc,
                                                                                observatory)
            if ag_status == ag_new_day:
                logMessageToDb(args.instrument,
                               "New day detected, ending process...")
                stopAg(PYTHONPATH, DONUTSPATH)
            elif ag_status == ag_new_field or ag_status == ag_new_filter:
                logMessageToDb(args.instrument,
                               "New field/filter detected, looking for previous reference image...")
                # reset the PID coeffs to not carry performance across objects
                logMessageToDb(args.instrument, 'Resetting PID loop for new field...')
                PIDx = PID(PID_COEFFS['x']['p'], PID_COEFFS['x']['i'], PID_COEFFS['x']['d'])
                PIDy = PID(PID_COEFFS['y']['p'], PID_COEFFS['y']['i'], PID_COEFFS['y']['d'])
                PIDx.setPoint(PID_COEFFS['set_x'])
                PIDy.setPoint(PID_COEFFS['set_y'])
                try:
                    ref_file = ref_track[current_field][current_filter]
                    donuts_ref = Donuts(ref_file)
                    images_to_stabilise = IMAGES_TO_STABILISE
                except KeyError:
                    logMessageToDb(args.instrument, 'No reference in ref_track for this field/filter')
                    logMessageToDb(args.instrument, 'Skipping back to reference image checks...')
                    break
            else:
                logMessageToDb(args.instrument, "Same field and same filter, continuing...")
                logMessageToDb(args.instrument,
                               "REF: {} CHECK: {} [{}]".format(ref_track[current_field][current_filter],
                                                               check_file, current_filter))
                images_to_stabilise -= 1
                # if we are done stabilising, reset the PID loop
                if images_to_stabilise == 0:
                    logMessageToDb(args.instrument, 'Stabilisation complete, reseting PID loop...')
                    PIDx = PID(PID_COEFFS['x']['p'], PID_COEFFS['x']['i'], PID_COEFFS['x']['d'])
                    PIDy = PID(PID_COEFFS['y']['p'], PID_COEFFS['y']['i'], PID_COEFFS['y']['d'])
                    PIDx.setPoint(PID_COEFFS['set_x'])
                    PIDy.setPoint(PID_COEFFS['set_y'])
                elif images_to_stabilise > 0:
                    logMessageToDb(args.instrument, 'Stabilising using P=1.0, I=0.0, D=0.0')
                    PIDx = PID(1.0, 0.0, 0.0)
                    PIDy = PID(1.0, 0.0, 0.0)
                    PIDx.setPoint(PID_COEFFS['set_x'])
                    PIDy.setPoint(PID_COEFFS['set_y'])

            # test load the comparison image to get the shift
            try:
                h2 = fits.open(check_file)
                del h2
            except IOError:
                logMessageToDb(args.instrument, "Problem opening CHECK: {}...".format(check_file))
                logMessageToDb(args.instrument, "Breaking back to look for new file...")
                continue

            # reset culled tags
            culled_max_shift_x = 'n'
            culled_max_shift_y = 'n'
            # work out shift here
            shift = donuts_ref.measure_shift(check_file)
            shift_x = shift.x.value
            shift_y = shift.y.value
            logMessageToDb(args.instrument, "x shift: {:.2f}".format(float(shift_x)))
            logMessageToDb(args.instrument, "y shift: {:.2f}".format(float(shift_y)))
            # revoke stabilisation early if shift less than 2 pixels
            if abs(shift_x) <= 2.0 and abs(shift_y) < 2.0 and images_to_stabilise > 0:
                images_to_stabilise = 1

            # Check if shift greater than max allowed error in post pull in state
            if images_to_stabilise < 0:
                stabilised = 'y'
                if abs(shift_x) > MAX_ERROR_PIXELS:
                    logMessageToDb(args.instrument,
                                   "X shift > {}, applying no correction".format(MAX_ERROR_PIXELS))
                    culled_max_shift_x = 'y'
                else:
                    pre_pid_x = shift_x
                if abs(shift_y) > MAX_ERROR_PIXELS:
                    logMessageToDb(args.instrument,
                                   "Y shift > {}, applying no correction".format(MAX_ERROR_PIXELS))
                    culled_max_shift_y = 'y'
                else:
                    pre_pid_y = shift_y
            else:
                logMessageToDb(args.instrument,
                               'Allowing field to stabilise, imposing new max error clip')
                stabilised = 'n'
                if shift_x > MAX_ERROR_STABIL_PIXELS:
                    pre_pid_x = MAX_ERROR_STABIL_PIXELS
                elif shift_x < -MAX_ERROR_STABIL_PIXELS:
                    pre_pid_x = -MAX_ERROR_STABIL_PIXELS
                else:
                    pre_pid_x = shift_x

                if shift_y > MAX_ERROR_STABIL_PIXELS:
                    pre_pid_y = MAX_ERROR_STABIL_PIXELS
                elif shift_y < -MAX_ERROR_STABIL_PIXELS:
                    pre_pid_y = -MAX_ERROR_STABIL_PIXELS
                else:
                    pre_pid_y = shift_y
            # if either axis is off by > MAX error then stop everything, no point guiding
            # in 1 axis, need to figure out the source of the problem and run again
            if culled_max_shift_x == 'y' or culled_max_shift_y == 'y':
                pre_pid_x, pre_pid_y, post_pid_x, post_pid_y, \
                    std_buff_x, std_buff_y = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            else:
                applied, post_pid_x, post_pid_y, \
                    std_buff_x, std_buff_y = guide(pre_pid_x, pre_pid_y,
                                                   images_to_stabilise)
                # !applied means no telescope, break to tomorrow
                if not applied:
                    logMessageToDb(args.instrument,
                                   'SHIFT NOT APPLIED, TELESCOPE *NOT* CONNECTED, EXITING')
                    stopAg(PYTHONPATH, DONUTSPATH)
            log_list = [night,
                        os.path.split(ref_file)[1],
                        check_file,
                        stabilised,
                        str(round(shift_x, 3)),
                        str(round(shift_y, 3)),
                        str(round(pre_pid_x, 3)),
                        str(round(pre_pid_y, 3)),
                        str(round(post_pid_x, 3)),
                        str(round(post_pid_y, 3)),
                        str(round(std_buff_x, 3)),
                        str(round(std_buff_y, 3)),
                        culled_max_shift_x,
                        culled_max_shift_y]

            # log info to file
            logShiftsToFile(LOGFILE, log_list)
            # log info to database - enable when DB is running
            logShiftsToDb(tuple(log_list))
            # reset the comparison templist so the nested while(1) loop
            # can find new images
            templist = g.glob("*{}".format(IMAGE_EXTENSION))
            n_images = len(templist)
