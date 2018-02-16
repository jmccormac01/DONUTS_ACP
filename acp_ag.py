"""
ACP + DONUTS Autoguiding

Usage:
    $> python acp_ag.py INSTRUMENT [--debug]

where INSRTRUMENT can be:
    nites
    speculoos

and --debug disables corrections being sent to the telescope
"""
import time
import os
import sys
from contextlib import contextmanager
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
from PID import PID
from donuts import Donuts

# pylint: disable = invalid-name
# pylint: disable = redefined-outer-name
# pylint: disable = line-too-long
# pylint: disable = no-member

# TODO : Test the rotation of ccd axes

# autoguider status flags
ag_timeout, ag_new_start, ag_new_field, ag_new_filter, ag_no_change = range(5)

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
                   choices=['nites', 'speculoos'])
    p.add_argument("--debug",
                   help="runs the script without applying corrections",
                   action="store_true")
    return p.parse_args()

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

# check the telescope
def scopeCheck(verbose):
    """
    Check the telescope and connect

    Parameters
    ----------
    verbose : string
        Level of verbosity

    Returns
    -------
    connected : boolean
        Is the telescope currently connected?
    can : array-like
        List of things the telescope can do
    site : array-like
        List of observatory site information

    Raises
    ------
    None
    """
    can, site = [], []
    connected = myScope.Connected
    if str(connected) == 'True' and verbose == "full":
        can.append(myScope.CanPark)
        can.append(myScope.CanPulseGuide)
        can.append(myScope.CanSetGuideRates)
        can.append(myScope.CanSetPierSide)
        can.append(myScope.CanSetTracking)
        can.append(myScope.CanSlew)
        can.append(myScope.CanSlewAltAz)
        can.append(myScope.CanSlewAltAzAsync)
        can.append(myScope.CanSlewAsync)
        can.append(myScope.CanSync)
        can.append(myScope.CanUnpark)
        can.append(myScope.CanSyncAltAz)
        can.append(myScope.CanSetRightAscensionRate)
        can.append(myScope.CanSetPark)
        can.append(myScope.CanSetDeclinationRate)
        can.append(myScope.CanFindHome)
        site.append(myScope.Name)
        site.append(myScope.AlignmentMode) # 0,1,2 - AltAz, Polar, Polar German
        site.append(myScope.SiteElevation)
        site.append(myScope.SiteLatitude)
        site.append(myScope.SiteLongitude)
        print("\n-------------------------------------------------")
        print("                Functionality Check")
        print("-------------------------------------------------\n")
        print("Telescope is connected: " + str(connected))
        print("Scope can/cannot:")
        print("                  Park: " + str(can[0]))
        print("                Unpark: " + str(can[10]))
        print("            PulseGuide: " + str(can[1]))
        print("         SetGuideRates: " + str(can[2]))
        print("           SetPierSide: " + str(can[3]))
        print("           SetTracking: " + str(can[4]))
        print("                  Slew: " + str(can[5]))
        print("             SlewAltAz: " + str(can[6]))
        print("        SlewAltAzAsync: " + str(can[7]))
        print("             SlewAsync: " + str(can[8]))
        print("                  Sync: " + str(can[9]))
        print("             SyncAltAz: " + str(can[11]))
        print(" SetRightAscensionRate: " + str(can[12]))
        print("               SetPark: " + str(can[13]))
        print("    SetDeclinationRate: " + str(can[14]))
        print("              FindHome: " + str(can[12]))
    return connected, can, site

