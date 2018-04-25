"""
Code to start and stop the donuts second thread
"""
import os
import sys
import argparse as ap
from datetime import datetime

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
    test_dir = "C:\\donutstests"
    if not os.path.exists(test_dir):
        os.mkdir(test_dir)
    tnow = datetime.utcnow().isoformat()
    if args.action == 'start':
        os.system('type nul >> {}\\start_{}.txt'.format(test_dir, tnow))
        sys.exit(0)
    elif args.action == 'stop':
        os.system('type nul >> {}\\stop_{}.txt'.format(test_dir, tnow))
        sys.exit(0)
    else:
        print('Unknown input, exiting')
        sys.exit(1)
