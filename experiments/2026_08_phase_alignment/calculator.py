"""Initial scratch calculation for step-count and bead-phase alignment."""

import numpy as np

48

aa = 165363
qq = 170233
ww = 201779

psi4 = -1.7553
psi5 =  2.2000
psi6 = -2.0721

corr = 400
cc = (aa % corr) / (corr) * 2 * np.pi 
dd = (qq % corr) / (corr) * 2 * np.pi 
ee = (ww % corr) / (corr) * 2 * np.pi 

align4 = psi4 - cc
align5 = psi5 - dd
align6 = psi6 - ee




print(f"Remainder: {cc} radiants")
print(f"Remainder: {dd} radiants")
print(f"Remainder: {ee} radiants")


print(f"Surprize...4 : {(align4 + np.pi) % np.pi - np.pi} radiants")
print(f"Surprize...5 : {(align5 + np.pi) % np.pi - np.pi} radiants")
print(f"Surprize...6 : {(align6 + np.pi) % np.pi - np.pi} radiants")



print(f"in deg: {(((align4 + np.pi) % np.pi - np.pi )/ np.pi * 180)} deg")
print(f"in deg: {(((align5 + np.pi) % np.pi - np.pi) / np.pi * 180)} deg")
print(f"in deg: {(((align6 + np.pi) % np.pi - np.pi )/ np.pi * 180)} deg")

print(f"differences: {cc-dd} and {dd - ee} and {ee - cc} deg")

