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
import win32com.client
from donuts import Donuts

# pylint: disable=invalid-name

def argParse():
    """
    Parse command line arguments
    """
    p = ap.ArgumentParser()
    return p.parse_args()

def takeImageWithMaxIm(exptime=10, outdir=""):
    """
    Take an image with MaxImDL
    """
    print('Taking image...')
    pass

def pulseGuide(scope, direction, duration):
    """
    Move the telescope along a given direction
    for the specified amount of time
    """
    scope.PulseGuide(direction, duration)
    while scope.IsPulseGuiding == 'True':
        time.sleep(0.1)

if __name__ == "__main__":
    print("Connecting to telescope...")
    myScope = win32com.client.Dispatch("ACP.Telescope")
    print("Connecting to camera...")
    myCamera = win32com.client.Dispatch("MaxIm.CCDCamera")
    try:
        myCamera.LinkEnabled = True
        myCamera.DisableAutoShutdown = True
    except AttributeError:
        print('WARNING: CANNOT CONNECT TO CAMERA')
        sys.exit(1)

    print("Starting calibration run...")
    takeImageWithMaxIm()
    # get image name and make it the reference
    # donuts_ref = Donuts(ref_image)
    for i in range(10):
        pulseGuide(myScope, 0, 2000)
        takeImageWithMaxIm()
        # work out shift
        pulseGuide(myScope, 1, 2000)
        takeImageWithMaxIm()
        # work out shift
        pulseGuide(myScope, 2, 2000)
        takeImageWithMaxIm()
        # work out shift
        pulseGuide(myScope, 3, 2000)
        takeImageWithMaxIm()
        # work out shift
        # TODO: Store all shifts
    # TODO: Work out the direction and average conversions




