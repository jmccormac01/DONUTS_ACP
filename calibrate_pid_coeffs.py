"""
Automated calibration of the AG PID coefficients

Plan:
    1. Take a series of 100 x 10s images with range of P=0.4,0.6,0.8,1.0 and fixed I=0.15
    1. Autoguide as normal and measure stats over 100 images
    1. Repeat steps above for different Is = 0.30, 0.45
    1. Determine which PI gives the best response

    Ideally we'd track the same Alt-Az sweep each time, but this
    might be an issue if certain fields contain less stars etc.
    Try first by tracking the same field over each 6h run

Observing plans:
    1. Make a plan with 100x10s images of target 3h east of meridian on equator
    1. Call object P0.40-I0.15-D0.00 (then scale coeffs in name as we go)
    1. Repeat block keeping the coords the same but changing the field name
    1. Call the next objects P0.60-I0.15-D0.00, P0.80-I0.15-D0.00, etc.
    1. The changing field name witll force a new ag reference image to split the blocks
    1. Run some stats over the block and determine the RMS in the guiding
    1. Plot the RMS vs P and determine the best value (expect a parabola?)
"""
import argparse as ap
import numpy as np
from donuts import Donuts
from PID import PID
from acp_ag import waitForImage
import ephem

# autoguider status flags
ag_timeout, ag_new_start, ag_new_field, ag_new_filter, ag_no_change = range(5)

# obser24tory value
LAT = -28. - 36./60. - 56./3600.
LON = -70. - 23./60. - 51./3600.
ELEV = 2535.
obs = ephem.Observer()
obs.lon = str(LON)
obs.lat = str(LAT)
obs.elev = ELEV

def argParse():
    """
    Parse the commmand line arguments
    """
    p = ap.ArgumentParser()
    p.add_argument('action',
                   help='generate the plans for tonight',
                   choices=['plan', 'analyse'],
                   action='store_true')
    parser.add_argument('night',
                        help='night of plan')
    return p.parse_args()

def getSunTimes(tn, horizon='-16'):
    """
    Return the times of dawn and dusk twilights for a given night
    """
    obs.horizon = horizon
    obs.date = tn
    end_dusk_twi = obs.next_setting(ephem.Sun(), use_center=True)
    start_dawn_twi = obs.next_rising(ephem.Sun(), use_center=True)
    return end_dusk_twi, start_dawn_twi

def splitObjectIdIntoPidCoeffs(object_id):
    """
    Take the object name and pull out the coeff values
    """
    p, i, d = object_id.split('-')
    p = round(float(p[1:]), 2)
    i = round(float(i[1:]), 2)
    d = round(float(d[1:]), 2)
    return p, i, d

if __name__ == "__main__":
    args = argParse()
    if args.action == 'plan':
        plan_dir = "C:\\Users\\speculoos\\Documents"
        # set up the date for twilights etc
        args.night = args.night.replace("-", "")
        tn_start = datetime.strptime((args.night + "T12:00:00"), "%Y%m%dT%H:%M:%S")
        tstart = getSunTimes(tn_start, horizon='-16')
        obs.date = tstart + 3*ephem.hour
        lst_for_ra = math.degrees(obs.sidereal_time())
        print(lst_for_ra)

    if args.action == 'analyse':
        print("Checking for the telescope...")
        myScope = win32com.client.Dispatch("ACP.Telescope")

        # get the data directory
        data_loc = getDataDir(0)

        # dictionaries to hold reference images for different fields/filters
        ref_track = defaultdict(dict)

        # make range of P values to check, this must match the plan names
        P = np.arange(0.5, 1.6, 0.1)
        for p in P:
            # initialise the PID controllers for X and Y
            PIDx = PID(p, 0, 0)
            PIDy = PID(p, 0, 0)
            PIDx.setPoint(0)
            PIDy.setPoint(0)
