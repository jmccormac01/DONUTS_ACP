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
from datetime import (
    date,
    timedelta,
    datetime)
from math import (
    radians,
    cos)
from collections import defaultdict
import argparse as ap
import glob as g
import numpy as np
import win32com.client
from astropy.io import fits
from PID import PID
from donuts import Donuts

# pylint: disable = invalid-name
# pylint: disable = redefined-outer-name
# pylint: disable = line-too-long

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
        else:
            if abs(x) > SIGMA_BUFFER * np.std(BUFF_X) or abs(y) > SIGMA_BUFFER * np.std(BUFF_Y):
                print('Guide error > {} sigma * buffer errors, ignoring...'.format(SIGMA_BUFFER))
                return 0
            else:
                pass
        # update the PID controllers, run them in parallel
        pidx = PIDx.update(x) * -1
        pidy = PIDy.update(y) * -1
        print("PID: {0:.2f}  {1:.2f}".format(float(pidx), float(pidy)))
        # abs() on -ve duration otherwise throws back an error
        if pidy > 0:
            guide_time_y = pidy * PIX2TIME['+y']
            if RA_AXIS == 'y':
                guide_time_y = guide_time_y/cos_dec
            myScope.PulseGuide(DIRECTIONS['+y'], guide_time_y)
        if pidy < 0:
            guide_time_y = abs(pidy * PIX2TIME['-y'])
            if RA_AXIS == 'y':
                guide_time_y = guide_time_y/cos_dec
            myScope.PulseGuide(DIRECTIONS['-y'], guide_time_y)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.10)
        if pidx > 0:
            guide_time_x = pidx * PIX2TIME['+x']
            if RA_AXIS == 'x':
                guide_time_x = guide_time_x/cos_dec
            myScope.PulseGuide(DIRECTIONS['+x'], guide_time_x)
        if pidx < 0:
            guide_time_x = abs(pidx * PIX2TIME['-x'])
            if RA_AXIS == 'x':
                guide_time_x = guide_time_x/cos_dec
            myScope.PulseGuide(DIRECTIONS['-x'], guide_time_x)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.10)
        print("Guide correction Applied")
        success = True
        # store the original values in the buffer
        BUFF_X.append(x)
        BUFF_Y.append(y)
    else:
        print("Telescope NOT connected!")
        print("Please connect Telescope via ACP!")
        print("Ignoring corrections!")
        success = False
    return success

# log guide corrections
def logShifts(logfile, ref, check, x, y, cx, cy):
    """
    Log the guide corrections to disc. This log is
    typically located with the data files for each night

    Parameters
    ----------
    logfile : string
        Path to the logfile
    ref : str
        Name of the current reference image
    check : string
        Name of the current guide image
    x : float
        Guide correction in X direction
    y : float
        Guide correction in Y direction
    cx : string
        Culled X measurement? y | n
    cy : string
        Culled Y measurement? y | n

    Returns
    -------
    None

    Raises
    ------
    None
    """
    with open(logfile, "a") as outfile:
        line = "[{}] {}\t{}\t{:.2f}\t{:.2f}\t{}\t{}\n".format(datetime.utcnow().isoformat(),
                                                              ref, check, x, y, cx, cy)
        outfile.write(line)

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
    else:
        return 1

# wait for the newest image
def waitForImage(current_field, timeout_limit, n_images, current_filter):
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
    timeout_limit : int
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
    timeout = 0
    while 1:
        t = g.glob('*{}'.format(IMAGE_EXTENSION))
        # get newest image
        try:
            newest_image = max(t, key=os.path.getctime)
            newest_field = fits.open(newest_image)[0].header[FIELD_KEYWORD]
        except ValueError:
            newest_image = 'xxx.fts'
            newest_field = "xxx"
        # check for no images or Tabby
        if len(t) == n_images:
            timeout = timeout + 1
            time.sleep(1)
            if timeout % 5 == 0:
                print("[{}/{}:{} - {}] No new images...".format(timeout, timeout_limit, n_images,
                                                                strtime(datetime.utcnow())))
            if timeout > timeout_limit:
                print("No new images in {} min, exiting...".format(int(timeout_limit/60.)))
                return ag_timeout, newest_image, None, None
            continue
        # check for new images and not Tabby
        if len(t) > n_images:
            timeout = 0
            # check for latest image - wait to be sure it's on disk
            time.sleep(1)
            # check what filter
            try:
                h = fits.open(newest_image)
            except IOError:
                print("Problem opening {0:s}...".format(newest_image))
                continue
            newest_filter = h[0].header[FILTER_KEYWORD]
            newest_field = h[0].header[FIELD_KEYWORD]
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
            culledx = 'n'
            culledy = 'n'
            # work out shift here
            shift = donuts_ref.measure_shift(check_file)
            solution_x = shift.x.value
            solution_y = shift.y.value
            print("x shift: {:.2f}".format(float(solution_x)))
            print("y shift: {:.2f}".format(float(solution_y)))
            # Check if shift great than max allowed error
            if solution_x > MAX_ERROR_PIXELS:
                print("X shift > {}, applying no correction".format(MAX_ERROR_PIXELS))
                solution_x = 0.0
                culledx = 'y'
            if solution_y > MAX_ERROR_PIXELS:
                print("Y shift > {}, applying no correction".format(MAX_ERROR_PIXELS))
                solution_y = 0.0
                culledy = 'y'
            if not args.debug:
                applied = guide(solution_x, solution_y)
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
            logShifts(LOGFILE, ref_file, check_file,
                      solution_x, solution_y, culledx,
                      culledy)
            # reset the comparison templist so the nested while(1) loop
            # can find new images
            templist = g.glob("*{}".format(IMAGE_EXTENSION))
            n_images = len(templist)
