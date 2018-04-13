"""
Script to measure the RMS of a given field using the database
"""
from collections import (
    defaultdict,
    OrderedDict
    )
import matplotlib.pyplot as plt
import numpy as np
import pymysql

# pylint: disable=invalid-name

def getUniqueObjectIds():
    """
    """
    qry = """
        SELECT
        distinct(field)
        FROM autoguider_ref
        """
    with pymysql.connect(host='localhost', db='spec_ops',
                         user='speculoos', password='spec_ops') as cur:
        cur.execute(qry)
        results = cur.fetchall()
    object_ids = []
    for row in results:
        object_ids.append(row[0])
    return object_ids

def getReferenceImagesForField(field):
    """
    """
    qry = """
        SELECT
        ref_image, filter
        FROM autoguider_ref
        WHERE field=%s
        """
    qry_args = (field, )
    with pymysql.connect(host='localhost', db='spec_ops',
                         user='speculoos', password='spec_ops') as cur:
        cur.execute(qry, qry_args)
        results = cur.fetchall()
    ref_filts = {row[0]: row[1] for row in results}
    return ref_filts

def getAgStats(ref_image):
    """
    """
    qry = """
        SELECT
        solution_x, solution_y
        FROM autoguider_log
        WHERE reference=%s
        """
    qry_args = (ref_image, )
    with pymysql.connect(host='localhost', db='spec_ops',
                         user='speculoos', password='spec_ops') as cur:
        cur.execute(qry, qry_args)
        results = cur.fetchall()
    return results

if __name__ == "__main__":
    object_ids = getUniqueObjectIds()
    x = OrderedDict()
    y = OrderedDict()
    for object_id in object_ids:
        x[object_id] = defaultdict(list)
        y[object_id] = defaultdict(list)
        ref_filts = getReferenceImagesForField(object_id)
        for ref in ref_filts:
            stats = getAgStats(ref, ref_filts[ref])
            for i, row in enumerate(stats):
                # skip the first 10
                if i >= 10:
                    x[object_id][ref_filts[ref]].append()
                    y[object_id][ref_filts[ref]].append()
