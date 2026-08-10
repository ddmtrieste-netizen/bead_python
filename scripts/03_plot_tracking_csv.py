"""Plot trajectory and position data from a tracking CSV."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from beadtrack.console import error, ok, result
from beadtrack.data import ensure_parent_dir, load_tracking_csv


def apply_screen_scale(scale):
    plt.rcParams.update(
        {
            "font.size": 14 * scale,
            "axes.titlesize": 18 * scale,
            "axes.labelsize": 16 * scale,
            "xtick.labelsize": 13 * scale,
            "ytick.labelsize": 13 * scale,
            "legend.fontsize": 13 * scale,
            "lines.linewidth": 2.0 * scale,
            "grid.linewidth": 0.8 * scale,
        }
    )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input tracking CSV.")
    parser.add_argument("--save", default=None, help="Optional trajectory image path.")
    parser.add_argument("--scale", type=float, default=1.6, help="Visual scale factor.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.scale <= 0:
        build_parser().error("--scale must be positive")

    try:
        t, x, y, _radius, _area = load_tracking_csv(args.input)
        apply_screen_scale(args.scale)

        plt.figure(figsize=(14, 8))
        plt.plot(x, y)
        plt.xlabel("x [px]")
        plt.ylabel("y [px]")
        plt.axis("equal")
        plt.grid(True)
        plt.title("Bead trajectory")

        if args.save is not None:
            output = ensure_parent_dir(args.save)
            plt.savefig(output, dpi=200, bbox_inches="tight")
            ok(f"Saved trajectory figure to {output}")

        plt.figure(figsize=(14, 8))
        plt.plot(t, x, label="x")
        plt.plot(t, y, label="y")
        plt.xlabel("t [s]")
        plt.ylabel("position [px]")
        plt.grid(True)
        plt.legend()
        plt.title("Position vs time")
        result(f"input={Path(args.input)} points={len(t)} plotted=true")
        plt.show()
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        error(str(exc))
        return 1
    finally:
        plt.close("all")


if __name__ == "__main__":
    raise SystemExit(main())
