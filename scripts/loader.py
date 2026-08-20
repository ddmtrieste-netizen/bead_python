import argparse

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
    parser = argparse.ArgumentParser(description="Inspect tracking frame timing.")
    parser.add_argument("--input", required=True, help="Input tracking CSV.")
    args = parser.parse_args()

    data = load_tracking_csv(args.input)
    if len(data) < 2:
        print("At least two tracking samples are required.")
        return

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
