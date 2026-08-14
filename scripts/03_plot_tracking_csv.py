import argparse
import numpy as np
import matplotlib.pyplot as plt

from beadtrack._common import(
    load_csv,
    apply_screen_scale,
    maximize_window,
)

def main():
    parser = argparse.ArgumentParser(description="Plot bead tracking CSV.")
    parser.add_argument("--input", type=str, required=True, help="Input tracking CSV.")
    parser.add_argument("--save", type=str, default=None, help="Optional output figure path.")
    parser.add_argument("--scale", type=float, default=1.6, help="Visual scale factor.")

    args = parser.parse_args()

    apply_screen_scale(args.scale)

    t, x, y, radius, area = load_csv(args.input)

    x_tilde = x - np.mean(x)
    y_tilde = y - np.mean(y)
    theta = np.arctan2(y_tilde , x_tilde)
    theta_hist = np.histogram(theta, bins=50)
    # rotating frame (psi) = static frame (theta) - moving part (phase = angular vel * time) 
    phase = 2*np.pi*31/60 * (3.66 + 0.09 - 0.0025 + 0.0009) * np.array(t)
    #phase = 2*np.pi * (5.0265) / 2 * np.array(t)q for 40 - 0.00122
    psi = theta + phase
    psi_unw = np.remainder(psi + np.pi, 2*np.pi) - np.pi

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

   
    if len(t) == 0:
        print("No data found.")
        return

    plt.figure(figsize=(14, 8))
    # maximize_window()

    plt.plot(t, theta, label="theta")
    plt.plot(t, psi_unw, label="psi")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("psi [rad]")
    plt.grid(True)
    plt.legend()
    plt.title("Angle vs time")

    if args.save is not None:
        plt.savefig(args.save, dpi=200, bbox_inches="tight")

    plt.figure(figsize=(14, 8))
    # maximize_window()

    

    plt.plot(x, y, ".")
    plt.xlabel("x [px]")
    plt.ylabel("y [px]")
    plt.axis("equal")
    plt.grid(True)
    plt.title("Bead trajectory")

    # print(len(theta_hist[0]))
    # print(len(theta_hist[1]))
    # print(theta_hist[0])

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


    plt.figure(figsize=(14, 8))

    plt.plot(t, theta_dot, label="theta dot")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("Theta dot [rad/s]")
    plt.grid(True)
    plt.legend()
    plt.title("Angular velocity")

    plt.figure(figsize=(14, 8))
    
    plt.plot(t, theta_ddot, label="theta dot dot")
    # plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("Theta dot dot [rad/s^2]")
    plt.grid(True)
    plt.legend()
    plt.title("Angular acceleration")

    plt.figure(figsize=(14, 8))
    
    plt.plot(theta[:], theta_ddot[:], ".")
    # plt.plot(t, y, label="y")
    plt.xlabel("Theta [s]")
    plt.ylabel("Theta dot dot [rad/s^2]")
    plt.grid(True)
    plt.title("Theta vs angular acceleration")

    plt.figure(figsize=(14, 8))
    
    plt.plot(theta[:], theta_dot[:], ".")
    plt.xlabel("Theta [s]")
    plt.ylabel("Theta dot [rad/s]")
    plt.grid(True)
    plt.title("Theta vs angular velocity")
    plt.show()

    print(f"- - - - - Velocity - - - - -")
    print(f"median: {np.median(theta_dot)}")
    print(f"mean: {np.mean(theta_dot)}")
    print(f"std: {np.std(theta_dot[100:])}")
    print(np.mean(theta_dot) / np.median(theta_dot))
    print(f"- - - - - Psi - - - - -")
    print(f"median: {np.median(psi_unw)}")
    print(f"- - - - - Frames - - - - -")
    print(f"mean: {np.mean(np.diff(t))}")

if __name__ == "__main__":
    main()
