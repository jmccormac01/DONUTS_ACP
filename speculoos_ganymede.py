"""
Confiuguration parameters for SPECULOOS Ganymede
"""
# e.g. .fits or .fit etc
IMAGE_EXTENSION = ".fts"

# header keyword for the current filter
FILTER_KEYWORD = 'FILTER'

# header keyword for the current target/field
FIELD_KEYWORD = 'OBJECT'

# RA axis alignment along x or y?
RA_AXIS = 'x'

# imager position angle
CAMERA_ANGLE = 1.2

# guider log file name
LOGFILE = "guider.log"

# rejection buffer length
GUIDE_BUFFER_LENGTH = 20

# number images allowed during pull in period
IMAGES_TO_STABILISE = 10

# outlier rejection sigma
SIGMA_BUFFER = 10

# pulseGuide conversions
# Equatorial fork = EQFK
# German equatorial = GEM
MOUNT_TYPE = "EQFK"
PIER_SIDE_KEYWORD = ""
PIX2TIME = {'+x': 68.44,
            '-x': 69.21,
            '+y': 69.21,
            '-y': 69.44}

# guide directions
DIRECTIONS = {'-y': 0, '+y': 1, '+x': 2, '-x': 3}

# max allowed shift to correct
MAX_ERROR_PIXELS = 20

# max alloed shift to correct during stabilisation
MAX_ERROR_STABIL_PIXELS = 40

# ACP data base directory
BASE_DIR = "C:\\Users\\speculoos\\Documents\\ACP Astronomy\\Images"
DATA_SUBDIR = ""
AUTOGUIDER_REF_DIR = "C:\\Users\\speculoos\\Documents\\ACP Astronomy\\Images\\autoguider_ref"
PYTHONPATH = "C:\\ProgramData\\Miniconda3\\python.exe"
DONUTSPATH = "C:\\Users\\speculoos\\Documents\\GitHub\\DONUTS_ACP"

# PID loop coefficients
PID_COEFFS = {'x': {'p': 0.70, 'i': 0.02, 'd': 0.0},
              'y': {'p': 0.50, 'i': 0.02, 'd': 0.0},
              'set_x': 0.0,
              'set_y': 0.0}

# database set up
DB_HOST = "localhost"
DB_USER = "speculoos"
DB_DATABASE = "spec_ops"
DB_PASS = 'spec_ops'

# observatory location for sun calculations
OLAT = -24.-(37./60.)-(38./3600.)
OLON = -70.-(24./60.)-(15./3600.)
ELEV = 2418.

# set the limit where donuts will shut off automatically
SUNALT_LIMIT = 0
