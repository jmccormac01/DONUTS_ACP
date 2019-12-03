"""
Script to calibrate the pulseGuide command

This is done by pointing the telescope at the meridian
and 0 deg Declination. The telescope is then pulseGuided
around the sky in a cross pattern, taking an image at each
location. DONUTS is then used to measure the shift and
determine the camera orientation and pulseGuide conversion
factors
"""
import sys
import time
import argparse as ap
from collections import defaultdict
import numpy as np
import win32com.client
from donuts import Donuts

# pylint: disable=invalid-name
# pylint: disable=redefined-outer-name

def argParse():
    """
    Parse command line arguments
    """
    p = ap.ArgumentParser()
    p.add_argument('instrument',
                   help='name of the instrument to calibrate',
                   choices=['nites', 'io',
                            'callisto', 'europa',
                            'ganymede', 'saintex',
                            'artemis', 'rcos20'])
    p.add_argument('--pulse_time',
                   help='time (ms) to pulse the mount during calibration',
                   default=5000)
    return p.parse_args()

def connectTelescope():
    """
    A reusable way to connect to ACP telescope
    """
    print("Connecting to telescope...")
    myScope = win32com.client.Dispatch("ACP.Telescope")
    try:
        SCOPE_READY = myScope.connected
        print('Telescope connected')
    except AttributeError:
        print('WARNING: CANNOT CONNECT TO TELESCOPE')
        SCOPE_READY = False
    return myScope, SCOPE_READY

def connectCamera():
    """
    A reusable way of checking camera connection

    The camera needs treated slightly differently. We
    have to try connecting before we can tell if
    connected or not. Annoying!
    """
    print("Connecting to camera...")
    myCamera = win32com.client.Dispatch("MaxIm.CCDCamera")
    try:
        myCamera.LinkEnabled = True
        myCamera.DisableAutoShutdown = True
        CAMERA_READY = True
        print('Camera connected')
    except AttributeError:
        print('WARNING: CANNOT CONNECT TO CAMERA')
        CAMERA_READY = False
    return myCamera, CAMERA_READY

def takeImageWithMaxIm(camera_object, image_path, filter_id=1,
                       exptime=10, t_settle=1):
    """
    Take an image with MaxImDL
    """
    print('Waiting {}s to settle...'.format(t_settle))
    time.sleep(t_settle)
    print('Taking image...')
    camera_object.Expose(exptime, 1, filter_id)
    while not camera_object.ImageReady:
        time.sleep(0.1)
    print('Image ready...')
    saved = camera_object.SaveImage(image_path)
    if not saved:
        print('ERROR: {} not saved, exiting!'.format(image_path))
        sys.exit(1)
    else:
        print('{} saved...'.format(image_path))

def pulseGuide(scope, direction, duration):
    """
    Move the telescope along a given direction
    for the specified amount of time
    """
    scope.PulseGuide(direction, duration)
    while scope.IsPulseGuiding == 'True':
        time.sleep(0.1)

def determineShiftDirectionMagnitude(shft):
    """
    Take a donuts shift object and work out
    the direction of the shift and the distance
    """
    sx = shft.x.value
    sy = shft.y.value
    if abs(sx) > abs(sy):
        if sx > 0:
            direction = '-x'
        else:
            direction = '+x'
        magnitude = abs(sx)
    else:
        if sy > 0:
            direction = '-y'
        else:
            direction = '+y'
        magnitude = abs(sy)
    return direction, magnitude

def newFilename(data_dir, direction, pulse_time,
                image_id, IMAGE_EXTENSION):
    """
    Generate new FITS image name
    """
    fname = "{}\\step_{:03d}_d{}_{}ms{}".format(data_dir, image_id, direction,
                                                pulse_time, IMAGE_EXTENSION)
    image_id += 1
    return fname, image_id

if __name__ == "__main__":
    args = argParse()
    if args.instrument == 'io':
        from speculoos_io import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'callisto':
        from speculoos_callisto import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'europa':
        from speculoos_europa import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'ganymede':
        from speculoos_ganymede import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'saintex':
        from saintex import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'artemis':
        from speculoos_artemis import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'nites':
        from nites import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    elif args.instrument == 'rcos20':
        from rcos20 import (
            BASE_DIR,
            IMAGE_EXTENSION
            )
    else:
        sys.exit(1)
    # set up objects to hold calib info
    DIRECTION_STORE = defaultdict(list)
    SCALE_STORE = defaultdict(list)
    data_dir = "{}\\donuts_calibration".format(BASE_DIR)
    image_id = 0
    # connect to hardware
    myScope, SCOPE_READY = connectTelescope()
    myCamera, CAMERA_READY = connectCamera()
    # start the calibration run
    print("Starting calibration run...")
    ref_image, image_id = newFilename(data_dir, 'R', 0, image_id, IMAGE_EXTENSION)
    takeImageWithMaxIm(myCamera, ref_image)
    # set up donuts with this reference point. Assume default params for now
    donuts_ref = Donuts(ref_image)
    # loop over 10 cycles of the U, D, L, R nudging to determine
    # the scale and orientation of the camera
    for i in range(10):
        # loop pver 4 directions, 0 to 3
        for j in range(4):
            pulseGuide(myScope, j, args.pulse_time)
            check, image_id = newFilename(data_dir, j, args.pulse_time,
                                          image_id, IMAGE_EXTENSION)
            # rcos20 seems to return not guiding before it's actually stopped.
            # adding small delay for now
            if args.instrument == 'rcos20':
                time.sleep(5)
            takeImageWithMaxIm(myCamera, check)
            shift = donuts_ref.measure_shift(check)
            direction, magnitude = determineShiftDirectionMagnitude(shift)
            DIRECTION_STORE[j].append(direction)
            SCALE_STORE[j].append(magnitude)
            donuts_ref = Donuts(check)
    # now do some analysis on the run from above
    # check that the directions are the same every time for each orientation
    for direc in DIRECTION_STORE:
        print(DIRECTION_STORE[direc])
        assert len(set(DIRECTION_STORE[direc])) == 1
        print('{}: {}'.format(direc, DIRECTION_STORE[direc][0]))
    # now work out the ms/pix scales from the calbration run above
    for direc in SCALE_STORE:
        print('{}: {:.2f} ms/pixel'.format(direc,
                                           args.pulse_time/np.average(SCALE_STORE[direc])))
