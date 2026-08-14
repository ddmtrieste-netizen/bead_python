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
    1786699963.2056553,
    1786700165.1971953,
    1786701430.477923,
    1786701451.2533998,
    1786701469.6039126
                    ])

ending_times = np.array([
    1786701442.9277394,
    1786701461.3101642,
    1786701480.3021162,

                    ])

number_of_samples = np.array([
    353,
    282,
    295
                    ])

# Bead phase
psi =  np.r_[
    -2.797436697204521,
    2.844809159168893,
    -2.8983016423207424,
    1.9572736353716174,
    -1.377821399282329
            ]



delta_time = diff_special(starting_times)
# fps_real = 1 / np.mean((ending_times[0] - starting_times)/number_of_samples)
#print(fps_real)
corr_omega = np.linspace(0.999999999, 1.00015, 10**4)
if 1:
    # omega = 2*np.pi*31/60*(3.66 + 0.09 - 0.0025 + 0.0009 - 0.000915)
    omega = 2*np.pi*31/60*(3.66 + 0.09 - 0.0025 + 0.0009) / 1.000293083235639 * corr_omega
    delta_phase = omega*delta_time[-1]
    psi_aligned = wrap(psi[-1] + delta_phase)
    misalignment = wrap(psi_aligned - psi[0])

    if 0:
        print(f"Fase del campo da PC clock: {(wrap(delta_phase))} rad")
        print(f"Fasi originali:             {psi} rad")
        print(f"Fasi riallineate:           {psi_aligned} rad")
        print(f"Dissalineamento:            {misalignment} rad")
        # print(rad2deg(diff_special(psi)))

        print(rad2deg(np.array([ 0.    ,     -0.03688979 ,-0.51919693, -0.53000801, -0.53329652])))
        print(f"Tempo passato: {diff_special(starting_times)/ 60}")

plt.figure()
plt.plot(corr_omega, misalignment, "--")
plt.grid()
plt.show()

