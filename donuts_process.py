"""
Code to start and stop the donuts second thread
"""
import sys
import argparse as ap
import Pyro4
from utils import ag_status

# pylint: disable=invalid-name

def argParse():
    """
    Parse the command line arguments
    """
    p = ap.ArgumentParser()
    p.add_argument('action',
                   help='start | stop the donuts process',
                   choices=['start', 'stop'])
    return p.parse_args()

if __name__ == "__main__":
    args = argParse()
    try:
        ag = Pyro4.Proxy('PYRO:donuts@localhost:9234')
    except Pyro4.errors.CommunicationError:
        sys.exit(ag_status.pyro_connection_error)
    if args.action == 'start':
        status = ag.start_ag()
        sys.exit(status)
    elif args.action == 'stop':
        status = ag.stop_ag()
        sys.exit(status)
    else:
        sys.exit(ag_status.unknown)
