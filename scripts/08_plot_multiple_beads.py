"""Plot trajectories and coordinates from a multiple-bead long-form CSV."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REQUIRED_FIELDS = ("bead_id", "t", "x", "y", "radius", "area")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input long-form CSV.")
    parser.add_argument("--save", default=None, help="Optional dashboard image path.")
    parser.add_argument("--no-show", action="store_true", help="Save/test without opening a window.")
    return parser


def load_multiple_beads_csv(filename):
    path = Path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")

    grouped = defaultdict(lambda: {"t": [], "x": [], "y": []})
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            try:
                bead_id = int(row["bead_id"])
                grouped[bead_id]["t"].append(float(row["t"]))
                grouped[bead_id]["x"].append(float(row["x"]))
                grouped[bead_id]["y"].append(float(row["y"]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid value at CSV line {line_number}") from exc

    if not grouped:
        raise ValueError("CSV contains no detections")

    for values in grouped.values():
        order = np.argsort(values["t"])
        for key in ("t", "x", "y"):
            values[key] = np.asarray(values[key], dtype=float)[order]
    return dict(grouped)


def create_dashboard(grouped, title=None):
    """Create one organized figure instead of one window per quantity."""
    figure, (trajectory_axis, x_axis, y_axis) = plt.subplots(1, 3, figsize=(18, 6))
    color_map = plt.get_cmap("tab10")

    for color_index, bead_id in enumerate(sorted(grouped)):
        values = grouped[bead_id]
        color = color_map(color_index % 10)
        label = f"bead {bead_id}"
        trajectory_axis.plot(values["x"], values["y"], ".-", ms=2, lw=1, color=color, label=label)
        x_axis.plot(values["t"], values["x"], color=color, label=label)
        y_axis.plot(values["t"], values["y"], color=color, label=label)

    trajectory_axis.set(xlabel="x [px]", ylabel="y [px]", title="x-y trajectories")
    trajectory_axis.axis("equal")
    x_axis.set(xlabel="t [s]", ylabel="x [px]", title="x(t)")
    y_axis.set(xlabel="t [s]", ylabel="y [px]", title="y(t)")
    for axis in (trajectory_axis, x_axis, y_axis):
        axis.grid(True, alpha=0.35)
        axis.legend()

    figure.suptitle(title or "Multiple-bead tracking")
    figure.tight_layout()
    return figure


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        grouped = load_multiple_beads_csv(args.input)
        figure = create_dashboard(grouped, title=Path(args.input).name)
        if args.save:
            output = Path(args.save)
            output.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(output, dpi=180, bbox_inches="tight")
            print(f"Saved dashboard to: {output}")
        points = sum(len(values["t"]) for values in grouped.values())
        print(f"Loaded {points} detections from {len(grouped)} beads.")
        if not args.no_show:
            plt.show()
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        plt.close("all")


if __name__ == "__main__":
    raise SystemExit(main())
