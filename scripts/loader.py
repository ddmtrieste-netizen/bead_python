from _common import(
    load_csv,
    apply_screen_scale,
    maximize_window
)

import matplotlib.pyplot as plt
import numpy as np

def concatPath(x):
    xx = ""
    for ii in x:
        xx += ii
    return xx

def plot_data(t, x):

    plt.figure(figsize=(14, 8))
        
    plt.hist(x, bins=150)
    # plt.plot(t, psi_unw, label="psi")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("psi [rad]")
    plt.grid(True)
    plt.title("Angle vs time")
    plt.figure(figsize=(14, 8))
        
    plt.plot(t[1:], 1/x)
    # plt.plot(t, psi_unw, label="psi")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("psi [rad]")
    plt.grid(True)
    plt.title("Angle vs time")
    plt.show()


def main():

    filePath = "data/14082026_PM/test"
    fileNumber = "1"
    for ii in range(1, 1+1):
        path = concatPath([filePath, str(ii)])
        t, x, y, _, _ = load_csv(path)
        # print(f"Experimetn test{ii} - duration: {t[-1]} sec")
        print(f"{t[-1]}, # sec")

    delta_t = np.mean(np.diff(t))
    dt_medio = t[-1]/len(t)
    correction_ref = delta_t / dt_medio

    print(f"Error on dt medio:   {correction_ref}")
    print(f"Error on dt median:  {np.median(np.diff(t)) / dt_medio}")
    print(f"Previous correction: 1.0002441637524901 ")
    print(f"STD on dt medio:     {np.std(np.diff(t))}")

    plot_data(t, np.diff(t))
    
    



        
main()