# apply guide corrections
def guide(x, y):
    """
    Generic autoguiding command with built-in PID control loop
    guide() will track recent autoguider corrections and ignore
    abnormally large offsets. It will also handle orientation
    and scale conversions as per the telescope specific config
    file.

    Parameters
    ----------
    x : float
        Guide correction to make in X direction
    y : float
        Guide correction to make in Y direction

    Returns
    -------
    success : boolean
        Was the correction applied successfully?
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
        # kill anything that is > sigma_buffer sigma buffer stats
        if len(BUFF_X) < GUIDE_BUFFER_LENGTH and len(BUFF_Y) < GUIDE_BUFFER_LENGTH:
            print('Filling AG stats buffer...')
            sigma_x = 0.0
            sigma_y = 0.0
        else:
            sigma_x = np.std(BUFF_X)
            sigma_y = np.std(BUFF_Y)
            if abs(x) > SIGMA_BUFFER * sigma_x or abs(y) > SIGMA_BUFFER * sigma_y:
                print('Guide error > {} sigma * buffer errors, ignoring...'.format(SIGMA_BUFFER))
                # store the original values in the buffer, even if correction
                # was too big, this will allow small outliers to be caught
                BUFF_X.append(x)
                BUFF_Y.append(y)
                return True, 0.0, 0.0, sigma_x, sigma_y
            else:
                pass
        # update the PID controllers, run them in parallel
        pidx = PIDx.update(x) * -1
        pidy = PIDy.update(y) * -1
        print("PID: {0:.2f}  {1:.2f}".format(float(pidx), float(pidy)))
        # make another check that the post PID values are not > Max allowed
        # abs() on -ve duration otherwise throws back an error
        if pidy > 0 and pidy < MAX_ERROR_PIXELS:
            guide_time_y = pidy * PIX2TIME['+y']
            if RA_AXIS == 'y':
                guide_time_y = guide_time_y/cos_dec
            myScope.PulseGuide(DIRECTIONS['+y'], guide_time_y)
        if pidy < 0 and pidy > -MAX_ERROR_PIXELS:
            guide_time_y = abs(pidy * PIX2TIME['-y'])
            if RA_AXIS == 'y':
                guide_time_y = guide_time_y/cos_dec
            myScope.PulseGuide(DIRECTIONS['-y'], guide_time_y)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.01)
        if pidx > 0 and pidx < MAX_ERROR_PIXELS:
            guide_time_x = pidx * PIX2TIME['+x']
            if RA_AXIS == 'x':
                guide_time_x = guide_time_x/cos_dec
            myScope.PulseGuide(DIRECTIONS['+x'], guide_time_x)
        if pidx < 0 and pidx > -MAX_ERROR_PIXELS:
            guide_time_x = abs(pidx * PIX2TIME['-x'])
            if RA_AXIS == 'x':
                guide_time_x = guide_time_x/cos_dec
            myScope.PulseGuide(DIRECTIONS['-x'], guide_time_x)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.01)
        print("Guide correction Applied")
        # store the original values in the buffer
        BUFF_X.append(x)
        BUFF_Y.append(y)
        return True, pidx, pidy, sigma_x, sigma_y
    else:
        print("Telescope NOT connected!")
        print("Please connect Telescope via ACP!")
        print("Ignoring corrections!")
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
        ref : str
            Name of the current reference image
        check : string
            Name of the current guide image
        solution_x : float
            Shift measured in X direction
        solution_y : float
            Shift measured in Y direction
        culled_max_shift_x : string
            Culled X measurement if > max allowed shift (y | n)
        culled_max_shift_y : string
            Culled Y measurement if > max allowed shift (y | n)
        pid_X : float
            X correction sent to the mount, post PID loop
        pid_y : float
            Y correction sent to the mount, post PID loop
        std_buff_x : float
            Sttdev of X AG value buffer
        std_buff_y : float
            Sttdev of Y AG value buffer
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
        line = "Ref  Check  sol_x  sol_y  cull_x  cull_y  pid_x  pid_y  std_buff_x  std_buff_y"
    else:
        line = "  ".join(loglist)
    with open(logfile, "a") as outfile:
        outfile.write("{}\n".format(line))

@contextmanager
def openDB(host, user, db, passwd):
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
        INSERT INTO autoguider_log
        (reference, comparison, solution_x, solution_y,
         culled_max_shift_x, culled_max_shift_y,
         pid_x, pid_y, std_buff_x, std_buff_y)
        VALUES
        (%s, %s, %s, %s, %s,
         %s, %s, %s, %s, %s)
        """
    with openDB(DB_HOST, DB_USER, DB_DATABASE, DB_PASS) as cur:
        cur.execute(qry, qry_args)

