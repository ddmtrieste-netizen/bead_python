import argparse

import matplotlib.pyplot as plt
import numpy as np

from beadtrack.io import load_tracking_csv
from beadtrack.plotting import apply_plot_scale


def main():
    parser = argparse.ArgumentParser(description="Plot bead tracking CSV.")
    parser.add_argument("--input", type=str, required=True, help="Input tracking CSV.")
    parser.add_argument(
        "--save", type=str, default=None, help="Optional output figure path."
    )
    parser.add_argument("--scale", type=float, default=1.6, help="Visual scale factor.")

    args = parser.parse_args()

    apply_plot_scale(args.scale)

    data = load_tracking_csv(args.input)
    if len(data) == 0:
        print("No data found.")
        return

    x_tilde = data.x - np.mean(data.x)
    y_tilde = data.y - np.mean(data.y)
    theta = np.arctan2(y_tilde, x_tilde)
    # rotating frame (psi) = static frame (theta) - moving part (phase = angular vel * time)
    phase = 2 * np.pi * 31 / 60 * (3.66 + 0.09 - 0.0025 + 0.0009) * data.time
    psi = theta + phase
    psi_unw = np.remainder(psi + np.pi, 2 * np.pi) - np.pi

    # angular velocity
    theta_unw = np.unwrap(theta)
    theta_dot = np.gradient(theta_unw, data.time)
    theta_ddot = np.gradient(theta_dot, data.time)

    plt.figure(figsize=(14, 8))
    plt.plot(data.time, theta, label="theta")
    plt.plot(data.time, psi_unw, label="psi")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("psi [rad]")
    plt.grid(True)
    plt.legend()
    plt.title("Angle vs time")

    if args.save is not None:
        plt.savefig(args.save, dpi=200, bbox_inches="tight")

    # Suppress too many figures
    if False:
        plt.figure(figsize=(14, 8))
        plt.plot(data.x, data.y, ".")
        plt.xlabel("x [px]")
        plt.ylabel("y [px]")
        plt.axis("equal")
        plt.grid(True)
        plt.title("Bead trajectory")

        plt.figure(figsize=(14, 8))
        plt.hist(theta, bins=100, label="hist")
        # plt.plot(t, y, label="y")
        plt.xlabel("theta [rad]")
        plt.ylabel("Histogram static")
        plt.grid(True)
        plt.legend()
        plt.title("Events vs time")

        plt.figure(figsize=(14, 8))
        plt.hist(psi_unw, bins=100, label="hist")
        # plt.plot(t, y, label="y")
        plt.xlabel("psi [rad]")
        plt.ylabel("Histogram rotating")
        plt.grid(True)
        plt.legend()
        plt.xlim((-np.pi, np.pi))
        plt.title("Events vs time")

        # Figure
        plt.figure(figsize=(14, 8))
        plt.plot(data.time, theta_dot, label="theta dot")
        plt.xlabel("t [s]")
        plt.ylabel("Theta dot [rad/s]")
        plt.grid(True)
        plt.legend()
        plt.title("Angular velocity")

        # Figure
        plt.figure(figsize=(14, 8))
        plt.plot(data.time, theta_ddot, label="theta dot dot")
        plt.xlabel("t [s]")
        plt.ylabel("Theta dot dot [rad/s^2]")
        plt.grid(True)
        plt.legend()
        plt.title("Angular acceleration")

        # Figure
        plt.figure(figsize=(14, 8))
        plt.plot(theta[:], theta_ddot[:], ".")
        plt.xlabel("Theta [s]")
        plt.ylabel("Theta dot dot [rad/s^2]")
        plt.grid(True)
        plt.title("Theta vs angular acceleration")

        # Figure
        plt.figure(figsize=(14, 8))
        plt.plot(theta[:], theta_dot[:], ".")
        plt.xlabel("Theta [s]")
        plt.ylabel("Theta dot [rad/s]")
        plt.grid(True)
        plt.title("Theta vs angular velocity")
    plt.show()

    print("- - - - - Velocity - - - - -")
    print(f"median: {np.median(theta_dot)}")
    print(f"mean: {np.mean(theta_dot)}")
    print(f"std: {np.std(theta_dot[100:])}")
    print(np.mean(theta_dot) / np.median(theta_dot))
    print("- - - - - Psi - - - - -")
    print(f"median: {np.median(psi_unw)}")
    print("- - - - - Frames - - - - -")
    print(f"mean: {np.mean(np.diff(data.time))}")


if __name__ == "__main__":
    main()
