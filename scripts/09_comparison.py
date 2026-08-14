import argparse
import csv
import numpy as np

from _common import(
    smooth_median,
    smooth_sav
)

import matplotlib.pyplot as plt


def load_csv(filename):
    t = []
    x = []
    y = []
    radius = []
    area = []

    with open(filename, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            t.append(float(row["t"]))
            x.append(float(row["x"]))
            y.append(float(row["y"]))
            radius.append(float(row["radius"]))
            area.append(float(row["area"]))

    return t, x, y, radius, area


def apply_screen_scale(scale):
    plt.rcParams.update({
        "font.size": 14 * scale,
        "axes.titlesize": 18 * scale,
        "axes.labelsize": 16 * scale,
        "xtick.labelsize": 13 * scale,
        "ytick.labelsize": 13 * scale,
        "legend.fontsize": 13 * scale,
        "lines.linewidth": 2.0 * scale,
        "grid.linewidth": 0.8 * scale,
    })


def maximize_window():
    manager = plt.get_current_fig_manager()

    try:
        manager.window.showMaximized()
    except Exception:
        try:
            manager.full_screen_toggle()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Plot bead tracking CSV.")
    parser.add_argument("--input", type=str, required=True, help="Input tracking CSV.")
    parser.add_argument("--save", type=str, default=None, help="Optional output figure path.")
    parser.add_argument("--scale", type=float, default=1.6, help="Visual scale factor.")

    args = parser.parse_args()

    apply_screen_scale(args.scale)

    t, x, y, radius, area = load_csv(args.input)
    t_ref, x_ref, y_ref, radius, area = load_csv("data/10082026/test5")

    x_tilde = x - np.mean(x)
    y_tilde = y - np.mean(y)
    theta = np.arctan2(y_tilde , x_tilde)
    # rotating frame (psi) = static frame (theta) - moving part (phase = angular vel * time) 
    phase = 2*np.pi*31/60 * (3.66 + 0.09 -0.0025) * np.array(t) 
    psi = theta + phase
    psi_unw = np.remainder(psi, 2*np.pi) - np.pi

    # angular velocity
    theta_unw = np.unwrap(theta)
    theta_dot = np.gradient(theta_unw, np.array(t))
    theta_ddot = np.gradient(theta_dot, np.array(t))
    #theta_dot = (theta - np.roll(theta, 1)) * 30  # rad/s
    #kk = 0
    #for ii in theta_dot:
    #    if ii  > 150 and ii  < -150:
    #        theta_dot[kk] = ii - 2*np.pi*30 
    #    kk = kk + 1
    # theta_dot = theta_dot % (2 * np.pi)


    ######## 
    # Subtract mean reference value for acceleration
    ########

    x_tilde_ref = x_ref - np.mean(x_ref)
    y_tilde_ref = y_ref - np.mean(y_ref)
    theta_ref  = np.arctan2(y_tilde_ref, x_tilde_ref)
    theta_unw_ref =  np.unwrap(theta_ref)
    theta_dot_ref = np.gradient(theta_unw_ref, np.array(t_ref))

    holder   = np.zeros(100)
    counter  = np.zeros(100)
    newTheta = np.arange(-314 , 314, 100) / 100

    idx = np.argsort(theta)
    theta_sort = theta[idx]
    theta_dot_sort = theta_dot[idx]

    idx_ref = np.argsort(theta_ref)
    theta_sort_ref = theta_ref[idx_ref]
    theta_dot_sort_ref = theta_dot_ref[idx_ref]

    trendline= smooth_median(
        theta_dot_sort,
        window = 501
    )
    trendline_ref = smooth_median(
        theta_dot_sort_ref,
        window = 501
    )

    theta_common = np.linspace(-np.pi, np.pi, 1000)
    # theta_dot_resamp = np.interp(theta_common, theta_sort, trendline, period=2*np.pi)
    delta_theta_dot= theta_dot - np.interp(theta, theta_sort_ref, trendline_ref, period=2*np.pi)
    theta_dot_sort_trend = delta_theta_dot[idx]
    delta_theta_trend = smooth_median(theta_dot_sort_trend)

    #####
   
    if len(t) == 0:
        print("No data found.")
        return

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
        loc = "upper right",
        bbox_to_anchor = (1.1, 1.1),
        frameon = False
        )
    plt.ylim((9, 14))
    plt.title("Angular velocity trendline magnitude")
    plt.show()



    print(f"median: {np.median(theta_dot)}")
    print(f"mean: {np.mean(theta_dot)}")
    print(f"std: {np.std(theta_dot[100:])}")
    print(np.mean(theta_dot) / np.median(theta_dot))

if __name__ == "__main__":
    main()
