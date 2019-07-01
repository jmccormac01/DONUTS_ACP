"""
Code to start and stop the donuts second thread
"""
import sys
import argparse as ap
import Pyro4
from utils import (
    ag_status,
    log_debug
    )

# pylint: disable=invalid-name

def arg_parse():
    """
    Parse the command line arguments
    """
    p = ap.ArgumentParser()
    p.add_argument('action',
                   help='\'start\' | \'stop\' the donuts process (or \'shutdown\' donuts process handler)',
                   choices=['start', 'stop', 'shutdown'])
    p.add_argument('--nodebug',
                   help='Enable debugging mode',
                   action='store_true')
    return p.parse_args()

if __name__ == "__main__":
    args = arg_parse()
    # do some debug logging
    if args.nodebug:
        log_debug(args)
    try:
        ag = Pyro4.Proxy('PYRO:donuts@localhost:9234')
    except (Pyro4.errors.CommunicationError, ConnectionRefusedError):
        if args.nodebug:
            log_debug("Pyro communications error, exiting with status = {}".format(ag_status.pyro_connection_error))
        ag = None
        sys.exit(ag_status.pyro_connection_error)
    if args.action == 'start' and ag:
        status = ag.start_ag()
        if args.nodebug:
            log_debug("AG start called, returning status = {}".format(status))
        sys.exit(status)
    elif args.action == 'stop' and ag:
        status = ag.stop_ag()
        if args.nodebug:
            log_debug("AG stop called, returning status = {}".format(status))
        sys.exit(status)
    elif args.action == 'shutdown' and ag:
        ag_stopped, ag_shutdown = ag.shutdown()
        if args.nodebug:
            log_debug("AG shutdown called: ")
            log_debug("\t AG stop returned status = {}".format(ag_stopped))
            log_debug("\t AG shutdown returned status = {}".format(ag_shutdown))
    else:
        status = ag_status.unknown
        if args.nodebug:
            log_debug("Unknown request, returning status = {}".format(status))
        sys.exit(status)
