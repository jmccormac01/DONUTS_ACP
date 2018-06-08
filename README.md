# ACP Autoguiding with DONUTS

Autoguiding ACP driven telescopes using DONUTS

# Setup

Clone this repository to the TCS

```sh
$> mkdir /path/to/ag/code/home
$> cd /path/to/ag/code/home
$> git clone https://github.com/jmccormac01/DONUTS_ACP.git
```

Add and configure an instrument specific configuration file. Use the ```nites``` or ```speculoos``` instrument files as examples. For example:

```
"""
Confiuguration parameters for NITES
"""
# e.g. .fits or .fit etc
IMAGE_EXTENSION = "*.fts"

# header keyword for the current filter
FILTER_KEYWORD = 'FILTER'

# header keyword for the current target/field
FIELD_KEYWORD = 'OBJECT'

# RA axis alignment along x or y?
RA_AXIS = 'y'

# imager position angle
CAMERA_ANGLE = 0.0

# guider log file name
LOGFILE = "guider.log"

# rejection buffer length
GUIDE_BUFFER_LENGTH = 20

# number images allowed during pull in period
IMAGES_TO_STABILISE = 10

# outlier rejection sigma
SIGMA_BUFFER = 5

# pulseGuide conversions
PIX2TIME = {'+x': 100.00,
            '-x': 100.00,
            '+y': 100.00,
            '-y': 100.00}

# guide directions
DIRECTIONS = {'+y': 0, '-y': 1, '+x': 2, '-x': 3}

# max allowed shift to correct
MAX_ERROR_PIXELS = 20

# max alloed shift to correct during stabilisation
MAX_ERROR_STABIL_PIXELS = 40

# ACP data base directory
BASE_DIR = "C:\\data"
AUTOGUIDER_REF_DIR = "C:\\data\\autoguider_ref"

# PID loop coefficients
PID_COEFFS = {'x': {'p': 1.0, 'i': 0.5, 'd': 0.0},
              'y': {'p': 1.0, 'i': 0.5, 'd': 0.0},
              'set_x': 0.0,
              'set_y': 0.0}

# database set up
DB_HOST = "localhost"
DB_USER = "nites"
DB_DATABASE = "nites_ops"
DB_PASS = "nites"

# observatory location for sun calculations
OLAT = 28.+(40./60.)+(00./3600.)
OLON = -17.-(52./60.)-(00./3600.)
ELEV = 2326.
```

# Summary

The DONUTS package consists of several components:

**Operations:**
   1. A modified version of the ACP ```UserActions.wsc``` file. This is used to trigger autoguiding from ACP plans
   1. A daemon script ```donuts_process_handler.py```. This code runs all the time listening for commands from ACP to start and stop the guiding. The commands are triggered by the custom ```UserActions.wsc``` script above
   1. A shim ```donuts_process.py```, which ```UserActions.wsc``` calls to insert jobs into the daemon using Pyro. The ```donuts_process.py``` script can also be used to manually start and stop guiding if required (in an emergency for example)
   1. The DONUTS main autoguiding code ```acp_ag.py```. This script does all the shift measuring and telescope movements
   1. A per instrument configuration file, e.g.: ```nites.py```, ```speculoos_io.py``` etc. This file contains information such as field orientation and header keyword maps.

**Admin:**
   1. A script to calibrate the autoguiding pulseGuide command, ```calibrate_pulse_guide.py```
   1. A script to update a field's autoguider reference image with a new one, ```setnewrefimage.py```. This is used when the old image is no longer suitable and you have a new image on disc that you would like to use.
   1. A script to stop field's current autoguider reference image, ```stopcurrentrefimage.py```. This is used to remove a referene frame and let DONUTS make a new one automatically next time it observes that field.

# Usage for each component


# Schematic

![Schematic](notes/DONUTS_AG_v3.png)

# Contributors

James McCormac

# License

MIT
