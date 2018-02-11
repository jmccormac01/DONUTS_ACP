"""
Automated calibration of the AG PID coefficients

Plan:
    1. Take a series of 50 x 20s images with P = 0.1
    1. Autoguide as normal and measure stats over 100 images
    1. Repeat steps above for P = 0.5 to 1.5 with dP = 0.1
    1. Determine which P gives the best response

    Ideally we'd track the same Alt-Az sweep each time, but this
    might be an issue if certain fields contain less stars etc.
    Try first by tracking the same field.

    Once P is determined, try then adding small amounts of I
    in steps of dI = 0.1, while keeping P fixed.

    Finally, when a suitable P and I are found, maybe try adding
    some D. For a responsive system we should not need much/any D.

Observing plans:
    1. Make a plan with 50x20s images of target 2h east of meridian on equator
    1. Call object P0_5-I0-D0
    1. Repeat block keeping the coords the same but changing the field name
    1. Call the next objects P0_6-I0-D0, P0_7-I0-D0, etc.
    1. The changing field name witll force a new ag referene image to split the blocks
    1. Run some stats over the block and determine the RMS in the guiding
    1. Plot the RMS vs P and determine the best value (expect a parabola?)
"""
import numpy as np
from donuts import Donuts
from PID import PID
from acp_ag import waitForImage

# autoguider status flags
ag_timeout, ag_new_start, ag_new_field, ag_new_filter, ag_no_change = range(5)

if __name__ == "__main__":
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
