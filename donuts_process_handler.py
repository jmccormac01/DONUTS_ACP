"""
Process handler for ACP to control Donuts

This code should be started when the control machine is booted.
It will run all the time anspawn AG processes when requested.
If this code is not running, the AG requests will not be met
and the ACP plans will continue with no guiding.


Pyro4 URI = PYRO:donuts@localhost:9234
"""
import os
import sys
import time
import signal
import threading
import argparse as ap
import subprocess as sp
import psutil
import Pyro4
import pymysql
from utils import ag_status

# pylint: disable=invalid-name
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import

AG_ON_TIME = 10
AG_OFF_TIME = 30

def argParse():
    """
    Parse the command line args

    Parameters
    ----------
    None

    Returns
    -------
    args : argparse object
        Object containing command line arguments

    Raises
    ------
    None
    """
    p = ap.ArgumentParser()
    p.add_argument('instrument',
                   help='select an instrument',
                   choices=['io', 'callisto', 'europa',
                            'ganymede', 'saintex',
                            'artemis', 'nites', 'rcos20'])
    return p.parse_args()

class Autoguider(object):
    """
    Autoguider class

    Parameters
    ----------
    instrument : string
        Name of the telescope we are guiding on
    pyro_uri : string
        URI on which to find the Pryo connection
    daemon : Pyro4.daemon
        Instance of the Pyro4 daemon. This is used
        to shutdown the request loop cleanly

    Returns
    -------
    ag_status : int
        Status of the autoguiding after various interactions

    Raises
    ------
    None
    """
    def __init__(self, instrument, db_info, donuts_info, pyro_uri, daemon):
        """
        Initialise the class

        See class docstring above
        """
        self.guiding = False
        self.proc = None
        self.instrument = instrument
        self.db_host = db_info['host']
        self.db_user = db_info['user']
        self.db_database = db_info['database']
        self.db_password = db_info['password']
        self.python_path = donuts_info['python_path']
        self.donuts_path = donuts_info['donuts_path']
        self.pyro_uri = pyro_uri
        self.daemon = daemon
        self.print_thread = threading.Thread(target=self.printStatus)
        self.print_thread.daemon = True
        self.print_thread.start()

    def printStatus(self):
        """
        Display current status. This method is looped in the
        Pyro4 request loop, displaying the current status of
        the guiding system

        Parameters
        ----------
        self : the class self object

        Returns
        -------
        None

        Raises
        ------
        None
        """
        while True:
            # clear screen
            os.system('cls')
            # print header
            print(self.pyro_uri)
            if self.guiding and self.proc:
                print('\n[PID: {}]: Autoguiding = {}'.format(self.proc.pid, self.guiding))
                self.printLastAgCorrection()
                time.sleep(AG_ON_TIME)
            else:
                print('\n[PID: ----]: Autoguiding = {}'.format(self.guiding))
                time.sleep(AG_OFF_TIME)

    def printLastAgCorrection(self):
        """
        Grab the last autoguider correction and recent info messages

        Parameters
        ----------
        self : the class self object

        Returns
        -------
        None

        Raises
        ------
        None

        """
        qry = """
            SELECT *
            FROM autoguider_log_new
            ORDER BY updated DESC
            LIMIT 1
            """
        with pymysql.connect(host=self.db_host,
                             db=self.db_database,
                             user=self.db_user,
                             password=self.db_password,
                             cursorclass=pymysql.cursors.DictCursor) as cur:
            cur.execute(qry)
            result = cur.fetchone()
        if result:
            print('[{}]: {}:'.format(result['updated'],
                                     result['comparison']))
            print('\tShifts: X: {:.3f} Y: {:.3f}'.format(result['shift_x'],
                                                         result['shift_y']))
            print('\tPrePID: X: {:.3f} Y: {:.3f}'.format(result['pre_pid_x'],
                                                         result['pre_pid_y']))
            print('\tPostPID: X: {:.3f} Y: {:.3f}'.format(result['post_pid_x'],
                                                          result['post_pid_y']))
        else:
            print('No shifts in database')

        print('\nRecent messages:')
        qry2 = """
            SELECT * FROM autoguider_info_log
            ORDER BY message_id DESC
            LIMIT 10
            """
        with pymysql.connect(host=self.db_host,
                             db=self.db_database,
                             user=self.db_user,
                             password=self.db_password,
                             cursorclass=pymysql.cursors.DictCursor) as cur:
            cur.execute(qry2)
            results = cur.fetchall()
        for row in results:
            print("[{}]: {}".format(row['updated'],
                                    row['message']))

    @Pyro4.expose
    def start_ag(self):
        """
        Exposed method to trigger donuts guiding

        Parameters
        ----------
        self : the class self object

        Returns
        -------
        ag_status : int
            Status of the autoguider after triggering

        Raises
        ------
        None
        """
        if self.proc is None:
            cmd = "{} {}\\acp_ag.py {}".format(self.python_path, self.donuts_path, self.instrument)
            self.proc = sp.Popen(cmd, stdout=sp.PIPE, shell=False, creationflags=sp.CREATE_NEW_PROCESS_GROUP)
            # poll = None means running
            if self.proc.poll() is None:
                self.guiding = True
                print(self.proc.pid)
                return ag_status.success
            elif self.proc.poll() == 0:
                self.guiding = False
                return ag_status.failed
            else:
                self.guiding = False
                return ag_status.unknown
        else:
            print('Already a guiding process running, cannot run 2, skipping!')
            return ag_status.already_running

    @Pyro4.expose
    def stop_ag(self):
        """
        Exposed method to stop donuts guiding

        Parameters
        ----------
        self : the class self object

        Returns
        -------
        ag_status : int
            Status of the autoguider stop request

        Raises
        ------
        None
        """
        if self.proc:
            if self.proc.poll() is None:
                guiding_pid = int(self.proc.pid)
                print('Killing AG script pid={}'.format(self.proc.pid))
                os.kill(self.proc.pid, signal.CTRL_BREAK_EVENT)
                time.sleep(5)
                # get running python processes - check it is dead
                pyproc = [int(p.pid) for p in psutil.process_iter() if 'python' in p.name()]
                if guiding_pid not in pyproc:
                    self.guiding = False
                    self.proc = None
                    return ag_status.success
                else:
                    print('Guiding process {} not dead!'.format(guiding_pid))
                    self.guiding = True
                    return ag_status.failed
        else:
            print('No process to kill')
            return ag_status.success

    @Pyro4.expose
    #@Pyro4.oneway
    def shutdown(self):
        """
        Exposed method to shutdown the donuts process handler (this script)

        Parameters
        ----------
        self : the class self object

        Returns
        -------
        None

        Raises
        ------
        None
        """
        print('Shutting down the donuts process handler...')
        # check for a guiding process, just in case
        ag_stopped = self.stop_ag()
        ag_shutdown = self.daemon.shutdown()
        return ag_stopped, ag_shutdown