# get evening or morning
def getAmOrPm():
    """
    Determine if it is morning or afteroon

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
    now = datetime.utcnow()
    if now.hour >= 12:
        token = 0
    else:
        token = 1
    return token

# get tonights directory
def getDataDir(tomorrow):
    """
    Get tonight's data directory

    Parameters
    ----------
    tomorrow : int
        Number of days since daemon started

    Returns
    -------
    data_loc : string
        Path to tonight's data directory

    Raises
    ------
    None
    """
    token = getAmOrPm()
    if token > 0 and tomorrow > 0:
        tomorrow = 0
    d = date.today()-timedelta(days=token)+timedelta(days=tomorrow)
    x = "%d%02d%02d" % (d.year, d.month, d.day)
    data_loc = "%s\\%s" % (BASE_DIR, x)
    if os.path.exists(data_loc):
        return data_loc
    return 1

# wait for the newest image
def waitForImage(current_field, timeout_limit_seconds, n_images, current_filter):
    """
    Wait for new images. Several things can happen:
        0. No new images come before timeout time, night is over
        1. A new image comes in of new field and filter (new start)
        2. A new image comes in but of a new field (new field)
        3. A new image comes in but with a different filter (new filter)
        4. No change occurs and same field and filter apply (no_change)

    Parameters
    ----------
    current_field : string
        name of the current target
    timeout_limit_seconds : int
        timeout in seconds before giving up for the night
    n_images : int
        number of images previously acquired
    current_filter : string
        name of the current filter

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
    tnow = datetime.utcnow()
    timeout_time = tnow + timedelta(seconds=timeout_limit_seconds)
    while tnow < timeout_time:
        t = g.glob('*{}'.format(IMAGE_EXTENSION))
        # check for new images
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
                # if the file cannot be accessed (not completely written to disc yet
                # cycle back and try again
                print('Problem accessing fits file {}, skipping...'.format(newest_image))
                continue
            # new start? if so, return the first new image
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
    print("No new images in {} min, exiting...".format(int(timeout_limit_seconds/60.)))
    return ag_timeout, newest_image, None, None

def rotateAxes(x, y, theta):
    """
    Take a correction in X and Y and rotate it
    by the known position angle of the camera

    This function accounts for non-orthogonalty
    between a camera's X/Y axes and the RA/Dec
    axes of the sky

    x' = x*cos(theta) + y*sin(theta)
    y' = -x*sin(theta) + y*cos(theta)

    Paramaeters
    -----------

    Returns
    -------

    Raises
    ------
    """
    x_new = x*cos(radians(theta)) + y*sin(radians(theta))
    y_new = -x*sin(radians(theta)) + y*cos(radians(theta))
    return x_new, y_new

