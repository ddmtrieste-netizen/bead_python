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


def main():
    parser = argparse.ArgumentParser(description="Plot bead tracking CSV.")
    parser.add_argument("--input", type=str, required=True, help="Input tracking CSV.")
    parser.add_argument("--save", type=str, default=None, help="Optional output figure path.")

    args = parser.parse_args()

    t, x, y, radius, area = load_csv(args.input)

    if len(t) == 0:
        print("No data found.")
        return

    plt.figure()
    plt.plot(x, y)
    plt.xlabel("x [px]")
    plt.ylabel("y [px]")
    plt.axis("equal")
    plt.grid(True)
    plt.title("Bead trajectory")

    if args.save is not None:
        plt.savefig(args.save, dpi=200, bbox_inches="tight")

    plt.figure()
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
