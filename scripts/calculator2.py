import numpy as np
import matplotlib.pyplot as plt

48

aa = np.r_[165363, 170233, 201779, 243890, 333004]

psi =  np.r_[-1.6811, +2.253, -1.888, -1.170, +1.2771]
aii = []
acc = []
corr = np.linspace(400, 401,  400)
for ii in corr:
    cc = (aa % ii) / (ii) * 2 * np.pi 

    align = psi - cc
    aii.append(ii)
    acc.append(cc[4])

plt.plot(aii, acc)
plt.grid(True)
plt.show()

# 413