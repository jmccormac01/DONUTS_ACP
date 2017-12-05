"""
ACP + DONUTS Autoguiding

Usage:
    $> python acp_guider.py INSTRUMENT [--debug]

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

# TODO: Assumes field name is in the filename, add check to header if not

# get command line arguments
def argParse():
    """
    Parse command line arguments
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
    Return a string formatted datetime
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S')

# check the telescope
def scopeCheck(verbose):
    """
    Check the telescope and connect
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
    Generic guide command

    Pulse Guiding Command Config:
    Directions:   0 - guideNorth
                  1 - guideSouth
                  2 - guideEast
                  3 - guideWest

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
            myScope.PulseGuide(DIRECTIONS['+y'], (pidy * PIX2TIME['y'])/cos_dec)
        if pidy < 0:
            myScope.PulseGuide(DIRECTIONS['-y'], abs(pidy * PIX2TIME['y'])/cos_dec)
        while myScope.IsPulseGuiding == 'True':
            time.sleep(0.10)
        if pidx > 0:
            myScope.PulseGuide(DIRECTIONS['+x'], pidx * PIX2TIME['x'])
        if pidx < 0:
            myScope.PulseGuide(DIRECTIONS['-x'], abs(pidx * PIX2TIME['x']))
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
def logShifts(logfile, ref, name, x, y, cx, cy):
    """
    Log the guide corrections
    """
    with open(logfile, "a") as outfile:
        line = "[{}] {}\t{}\t{:.2f}\t{:.2f}\t{}\t{}\n".format(datetime.utcnow().isoformat(),
                                                              ref, name, x, y, cx, cy)
        outfile.write(line)

# get evening or morning
def getAmOrPm():
    """
    Get if it is morning or afteroon
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
    """
    token = getAmOrPm()
    if token > 0 and tomorrow > 0:
        tomorrow = 0
    d = date.today()-timedelta(days=token)+timedelta(days=tomorrow)
    x = "%d%02d%02d" % (d.year, d.month, d.day)
    data_loc = "%s%s" % (BASE_DIR, x)
    if os.path.exists(data_loc):
        return data_loc
    else:
        return 1

# wait for the newest image
def waitForImage(field, tlim, imgs, cf):
    """
    Wait for images
    """
    timeout = 0
    while 1:
        t = g.glob(IMAGE_EXTENSION)
        # get newest image
        try:
            newest_img = max(t, key=os.path.getctime)
        except ValueError:
            newest_img = 'xxx.fts'
        # check for no images or Tabby
        if len(t) == imgs:
            timeout = timeout + 1
            time.sleep(1)
            if timeout % 5 == 0:
                print("[{}/{}:{} - {}] No new images...".format(timeout, tlim, imgs,
                                                                strtime(datetime.utcnow())))
            if timeout > tlim:
                print("No new images in {} min, exiting...".format(int(tlim/60.)))
                return 1
            continue
        # check for new images and not Tabby
        if len(t) > imgs:
            timeout = 0
            # check for latest image - wait to be sure it's on disk
            time.sleep(1)
            # check what filter
            try:
                h = fits.open(newest_img)
            except IOError:
                print("Problem opening {0:s}...".format(newest_img))
                continue
            nf = h[0].header[FILTER_KEYWORD]
            # new start? if so, return the first new image
            if field == "" and cf == "":
                print("New start...")
                return newest_img, nf
            # check that the field is the same
            if field != "" and field not in newest_img:
                print("New field detected...")
                return 999, nf
            # check that the field is the same but filter has changed
            if field != "" and field in newest_img and cf != nf:
                print("Same field but different filter, changing ref image...")
                return 888, nf
            # check the field ad filters are the same
            if field != "" and field in newest_img and cf == nf:
                print("Same field and same filter, continuing...")
                return newest_img, cf

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
    # dictionaries to hold reference projections from different filters
    # and reference file names for printing
    ref_xproj = {}
    ref_yproj = {}
    ref_track = {}
    # multiple day loop
    while 1:
        # check the telescope to sure make it's ready to go
        connected, can, site = scopeCheck("full")
        # run in daemon mode, looking for tonight's directory
        data_loc = 1
        sleep_time = 10
        # loop while waiting on data directory & scope to be connected
        while data_loc == 1:
            time.sleep(sleep_time)
            data_loc = getDataDir(tomorrow)
            connected, can, site = scopeCheck("simple")
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
        templist = g.glob(IMAGE_EXTENSION)
        # check for any data in there
        old_i = len(templist)
        # if no reference images appear for WAITTIME, roll out to tomorrow
        if old_i == 0:
            ref_file, cf = waitForImage("", WAITTIME, 0, "")
            if ref_file == 1:
                print("Rolling back to tomorrow...")
                token = getAmOrPm()
                if token == 0:
                    tomorrow = 0
                else:
                    tomorrow = 1
                # reset projection dictionaries
                ref_xproj = {}
                ref_yproj = {}
                ref_track = {}
                continue
        else:
            ref_file = max(templist, key=os.path.getctime)
        # check we can access the reference file
        try:
            h = fits.open(ref_file)
        except IOError:
            print("Problem opening REF: {}...".format(ref_file))
            print("Breaking back to the start for new reference image")
            continue
        print("Ref_File: {}".format(ref_file))
        # filter?
        cf = h[0].header[FILTER_KEYWORD]
        ref_track[cf] = ref_file
        # set up the reference image with donuts
        donuts_ref = Donuts(ref_file)
        # now wait on new images
        while 1:
            check_file, cf = waitForImage(ref_file.split('-')[0], WAITTIME, old_i, cf)
            if check_file == 1:
                print("Breaking back to first checks (i.e. tomorrow)")
                token = getAmOrPm()
                if token == 1:
                    tomorrow = 0
                else:
                    tomorrow = 1
                # reset projection dictionaries
                ref_xproj = {}
                ref_yproj = {}
                ref_track = {}
                break
            elif check_file == 999:
                print("New field detected, breaking back to reference image creator")
                # reset projection dictionaries
                ref_xproj = {}
                ref_yproj = {}
                ref_track = {}
                break
            elif check_file == 888:
                print("New filter detected, looking for previous ref projections...")
                try:
                    prod = ref_xproj[cf]
                    continue
                except KeyError:
                    print("No reference projections for this filter, skipping to reference image creator")
                    break
            print("REF: {} CHECK: {} [{}]".format(ref_track[cf], check_file, cf))
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
            templist = g.glob(IMAGE_EXTENSION)
            old_i = len(templist)
