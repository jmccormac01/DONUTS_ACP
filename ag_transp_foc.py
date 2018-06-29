"""
Measure the transparency in SPECULOOS images with respect to the
fluxes in the reference image for a given field
"""
import os
import math
import glob as g
import numpy as np
import matplotlib
matplotlib.use('QT5Agg')
import matplotlib.pyplot as plt
from astropy.io import fits
import sep
from donuts import Donuts

# pylint: disable = invalid-name

BKG_SIGMA = 3.0
SATURATION_LEVEL = 45000
PHOT_RADIUS = 10
GAIN = 1.0

def get_data(image):
    """
    Read in rhe fits image and return the data array

    Parameters
    ----------
    image : string
        Name of the image to open and extract data from

    Returns
    -------
    data : array-like
        The data in np.int32 format

    Raises
    ------
    None
    """
    with fits.open(image) as ff:
        # remove the overscan
        data = ff[0].data[20:2068, 4:].astype(np.int32)
    return data

def source_detect(data, sigma=BKG_SIGMA):
    """
    Find all the stars in a given image

    Parameters
    ----------
    data : array-like
        The data in np.int32 format

    Returns
    -------
    objects : sep extract object
        Information on all the sources found in the image
    bkg : array-like
        The sep background map

    Raises
    ------
    None
    """
    bkg = sep.Background(data)
    thresh = sigma * bkg.globalrms
    objects = sep.extract(data-bkg, thresh)
    return objects, bkg

def get_reference_set_of_stars(data, objects, saturation_level=SATURATION_LEVEL,
                               radius=PHOT_RADIUS):
    """
    Look through the list of detections and keep the good ones only

    Parameters
    ----------
    data : array-like
        data array to detect the stars in
    objects : sep.extract object
        list of information for a set of detections
    saturation_level : int
        the level above which to exclude stars in detection
        default = SATURATION_LEVEL
    radius : float
        the aperture radius to use when extracting photometry
        default =  PHOT_RADIUS

    Returns
    -------
    x_ref : array-like
        list of good stars' x positions
    y_ref : array-like
        list of good stars' y positions

    Raises
    ------
    None
    """
    x_ref, y_ref = [], []
    for i, j in zip(objects['x'], objects['y']):
        if i > 25 and i < 2023 and j > 25 and j < 2023:
            max_pix_val = round(data[int(j)-radius:int(j)+radius,
                                     int(i)-radius:int(i)+radius].ravel().max(), 2)
            if max_pix_val < saturation_level:
                x_ref.append(i)
                y_ref.append(j)
    return np.array(x_ref), np.array(y_ref)

def filter_list_of_objects_for_psf(objects, data, radius=PHOT_RADIUS,
                                   saturation_level=SATURATION_LEVEL):
    """
    filter a list of objects and return the best ones only
    """
    a, b = [], []
    k = 0
    for i, j in zip(objects['x'], objects['y']):
        if i > 25 and i < 2023 and j > 25 and j < 2023:
            max_pix_val = round(data[int(j)-radius:int(j)+radius,
                                     int(i)-radius:int(i)+radius].ravel().max(), 2)
            if max_pix_val < saturation_level:
                a.append(objects['a'][k])
                b.append(objects['b'][k])
        k += 1
    return np.array(a), np.array(b)


def do_phot(data, x, y, r_aper=PHOT_RADIUS):
    """
    Extract photometry from the reference positions,
    altered by the shifts from donuts

    Parameters
    ----------
    data : array-like
        data array to extract photometry from
    x : array-like
        list of x positions to extract
    y : array-like
        list of y positions to extract
    r_aper : float
        radius used for the aperture photometry

    Returns
    -------
    new_fluxes : array-like
        new flux measurements at these positions

    Raises
    ------
    None
    """
    bkg = sep.Background(data)
    data_new = data - bkg
    flux_new = []
    for i, j in zip(x, y):
        flux, _, _ = sep.sum_circle(data_new,
                                    i, j, r_aper,
                                    subpix=0,
                                    gain=GAIN)
        flux_new.append(flux)
    return np.array(flux_new)

def compare_ref_comp_fluxes(ref_flux, comp_flux):
    """
    Compare rhe reference fluxes with the latest values
    Return the average difference between the two sets

    Parameters
    ----------
    ref_flux : array-like
        list of fluxes at the reference position
    comp_flux : array-like
        list of fluxes to compare to the reference values

    Returns
    -------
    ratio : float
        average ratio between comp / ref

    Raises
    ------
    """
    assert len(ref_flux) == len(comp_flux), "Length of flux arrays not the same..."
    ratio = (comp_flux / ref_flux)*100.
    return np.average(ratio)

def get_average_fwhm(a, b):
    """
    Get the average FWHM for a given set of objects
    """
    fwhms = []
    for k, l in zip(a, b):
        fwhms.append(2. * math.sqrt(math.log(2.) * (k**2. + l**2.)))
    return np.average(fwhms)

if __name__ == "__main__":
    # what is the current reference image?
    data_dir = '/Users/jmcc/Dropbox/data/speculoos/europa/20180624'
    os.chdir(data_dir)
    image_ids = sorted(g.glob('*.fts'))
    transparency, fwhm = [], []

    # set up reference frame
    ref_image = image_ids[0]
    d = Donuts(ref_image, scan_direction='y', overscan_width=20, prescan_width=20)

    # get the reference stars and the reference fluxes
    ref_data = get_data(ref_image)
    ref_objects, _ = source_detect(ref_data)
    x_ref, y_ref = get_reference_set_of_stars(ref_data, ref_objects)
    flux_ref = do_phot(ref_data, x_ref, y_ref)
    transparency.append(100)

    for i, image_id in enumerate(image_ids[1:]):
        print('[{}/{}]'.format(i, len(image_ids)))
        shift = d.measure_shift(image_id)
        data = get_data(image_id)
        x_new = x_ref - shift.x.value
        y_new = y_ref - shift.y.value
        # get a filtered list of objects in the image
        # these are used for the PSF stats, maybe slightly different
        # to those used for the photometry
        objects, _ = source_detect(data)
        psf_a, psf_b = filter_list_of_objects_for_psf(objects, data)
        fwhm.append(get_average_fwhm(psf_a, psf_b))
        flux_comp = do_phot(data, x_new, y_new)
        transparency.append(compare_ref_comp_fluxes(flux_ref, flux_comp))

    # plot the results
    fig, ax = plt.subplots(1, figsize=(10, 10))
    ax2 = ax.twinx()
    ax.plot(transparency, 'g.')
    ax.set_xlabel('Image ID')
    ax.set_ylabel('Relative Transparency (comp/ref) per-cent')
    ax2.plot(fwhm, 'r.')
    ax2.set_ylabel('FWHM (pixels)')
    plt.show()
