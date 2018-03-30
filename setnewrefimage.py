"""
Script to create a new reference image for a given field

   1. First check for current referene image for this field
   1. If there is one:
      1. Update that row with valid_until as now
      1. Move the image to the autoguider_ref/old folder
   1. Add the new image to the table
   1. Copy the new image to the autoguider_ref folder
"""
import os
import sys
import argparse as ap
from shutil import (
    copyfile,
    move
    )
from datetime import datetime
import pymysql

# pylint: disable=invalid-name
# pylint: disable=wildcard-import
# pylint: disable=unused-import

# TODO: check if names or paths in table
# TODO: update new db schema
# TODO: copy old table over
# TODO: test adding new fields manually
# TODO: Fix restarting donuts during the day
# TODO: Is donuts building up the telescope offset over time?

def argParse():
    """
    """
    p = ap.ArgumentParser()
    p.add_argument('ref_image',
                   help='Name of new reference image')
    p.add_argument('field',
                   help='Name of field')
    p.add_argument('telescope',
                   help='Name of telescope',
                   choices=['io', 'callisto', 'europa',
                            'ganymede', 'nites'])
    p.add_argument('filt',
                   help='Name of filter')
    return p.parse_args()

def tnow():
    """
    """
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

def moveImage(image, dest):
    """
    """
    if not os.path.exists(dest):
        os.mkdir(dest)
    move(image, dest)

def copyImage(image, dest):
    """
    """
    if not os.path.exists(dest):
        os.mkdir(dest)
    copyfile(image, "{}/{}".format(dest, image))

def disableRefImage(ref_id, field, telescope, ref_image, filt):
    """
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
            yn = input('Replace this image? (y | n): ')
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
def addNewRefImage(ref_image, field, telescope, filt):
    """
    """
    print('Adding new ref_image to database')
    qry_args = (field, telescope, ref_image, filt, tnow())
    qry = """
        INSERT INTO autoguider_ref
        (field, telescope, ref_image, filter, valid_from)
        VALUES
        (%s, %s, %s, %s, %s)
        """
    with pymysql.connect(host=DB_HOST, db=DB_DATABASE,
                         user=DB_USER, password=DB_PASS) as cur:
        cur.execute(qry, qry_args)
    print('Copying {} --> {}'.format(ref_image, AUTOGUIDER_REF_DIR))
    copyImage(ref_image, AUTOGUIDER_REF_DIR)


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
    else:
        sys.exit(1)
    checkForPreviousRefImage(args.field, args.telescope, args.filt)
    addNewRefImage(args.ref_image, args.field, args.telescope, args.filt)
    print('Remember to restart Donuts after applying new reference images!')
