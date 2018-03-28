import glob as g
from astropy.io import fits
t1 = sorted(g.glob('Sp0746*.fts'))
t2 = sorted(g.glob('Sp1507*.fts'))

best_image1 = ""
best_image2 = ""
airmass1 = 5.0
airmass2 = 5.0
for i in t1:
  with fits.open(i) as ff:
    airmass = float(ff[0].header['AIRMASS'])
    if airmass < airmass1:
      airmass1 = airmass
      best_image1 = i
print(best_image1, airmass1)

for i in t2:
  with fits.open(i) as ff:
    airmass = float(ff[0].header['AIRMASS'])
    if airmass < airmass2:
      airmass2 = airmass
      best_image2 = i
print(best_image2, airmass2)