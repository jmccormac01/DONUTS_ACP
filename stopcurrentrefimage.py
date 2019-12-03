"""
Script to disable the current reference image for a given field.
Use this is you want donuts to make a new reference automatically

   1. First check for current referene image for this field
   1. If there is one:
      1. Update that row with valid_until as now
      1. Move the image to the autoguider_ref/old folder
   1. Else, do nothing
"""
import os
import sys
import argparse as ap
from shutil import move
from datetime import datetime
import pymysql

# pylint: disable=invalid-name
# pylint: disable=wildcard-import
# pylint: disable=unused-import

def argParse():
    """
    Parse the command line arguments

    Parameters
    ----------
    None

    Returns
    -------
    args : argparse object
        Contains the command line arguments

    Raises
    ------
    None
    """
    p = ap.ArgumentParser()
    p.add_argument('field',
                   help='Name of field')
    p.add_argument('telescope',
                   help='Name of telescope',
                   choices=['io', 'callisto', 'europa',
                            'ganymede', 'artemis', 'saintex',
                            'nites', 'rcos20'])
    p.add_argument('filt',
                   help='Name of filter')
    return p.parse_args()

def tnow():
    """
    Return an iso formatted string for the current UTC time

    Parameters
    ----------
    None

    Returns
    -------
    utcnow : string
        The current UTC time string in iso format

    Raises
    ------
    None
    """
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def moveImage(image, dest):
    """
    Move a file image to dest

    Parameters
    ----------
    image : string
        Name of the file to move
    dest : string
        Path to move the file to

    Returns
    -------
    None

    Raises
    ------
    None
    """
    if not os.path.exists(dest):
        os.mkdir(dest)
    move(image, dest)

def disableRefImage(ref_id, field, telescope, ref_image, filt):
    """
    Set the valid until time for a given reference image as utcnow.
    Doing so invalidates it for use.

    Parameters
    ----------
    ref_id : int
        Unique integer asigned to each reference image on creation, primary key
    field : string
        Name of the field that the reference image is from
    telescope : string
        Name of the telescope used to take the reference image
    ref_image : string
        Name of the reference image to disable
    filt : string
        Name of the filter used to the take the reference image

    Returns
    -------
    None

    Raises
    ------
    None
    """
    qry_args = (tnow(), ref_id, field, telescope, ref_image, filt, )
    qry = """
        UPDATE autoguider_ref
        SET valid_until=%s
        WHERE ref_id=%s
        AND field=%s
        AND telescope=%s
        AND ref_image=%s
        AND filter=%s
        """
    with pymysql.connect(host=DB_HOST, db=DB_DATABASE,
                         user=DB_USER, password=DB_PASS) as cur:
        cur.execute(qry, qry_args)

def checkForPreviousRefImage(field, telescope, filt):
    """
    Look in the database to see if we have a reference image for
    this particular field, telescope and filter combination

    If a previous image is found, the user is prompted to disable
    this file in preparation for submitting the new reference image
    in the next step.

    Parameters
    ----------
    field : string
        Name of the field that the reference image is from
    telescope : string
        Name of the telescope used to take the reference image
    filt : string
        Name of the filter used to the take the reference image

    Returns
    -------
    None

    Raises
    ------
    None
    """
    qry_args = (field, telescope, filt, tnow(), )
    qry = """
        SELECT
        ref_id, field, telescope, ref_image, filter,
        valid_from, valid_until
        FROM autoguider_ref
        WHERE field=%s
        AND telescope=%s
        AND filter=%s
        AND valid_from<%s
        AND valid_until IS NULL
        """
    with pymysql.connect(host=DB_HOST, db=DB_DATABASE,
                         user=DB_USER, password=DB_PASS) as cur:
        cur.execute(qry, qry_args)
        results = cur.fetchall()
    if results:
        if len(results) > 1:
            print('ERROR: multiple active reference images for field {}'.format(field))
            for row in results:
                print(row)
            print('Resolve this issue manually! Quitting.')
            sys.exit(1)
        else:
            print('Found currently active reference image:')
            print(results)
            yn = input('Disable this image? (y | n): ')
            if yn.lower() == 'y':
                o_ref_id = results[0][0]
                o_field = results[0][1]
                o_telescope = results[0][2]
                o_ref_image = results[0][3]
                o_filt = results[0][4]
                disableRefImage(o_ref_id, o_field, o_telescope,
                                o_ref_image, o_filt)
                o_ref_loc = "{}\\{}".format(AUTOGUIDER_REF_DIR, o_ref_image)
                o_ref_loc_new = "{}\\old\\".format(AUTOGUIDER_REF_DIR)
                print('Moving {} --> {}'.format(o_ref_loc, o_ref_loc_new))
                moveImage(o_ref_loc, o_ref_loc_new)
            else:
                print('Aborting update. Quitting.')
                sys.exit(1)
    else:
        print('No previous reference image found for {} {} {}'.format(field,
                                                                      telescope,
                                                                      filt))

if __name__ == "__main__":
    args = argParse()
    if args.telescope == 'nites':
        from nites import *
    elif args.telescope == 'io':
        from speculoos_io import *
    elif args.telescope == 'callisto':
        from speculoos_callisto import *
    elif args.telescope == 'europa':
        from speculoos_europa import *
    elif args.telescope == 'ganymede':
        from speculoos_ganymede import *
    elif args.telescope == 'artemis':
        from speculoos_artemis import *
    elif args.telescope == 'saintex':
        from saintex import *
    elif args.telescope == 'rcos20':
        from rcos20 import *
    else:
        sys.exit(1)
    checkForPreviousRefImage(args.field, args.telescope, args.filt)
    print('Remember to restart Donuts guiding job after disabling reference images!')
