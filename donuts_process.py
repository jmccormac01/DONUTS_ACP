"""
Code to start and stop the donuts second thread
"""
import os
import sys
import argparse as ap

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
    if args.action == 'start':
        os.mkdir('C:\\testdirstart')
    elif args.action == 'stop':
        os.mkdir('C:\\testdirstop')
    else:
        print('Unknown input, exiting')
        sys.exit(1)
