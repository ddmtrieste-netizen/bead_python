import argparse

import matplotlib.pyplot as plt
import numpy as np

from beadtrack.io import load_tracking_csv
from beadtrack.plotting import apply_plot_scale
from beadtrack.signals import median_smooth


def main():
    parser = argparse.ArgumentParser(description="Plot bead tracking CSV.")
    parser.add_argument("--input", type=str, required=True, help="Input tracking CSV.")
    parser.add_argument(
        "--reference",
        type=str,
        required=True,
        help="Reference tracking CSV.",
    )
    parser.add_argument(
        "--save", type=str, default=None, help="Optional output figure path."
    )
    parser.add_argument("--scale", type=float, default=1.6, help="Visual scale factor.")

    args = parser.parse_args()

    apply_plot_scale(args.scale)

    data = load_tracking_csv(args.input)
    reference = load_tracking_csv(args.reference)
    if len(data) == 0 or len(reference) == 0:
        print("No data found.")
        return

    x_tilde = data.x - np.mean(data.x)
    y_tilde = data.y - np.mean(data.y)
    theta = np.arctan2(y_tilde, x_tilde)

    # angular velocity
    theta_unw = np.unwrap(theta)
    theta_dot = np.gradient(theta_unw, data.time)
    # theta_dot = (theta - np.roll(theta, 1)) * 30  # rad/s
    # kk = 0
    # for ii in theta_dot:
    #    if ii  > 150 and ii  < -150:
    #        theta_dot[kk] = ii - 2*np.pi*30
    #    kk = kk + 1
    # theta_dot = theta_dot % (2 * np.pi)

    ########
    # Subtract mean reference value for acceleration
    ########

    x_tilde_ref = reference.x - np.mean(reference.x)
    y_tilde_ref = reference.y - np.mean(reference.y)
    theta_ref = np.arctan2(y_tilde_ref, x_tilde_ref)
    theta_unw_ref = np.unwrap(theta_ref)
    theta_dot_ref = np.gradient(theta_unw_ref, reference.time)

    idx = np.argsort(theta)
    theta_sort = theta[idx]
    theta_dot_sort = theta_dot[idx]

    idx_ref = np.argsort(theta_ref)
    theta_sort_ref = theta_ref[idx_ref]
    theta_dot_sort_ref = theta_dot_ref[idx_ref]

    trendline = median_smooth(
        theta_dot_sort,
        window_size=501,
    )
    trendline_ref = median_smooth(
        theta_dot_sort_ref,
        window_size=501,
    )

    delta_theta_dot = theta_dot - np.interp(
        theta,
        theta_sort_ref,
        trendline_ref,
        period=2 * np.pi,
    )
    theta_dot_sort_trend = delta_theta_dot[idx]
    delta_theta_trend = median_smooth(theta_dot_sort_trend)

    #####

    if args.save is not None:
        plt.savefig(args.save, dpi=200, bbox_inches="tight")

    plt.figure(figsize=(14, 8))

    plt.plot(theta_ref[:], theta_dot_ref[:], ".")
    plt.plot(theta_sort_ref[:], trendline_ref[:], linewidth=2)
    plt.xlabel("Theta [s]")
    plt.ylabel("Theta dot [rad/s]")
    plt.grid(True)
    plt.legend(("7", "5"))
    plt.title("Comparison Theta vs angular velocity")

    plt.figure(figsize=(14, 8))

    plt.plot(theta, delta_theta_dot[:], ".")
    plt.plot(theta_sort, delta_theta_trend, c="r")
    plt.xlabel("Theta [s]")
    plt.ylabel("Theta dot [rad/s]")
    plt.grid(True)
    plt.legend(("7", "5"))
    plt.title("Comparison Theta vs angular velocity")

    plt.figure(figsize=(14, 8))

    plt.plot(theta[:], theta_dot[:], ".")
    plt.plot(theta_ref[:], theta_dot_ref[:], ".")
    plt.xlabel("Theta [s]")
    plt.ylabel("Theta dot [rad/s]")
    plt.grid(True)
    plt.legend(("7", "5"))
    plt.title("Comparison Theta vs angular velocity")

    plt.figure(figsize=(8, 8))
    plt.subplot(projection="polar")
    plt.plot(theta_sort[:], -trendline[:], linewidth=2)
    plt.plot(theta_sort_ref[:], -trendline_ref[:], linewidth=2)
    plt.grid(True)
    plt.legend(
        ("Actual", "Reference"),
        loc="upper right",
        bbox_to_anchor=(1.1, 1.1),
        frameon=False,
    )
    plt.ylim((9, 14))
    plt.title("Angular velocity trendline magnitude")

    plt.figure(figsize=(14, 8))

    plt.plot(theta_sort, delta_theta_trend, c="r")
    plt.xlabel("Theta [s]")
    plt.ylabel("Theta dot [rad/s]")
    plt.grid(True)
    plt.legend(("7", "5"))
    plt.title("Comparison Theta vs angular velocity")
    plt.show()

    print(f"median: {np.median(theta_dot)}")
    print(f"mean: {np.mean(theta_dot)}")
    print(f"std: {np.std(theta_dot[100:])}")
    print(np.mean(theta_dot) / np.median(theta_dot))


if __name__ == "__main__":
    main()
