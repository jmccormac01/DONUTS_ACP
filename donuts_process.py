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
                   help='\'start\' | \'stop\' the donuts process (or \'shutdown\' donuts process handler)',
                   choices=['start', 'stop', 'shutdown'])
    return p.parse_args()

if __name__ == "__main__":
    args = argParse()
    try:
        ag = Pyro4.Proxy('PYRO:donuts@localhost:9234')
    except (Pyro4.errors.CommunicationError, ConnectionRefusedError):
        sys.exit(ag_status.pyro_connection_error)
        ag = None
    if args.action == 'start' and ag:
        status = ag.start_ag()
        sys.exit(status)
    elif args.action == 'stop' and ag:
        status = ag.stop_ag()
        sys.exit(status)
    elif args.action == 'shutdown' and ag:
        ag.shutdown()
    else:
        sys.exit(ag_status.unknown)
