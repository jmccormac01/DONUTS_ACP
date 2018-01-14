"""
Confiuguration parameters for SPECULOOS
"""
# e.g. .fits or .fit etc
IMAGE_EXTENSION = ".fts"

# header keyword for the current filter
FILTER_KEYWORD = 'FILTER'

# header keyword for the current target/field
FIELD_KEYWORD = 'OBJECT'

# RA axis alignment along x or y?
RA_AXIS = 'x'

# guider log file name
LOGFILE = "guider.log"

# rejection buffer length
GUIDE_BUFFER_LENGTH = 20

# outlier rejection sigma
SIGMA_BUFFER = 5

# wait time (s)
WAITTIME = 21600

# pulseGuide conversions
PIX2TIME = {'+x': 69.10,
            '-x': 69.11,
            '+y': 69.15,
            '-y': 69.27}

# guide directions
DIRECTIONS = {'-y': 0, '+y': 1, '+x': 2, '-x': 3}

# max allowed shift to correct
MAX_ERROR_PIXELS = 20

# ACP data base directory
BASE_DIR = "C:\\Users\\speculoos\\Documents\\ACP Astronomy\\Images"

# PID loop coefficients
PID_COEFFS = {'x': {'p': 0.9, 'i': 0.0, 'd': 0.0},
              'y': {'p': 0.9, 'i': 0.0, 'd': 0.0},
              'set_x': 0.0,
              'set_y': 0.0}
