"""
Take a measure of the RMS from the AG log file

This may be intrinsically different from the real RMS
measured by tracking a star post-facto
"""
import numpy as np

if __name__ == "__main__":
    x, y = np.loadtxt('guider.log', usecols=[3, 4], unpack=True)
    print("RMS: X={:.3f} pix - Y={:.3f} pix".format(np.std(x), np.std(y)))