if __name__ == "__main__":
    args = argParse()
    if args.instrument == 'nites':
        from nites import *
    elif args.instrument == 'io':
        from speculoos_io import *
    elif args.instrument == 'callisto':
        from speculoos_callisto import *
    elif args.instrument == 'europa':
        from speculoos_europa import *
    elif args.instrument == 'ganymede':
        from speculoos_ganymede import *
    elif args.instrument == 'saintex':
        from saintex import *
    elif args.instrument == 'artemis':
        from speculoos_artemis import *
    elif args.instrument == 'rcos20':
        from rcos20 import *
    else:
        sys.exit(1)

    # need to generate database connection info and the location
    # of python and the autoguiding code - build from imports
    db_info = {'host': DB_HOST, 'user': DB_USER,
               'database':DB_DATABASE, 'password': DB_PASS}
    donuts_info = {'python_path': PYTHONPATH,
                   'donuts_path': DONUTSPATH}

    sys.excepthook = Pyro4.util.excepthook
    daemon = Pyro4.Daemon(host='localhost', port=9234)
    ag = Autoguider(args.instrument, db_info, donuts_info,
                    'PYRO:donuts@localhost:9234', daemon)
    uri = daemon.register(ag, objectId='donuts')
    daemon.requestLoop()
    print('Exiting Donuts process handler')
    daemon.close()
    print('Daemon closed')
