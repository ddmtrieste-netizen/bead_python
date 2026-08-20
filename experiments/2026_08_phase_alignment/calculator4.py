"""Reconstruct field phase from acquisition timestamps and angular velocity."""

import numpy as np
import matplotlib.pyplot as plt

def wrap(x):
    return (x + np.pi) % (2*np.pi) - np.pi

def rad2deg(x):
    return x * 180 / np.pi

def diff_special(x):
    # return np.diff(x, prepend=x[0])
    return x - x[0]
# Steps count
starting_times = np.array([
                    1786627207.7428648,
                    1786627291.3519,
                    1786627551.2822418,
                    1786631062.8429468
                    ])

duration = np.array([
                    45.6213800907135, # sec
                    65.5196430683136, # sec
                    132.0927929878235, # sec
                    613.469313621521 # sec
                    ])
# Bead phase
psi =  np.r_[ 
            2.7724383393340197, 
            2.2703656251276776,
            2.946129739481968,
            -0.006093048143959834
            ]

delta_time = diff_special(starting_times)
omega = 2*np.pi*40/60*(3.66 + 0.09 - 0.0025 - 0.00122)
delta_phase = omega*delta_time
psi_aligned = wrap(psi + delta_phase)
misalignment = wrap(psi_aligned - psi[0])

if 0:
    print(f"Fase del campo da PC clock: {(wrap(delta_phase))} rad")
    print(f"Fasi originali:             {psi} rad")
    print(f"Fasi riallineate:           {psi_aligned} rad")
    print(f"Dissalineamento:            {misalignment} rad")
    # print(rad2deg(diff_special(psi)))


print(f"{wrap(duration[0] * omega)}")
