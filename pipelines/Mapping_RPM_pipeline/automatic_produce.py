# pipelines/Mapping_RPM_pipeline/automatic_produce.py

import argparse
import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from graphs_RPM import analyze_single_file

from beadtrack.plotting import apply_plot_scale


def infer_speed_from_filename(file_path):
    """
    Expected filename:
        5_RPM.csv
        25_RPM.csv

    The leading number is interpreted as motor command [steps/s].
    """

    file_path = Path(file_path)
    match = re.match(r"(\d+)_RPM\.csv$", file_path.name)

    if match is None:
        raise ValueError(f"Cannot infer speed from filename: {file_path.name}")

    return int(match.group(1))


def find_speed_files(data_dir):
    data_dir = Path(data_dir)

    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    files = list(data_dir.glob("*_RPM.csv"))

    files = sorted(
        files,
        key=lambda file_path: infer_speed_from_filename(file_path),
    )

    return files


def save_summary_csv(output_file, rows):
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "steps_per_second",
        "file",
        "method",
        "signal",
        "bead_rpm_fft",
        "bead_rpm_fft_std",
        "duration_s",
        "n_points",
        "n_bins",
        "bin_sec",
    ]

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def plot_rpm_curve(rows, output_figure=None, title=None):
    steps = np.asarray([row["steps_per_second"] for row in rows], dtype=float)
    bead_rpm = np.asarray([row["bead_rpm_fft"] for row in rows], dtype=float)
    bead_rpm_std = np.asarray([row["bead_rpm_fft_std"] for row in rows], dtype=float)

    method = rows[0]["method"]
    signal = rows[0]["signal"]

    plt.figure(figsize=(14, 8))

    if method == "bins":
        plt.errorbar(
            steps,
            bead_rpm,
            yerr=bead_rpm_std,
            marker="o",
            linestyle="-",
            capsize=4,
            label=f"FFT bins, signal={signal}",
        )
    else:
        plt.plot(
            steps,
            bead_rpm,
            marker="o",
            linestyle="-",
            label=f"Raw FFT, signal={signal}",
        )

    plt.xlabel("motor command [steps/s]")
    plt.ylabel("bead dominant frequency [cycles/min]")
    plt.grid(True)
    plt.legend()

    if title is None:
        title = "Bead RPM from FFT vs motor steps/s"

    plt.title(title)
    plt.tight_layout()

    if output_figure is not None:
        output_figure = Path(output_figure)
        output_figure.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_figure, dpi=200)
        print(f"Saved figure to: {output_figure}")

    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Batch-produce bead RPM vs motor steps/s curve."
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data/mapping_RMP_aug07/mapping_RMP_1",
        help="Folder containing files like 5_RPM.csv.",
    )

    parser.add_argument(
        "--method",
        type=str,
        default="raw",
        choices=["raw", "bins"],
        help="FFT method.",
    )

    parser.add_argument(
        "--signal",
        type=str,
        default="x",
        choices=["x", "y", "r", "radius"],
        help="Signal used for FFT.",
    )

    parser.add_argument(
        "--bin-sec",
        type=float,
        default=20.0,
        help="Bin length in seconds for --method bins.",
    )

    parser.add_argument(
        "--fmin",
        type=float,
        default=0.0,
        help="Minimum frequency considered in FFT [Hz].",
    )

    parser.add_argument(
        "--fmax",
        type=float,
        default=None,
        help="Maximum frequency considered in FFT [Hz].",
    )

    parser.add_argument(
        "--scale",
        type=float,
        default=1.6,
        help="Visual scale factor.",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="./data/mapping_RMP_aug07/mapping_1/rpm_summary.csv",
        help="Output summary CSV.",
    )

    parser.add_argument(
        "--figure",
        type=str,
        default="./data/mapping_RMP_aug07/outcome/rpm_curve_raw.png",
        help="Output figure path. Use empty string to disable saving.",
    )

    args = parser.parse_args()

    if args.figure == "":
        args.figure = None

    apply_plot_scale(args.scale)

    files = find_speed_files(args.data_dir)

    if len(files) == 0:
        print(f"No *_RPM.csv files found in: {args.data_dir}")
        return

    print("Producing RPM curve...")
    print(f"data_dir = {args.data_dir}")
    print(f"method   = {args.method}")
    print(f"signal   = {args.signal}")
    print(f"n_files  = {len(files)}")
    print()

    rows = []

    for file_path in files:
        speed = infer_speed_from_filename(file_path)

        try:
            result = analyze_single_file(
                speed=speed,
                data_dir=args.data_dir,
                method=args.method,
                signal_name=args.signal,
                bin_sec=args.bin_sec,
                fmin=args.fmin,
                fmax=args.fmax,
            )

            rows.append(result)

            rpm = result["bead_rpm_fft"]
            rpm_std = result["bead_rpm_fft_std"]

            if args.method == "bins":
                print(
                    f"{speed:>4} steps/s | "
                    f"{rpm:>10.4g} ± {rpm_std:>8.4g} cycles/min | "
                    f"{file_path.name}"
                )
            else:
                print(
                    f"{speed:>4} steps/s | {rpm:>10.4g} cycles/min | {file_path.name}"
                )

        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Skipping {file_path.name}: {exc}")

    if len(rows) == 0:
        print("No valid files analyzed.")
        return

    save_summary_csv(args.output, rows)
    print()
    print(f"Saved summary to: {args.output}")

    plot_rpm_curve(
        rows,
        output_figure=args.figure,
        title="Bead RPM from FFT vs motor steps/s",
    )


if __name__ == "__main__":
    main()