if __name__ == "__main__":
    # read the command line args
    args = argParse()
    if args.instrument == 'nites':
        from nites import *
    elif args.instrument == 'speculoos':
        from speculoos import *
    else:
        sys.exit(1)
    # initialise the PID controllers for X and Y
    PIDx = PID(PID_COEFFS['x']['p'], PID_COEFFS['x']['i'], PID_COEFFS['x']['d'])
    PIDy = PID(PID_COEFFS['y']['p'], PID_COEFFS['y']['i'], PID_COEFFS['y']['d'])
    PIDx.setPoint(PID_COEFFS['set_x'])
    PIDy.setPoint(PID_COEFFS['set_y'])
    # ag buffers
    BUFF_X, BUFF_Y = [], []
    # debugging mode?
    if args.debug:
        print("\n**********************")
        print("* DEBUGGING Mode ON! *")
        print("**********************\n")
    # connect to ACP
    if not args.debug:
        print("Checking for the telescope...")
        myScope = win32com.client.Dispatch("ACP.Telescope")
    elif args.debug:
        print("[SIM] Connecting to telescope...")
        time.sleep(3)
    else:
        print("Unknown status of DEBUG, exiting...")
        sys.exit(1)
    # used to determine when a night is classified as over
    tomorrow = 0
    # dictionaries to hold reference images for different fields/filters
    ref_track = defaultdict(dict)
    # multiple day loop
    while 1:
        # check the telescope to sure make it's ready to go
        if not args.debug:
            connected, can, site = scopeCheck("full")
        else:
            connected = True
        # run in daemon mode, looking for tonight's directory
        data_loc = 1
        sleep_time = 10
        # loop while waiting on data directory & scope to be connected
        while data_loc == 1:
            time.sleep(sleep_time)
            data_loc = getDataDir(tomorrow)
            if not args.debug:
                connected, can, site = scopeCheck("simple")
            else:
                connected = True
            if connected and data_loc != 1:
                print("Found data directory: {}".format(data_loc))
                os.chdir(data_loc)
                break
            if not connected:
                print("[{}] Scope not connected...".format(strtime(datetime.utcnow())))
                data_loc = 1
                sleep_time = 120
                continue
            print("[{}] No data directory yet...".format(strtime(datetime.utcnow())))
            sleep_time = 120
        # if we get to here we assume we have found the data directory
        # and that the scope is connected
        # get a list of the images in the directory
        templist = g.glob('*{}'.format(IMAGE_EXTENSION))
        # add the logfile header row
        logShiftsToFile(LOGFILE, [], header=True)
        # check for any data in there
        n_images = len(templist)
        # if no reference images appear for WAITTIME, roll out to tomorrow
        if n_images == 0:
            ag_status, ref_file, current_field, current_filter = waitForImage("", WAITTIME, n_images, "")
            if ag_status == ag_new_start:
                print("Rolling back to tomorrow...")
                token = getAmOrPm()
                if token == 0:
                    tomorrow = 0
                else:
                    tomorrow = 1
                # reset the reference images
                ref_track = defaultdict(dict)
                continue
        else:
            ref_file = max(templist, key=os.path.getctime)
        # check we can access the reference file
        try:
            h = fits.open(ref_file)
            # current field and filter?
            current_filter = h[0].header[FILTER_KEYWORD]
            current_field = h[0].header[FIELD_KEYWORD]
        except IOError:
            print("Problem opening REF: {}...".format(ref_file))
            print("Breaking back to the start for new reference image")
            continue
        print("Ref_File: {}".format(ref_file))
        ref_track[current_field][current_filter] = ref_file
        # set up the reference image with donuts
        donuts_ref = Donuts(ref_file)
        # now wait on new images
        while 1:
            ag_status, check_file, current_field, current_filter = waitForImage(current_field,
                                                                                WAITTIME, n_images,
                                                                                current_filter)
            if ag_status == ag_new_start:
                print("New start...")
                print("Breaking back to intial checks (i.e. assumed it is now tomorrow)...")
                token = getAmOrPm()
                if token == 1:
                    tomorrow = 0
                else:
                    tomorrow = 1
                # reset the reference image tracker
                ref_track = defaultdict(dict)
                break
            elif ag_status == ag_new_field:
                print("New field detected, looking for previous reference image...")
                try:
                    ref_file = ref_track[current_field][current_filter]
                    donuts_ref = Donuts(ref_file)
                except KeyError:
                    print('No reference for this field/filter, skipping back to reference creation...')
                    break
            elif ag_status == ag_new_filter:
                print("New filter detected, looking for previous reference image...")
                try:
                    ref_file = ref_track[current_field][current_filter]
                    donuts_ref = Donuts(ref_file)
                    continue
                except KeyError:
                    print("No reference for this field/filter, skipping back to reference creation")
                    break
            else:
                print("Same field and same filter, continuing...")
                print("REF: {} CHECK: {} [{}]".format(ref_track[current_field][current_filter],
                                                      check_file, current_filter))
            try:
                h2 = fits.open(check_file)
            except IOError:
                print("Problem opening CHECK: {}...".format(check_file))
                print("Breaking back to look for new file...")
                continue
            # reset culled tags
            culled_max_shift_x = 'n'
            culled_max_shift_y = 'n'
            # work out shift here
            shift = donuts_ref.measure_shift(check_file)
            solution_x = shift.x.value
            solution_y = shift.y.value
            print("x shift: {:.2f}".format(float(solution_x)))
            print("y shift: {:.2f}".format(float(solution_y)))
            # Check if shift great than max allowed error
            if solution_x > MAX_ERROR_PIXELS:
                print("X shift > {}, applying no correction".format(MAX_ERROR_PIXELS))
                culled_max_shift_x = 'y'
            if solution_y > MAX_ERROR_PIXELS:
                print("Y shift > {}, applying no correction".format(MAX_ERROR_PIXELS))
                culled_max_shift_y = 'y'
            # if either axis is off by > MAX error then stop everything, no point guiding
            # in 1 axis, need to figure out the source of the problem and run again
            if culled_max_shift_x == 'y' or culled_max_shift_y == 'y':
                pid_x, pid_y, std_buff_x, std_buff_y = 0.0, 0.0, 0.0, 0.0
            else:
                if not args.debug:
                    applied, pid_x, pid_y, std_buff_x, std_buff_y = guide(solution_x, solution_y)
                    if not applied:
                        print("Breaking back to first checks (i.e. tomorrow)")
                        token = getAmOrPm()
                        if token == 1:
                            tomorrow = 0
                        else:
                            tomorrow = 1
                        break
                if args.debug:
                    print("[SIM] Guide correction Applied")
            log_list = [ref_file, check_file,
                        round(solution_x, 2),
                        round(solution_y, 2),
                        culled_max_shift_x,
                        culled_max_shift_y,
                        round(pid_x, 2),
                        round(pid_y, 2),
                        round(std_buff_x, 2),
                        round(std_buff_y, 2)]
            # log info to file
            logShiftsToFile(LOGFILE, log_list)
            # log info to database - enable when DB is running
            logShiftsToDb(tuple(log_list))
            # reset the comparison templist so the nested while(1) loop
            # can find new images
            templist = g.glob("*{}".format(IMAGE_EXTENSION))
            n_images = len(templist)
