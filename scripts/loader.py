import matplotlib.pyplot as plt
import numpy as np

from beadtrack.io import load_tracking_csv


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

    plt.plot(t[1:], 1 / x)
    # plt.plot(t, psi_unw, label="psi")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("psi [rad]")
    plt.grid(True)
    plt.title("Angle vs time")
    plt.show()


def main():
    file_path_prefix = "data/14082026_PM/test"
    for index in range(1, 2):
        path = f"{file_path_prefix}{index}"
        data = load_tracking_csv(path)
        # print(f"Experimetn test{ii} - duration: {t[-1]} sec")
        print(f"{data.time[-1]}, # sec")

    delta_t = np.mean(np.diff(data.time))
    dt_medio = data.time[-1] / len(data)
    correction_ref = delta_t / dt_medio

    print(f"Error on dt medio:   {correction_ref}")
    print(f"Error on dt median:  {np.median(np.diff(data.time)) / dt_medio}")
    print("Previous correction: 1.0002441637524901")
    print(f"STD on dt medio:     {np.std(np.diff(data.time))}")

    plot_data(data.time, np.diff(data.time))


if __name__ == "__main__":
    main()
