"""Evaluate phase alignment with a fixed steps-per-revolution value."""

import numpy as np
import matplotlib.pyplot as plt


# Steps count
steps_count = np.r_[165363, 170233, 201779, 243890, 333004]
# Bead phase
psi =  np.r_[-1.6811, +2.253, -1.888, -1.170, +1.2771]

steps_per_revol = 400.25
steps_count_angle = (steps_count % steps_per_revol) / (steps_per_revol) * 2 * np.pi - np.pi

align = psi - steps_count_angle

plt.plot(steps_count_angle)
plt.plot(align)
#plt.plot(steps_count_angle)
plt.grid(True)
plt.show()

# 413
