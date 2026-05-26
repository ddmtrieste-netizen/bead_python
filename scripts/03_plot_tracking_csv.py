import argparse
import csv

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

    if len(t) == 0:
        print("No data found.")
        return

    plt.figure(figsize=(14, 8))
    # maximize_window()

    plt.plot(x, y)
    plt.xlabel("x [px]")
    plt.ylabel("y [px]")
    plt.axis("equal")
    plt.grid(True)
    plt.title("Bead trajectory")

    if args.save is not None:
        plt.savefig(args.save, dpi=200, bbox_inches="tight")

    plt.figure(figsize=(14, 8))
    # maximize_window()

    plt.plot(t, x, label="x")
    plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("position [px]")
    plt.grid(True)
    plt.legend()
    plt.title("Position vs time")

    plt.show()


if __name__ == "__main__":
    main()
