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
            stats = getAgStats(ref)
            for i, row in enumerate(stats):
                x[object_id][ref_filts[ref]].append(float(row[0]))
                y[object_id][ref_filts[ref]].append(float(row[1]))
    # now plot the values and do stats
    for object_id in x:
        for filt in x[object_id]:
            xx = np.array(x[object_id][filt])
            yy = np.array(y[object_id][filt])
            fig, ax = plt.subplots(1, figsize=(10, 5))
            ax.plot(xx, 'r.')
            ax.plot(yy, 'b.')
            rms_x = np.std(xx)
            rms_y = np.std(yy)

            # get stats on clipped data
            n_x = np.where((xx > -5*rms_x) & (xx < 5*rms_x))
            n_y = np.where((yy > -5*rms_y) & (yy < 5*rms_y))
            rms_x_c = np.std(xx[n_x])
            rms_y_c = np.std(yy[n_y])

            ax.legend(("RMS_x={:.3f} ({:.3f}) pix".format(rms_x, rms_x_c),
                       "RMS_y={:.3f} ({:.3f}) pix".format(rms_y, rms_y_c)),
                      fontsize=16)
            ax.set_xlabel('Image number', fontsize=16)
            ax.set_ylabel('Offset (pixels)', fontsize=16)
            ax.set_title('{} {}'.format(object_id, filt), fontsize=16)
            fig.subplots_adjust(bottom=0.10, top=0.95, left=0.10, right=0.97)
            fig.savefig('{}_{}_donuts.png'.format(object_id, filt), dpi=300)
