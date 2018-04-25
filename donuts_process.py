"""
Code to start and stop the donuts second thread
"""
import sys
import argparse as ap
import Pyro4

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
    ag = Pyro4.Proxy('PYRO:donuts@localhost:9234')
    if args.action == 'start':
        ag.start_ag()
        sys.exit(0)
    elif args.action == 'stop':
        ag.stop_ag()
        sys.exit(0)
    else:
        print('Unknown input, exiting')
        sys.exit(1)
