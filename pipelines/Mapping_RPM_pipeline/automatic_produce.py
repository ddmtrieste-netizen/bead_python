# pipelines/Mapping_RPM_pipeline/automatic_produce.py

import argparse
import csv
import re
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from beadtrack.console import error, info, ok, result as console_result, warn

from graphs_RPM import analyze_single_file, apply_screen_scale


def infer_speed_from_filename(file_path):
    """
    Expected filename:
        5_RPM.csv
        25_RPM.csv

    The leading number is interpreted as motor command [RPM].
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
        "motor_rpm_command",
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


def plot_rpm_curve(rows, output_figure=None, title=None, show=True):
    motor_rpm = np.asarray([row["motor_rpm_command"] for row in rows], dtype=float)
    bead_rpm = np.asarray([row["bead_rpm_fft"] for row in rows], dtype=float)
    bead_rpm_std = np.asarray([row["bead_rpm_fft_std"] for row in rows], dtype=float)

    method = rows[0]["method"]
    signal = rows[0]["signal"]

    plt.figure(figsize=(14, 8))

    if method == "bins":
        plt.errorbar(
            motor_rpm,
            bead_rpm,
            yerr=bead_rpm_std,
            marker="o",
            linestyle="-",
            capsize=4,
            label=f"FFT bins, signal={signal}",
        )
    else:
        plt.plot(
            motor_rpm,
            bead_rpm,
            marker="o",
            linestyle="-",
            label=f"Raw FFT, signal={signal}",
        )

    plt.xlabel("motor command [RPM]")
    plt.ylabel("bead dominant frequency [cycles/min]")
    plt.grid(True)
    plt.legend()

    if title is None:
        title = "Bead RPM from FFT vs commanded motor RPM"

    plt.title(title)
    plt.tight_layout()

    if output_figure is not None:
        output_figure = Path(output_figure)
        output_figure.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_figure, dpi=200)
        ok(f"Saved figure to {output_figure}")

    if show:
        plt.show()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Batch-produce bead RPM vs commanded motor RPM curve."
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/processed/mapping_RPM",
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
        default="data/processed/mapping_RPM/rpm_summary.csv",
        help="Output summary CSV.",
    )

    parser.add_argument(
        "--figure",
        type=str,
        default="data/processed/mapping_RPM/rpm_curve_bins.png",
        help="Output figure path. Use empty string to disable saving.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open an interactive plot window.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.scale <= 0:
        parser.error("--scale must be positive.")
    if args.bin_sec <= 0:
        parser.error("--bin-sec must be positive.")
    if args.fmax is not None and args.fmax <= args.fmin:
        parser.error("--fmax must be greater than --fmin.")

    if args.figure == "":
        args.figure = None

    try:
        apply_screen_scale(args.scale)
        files = find_speed_files(args.data_dir)
    except (OSError, ValueError) as exc:
        error(str(exc))
        return 1

    if len(files) == 0:
        error(f"No *_RPM.csv files found in {args.data_dir}")
        return 1

    info(
        f"Producing RPM curve: data_dir={args.data_dir} method={args.method} "
        f"signal={args.signal} files={len(files)}"
    )

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
                info(
                    f"{speed:>4} motor RPM | "
                    f"{rpm:>10.4g} +/- {rpm_std:>8.4g} cycles/min | "
                    f"{file_path.name}"
                )
            else:
                info(f"{speed:>4} motor RPM | {rpm:>10.4g} cycles/min | {file_path.name}")

        except Exception as exc:
            warn(f"Skipping {file_path.name}: {exc}")

    if len(rows) == 0:
        error("No valid RPM files were analyzed.")
        return 1

    try:
        save_summary_csv(args.output, rows)
        ok(f"Saved summary to {args.output}")
        plot_rpm_curve(
            rows,
            output_figure=args.figure,
            title="Bead RPM from FFT vs commanded motor RPM",
            show=not args.no_show,
        )
        console_result(f"files_analyzed={len(rows)} summary={args.output}")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        error(str(exc))
        return 1
    finally:
        plt.close("all")


if __name__ == "__main__":
    raise SystemExit(main())
