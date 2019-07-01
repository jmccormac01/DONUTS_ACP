"""
Some useful utilities for donuts
"""
from datetime import datetime

class ag_status:
    """
    Class to hold status flags
    """
    success, failed, unknown, pyro_connection_error, already_running = range(5)

def log_debug(message):
    """
    log all output to a file for inspection
    """
    location = "C:\\donuts_debugging.txt"
    with open(location, 'a') as dlf:
        dlf.write('{} {}\n'.format(datetime.utcnow(), message))
