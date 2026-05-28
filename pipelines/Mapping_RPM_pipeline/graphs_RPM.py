# pipelines/Mapping_RPM_pipeline/graphs_RPM.py

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------

def load_csv(filename):
    t = []
    x = []
    y = []
    radius = []
    area = []

    with open(filename, "r", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            t.append(float(row["t"]))
            x.append(float(row["x"]))
            y.append(float(row["y"]))
            radius.append(float(row["radius"]))
            area.append(float(row["area"]))

    return (
        np.asarray(t, dtype=float),
        np.asarray(x, dtype=float),
        np.asarray(y, dtype=float),
        np.asarray(radius, dtype=float),
        np.asarray(area, dtype=float),
    )


def get_file_from_speed(data_dir, speed):
    data_dir = Path(data_dir)
    return data_dir / f"{speed}_RPM.csv"


def write_single_result_csv(output_file, result):
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
        writer.writerow(result)


# ---------------------------------------------------------------------
# Plot style
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------

def select_signal(signal_name, x, y, radius):
    if signal_name == "x":
        return x

    if signal_name == "y":
        return y

    if signal_name in ("r", "radius"):
        return radius

    raise ValueError(f"Unknown signal: {signal_name}")


def clean_and_sort_time_signal(t, signal):
    t = np.asarray(t, dtype=float)
    signal = np.asarray(signal, dtype=float)

    valid = np.isfinite(t) & np.isfinite(signal)
    t = t[valid]
    signal = signal[valid]

    if len(t) == 0:
        return t, signal

    order = np.argsort(t)

    return t[order], signal[order]


# ---------------------------------------------------------------------
# FFT core
# ---------------------------------------------------------------------

def estimate_fft_raw(t, signal, fmin=0.0, fmax=None):
    """
    Estimate the dominant frequency from one signal using FFT.

    The input timestamps can be slightly non-uniform because they come from
    real camera acquisition. For this reason, the signal is first interpolated
    on a uniform time grid.

    Returns
    -------
    rpm : float
        Dominant frequency converted to cycles/min.
    freq_hz : float
        Dominant frequency in Hz.
    freqs : ndarray
        Frequency axis.
    spectrum : ndarray
        One-sided FFT amplitude.
    """

    t, signal = clean_and_sort_time_signal(t, signal)

    if len(t) < 4:
        return np.nan, np.nan, np.array([]), np.array([])

    duration = t[-1] - t[0]

    if duration <= 0:
        return np.nan, np.nan, np.array([]), np.array([])

    dt = np.median(np.diff(t))

    if not np.isfinite(dt) or dt <= 0:
        return np.nan, np.nan, np.array([]), np.array([])

    n_uniform = int(np.floor(duration / dt)) + 1

    if n_uniform < 4:
        return np.nan, np.nan, np.array([]), np.array([])

    t_uniform = np.linspace(t[0], t[-1], n_uniform)
    signal_uniform = np.interp(t_uniform, t, signal)

    # Raw FFT idea: only remove the mean/DC component.
    signal_uniform = signal_uniform - np.mean(signal_uniform)

    dt_uniform = t_uniform[1] - t_uniform[0]

    freqs = np.fft.rfftfreq(n_uniform, d=dt_uniform)
    spectrum = np.abs(np.fft.rfft(signal_uniform))

    mask = freqs > 0.0

    if fmin is not None:
        mask &= freqs >= fmin

    if fmax is not None:
        mask &= freqs <= fmax

    if not np.any(mask):
        return np.nan, np.nan, freqs, spectrum

    freqs_selected = freqs[mask]
    spectrum_selected = spectrum[mask]

    freq_hz = freqs_selected[np.argmax(spectrum_selected)]
    rpm = 60.0 * freq_hz

    return rpm, freq_hz, freqs, spectrum


def estimate_fft_bins(t, signal, bin_sec=20.0, fmin=0.0, fmax=None):
    """
    Estimate dominant frequency on non-overlapping bins.

    For each bin, compute one raw FFT.
    The final value is the median of the bin-wise RPM values.
    """

    t, signal = clean_and_sort_time_signal(t, signal)

    if len(t) < 4:
        return np.nan, np.nan, []

    t0 = t[0]
    t1 = t[-1]
    duration = t1 - t0

    if duration <= 0:
        return np.nan, np.nan, []

    if duration < bin_sec:
        rpm, _, _, _ = estimate_fft_raw(t, signal, fmin=fmin, fmax=fmax)
        return rpm, np.nan, [rpm]

    bin_rpms = []
    start = t0

    while start + bin_sec <= t1:
        end = start + bin_sec
        mask = (t >= start) & (t < end)

        if np.count_nonzero(mask) >= 4:
            rpm, _, _, _ = estimate_fft_raw(
                t[mask],
                signal[mask],
                fmin=fmin,
                fmax=fmax,
            )

            if np.isfinite(rpm):
                bin_rpms.append(rpm)

        start = end

    if len(bin_rpms) == 0:
        return np.nan, np.nan, []

    bin_rpms = np.asarray(bin_rpms, dtype=float)

    rpm_median = float(np.median(bin_rpms))
    rpm_std = float(np.std(bin_rpms))

    return rpm_median, rpm_std, list(bin_rpms)


# ---------------------------------------------------------------------
# Analysis of one file
# ---------------------------------------------------------------------

def analyze_single_file(
    speed=None,
    data_dir="./data/mapping_RPM_submerged/mapping_RMP",
    method="raw",
    signal_name="x",
    bin_sec=20.0,
    fmin=0.0,
    fmax=None,
):
    """
    Atomic analysis: one speed -> one file -> one result.

    If speed is not provided, speed=5 is used as fallback.
    """

    if speed is None:
        speed = 5

    file_path = get_file_from_speed(data_dir, speed)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    t, x, y, radius, area = load_csv(file_path)

    if len(t) == 0:
        raise ValueError(f"No data found in file: {file_path}")

    signal = select_signal(signal_name, x, y, radius)

    if method == "raw":
        bead_rpm, _, _, _ = estimate_fft_raw(
            t,
            signal,
            fmin=fmin,
            fmax=fmax,
        )
        bead_rpm_std = np.nan
        n_bins = 1

    elif method == "bins":
        bead_rpm, bead_rpm_std, bin_rpms = estimate_fft_bins(
            t,
            signal,
            bin_sec=bin_sec,
            fmin=fmin,
            fmax=fmax,
        )
        n_bins = len(bin_rpms)

    else:
        raise ValueError(f"Unknown method: {method}")

    duration_s = float(t[-1] - t[0]) if len(t) > 1 else np.nan

    result = {
        "steps_per_second": int(speed),
        "file": str(file_path),
        "method": method,
        "signal": signal_name,
        "bead_rpm_fft": bead_rpm,
        "bead_rpm_fft_std": bead_rpm_std,
        "duration_s": duration_s,
        "n_points": int(len(t)),
        "n_bins": int(n_bins),
        "bin_sec": float(bin_sec) if method == "bins" else np.nan,
    }

    return result


# ---------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------

def run_explore(args):
    

    if args.speed is None:
        args.speed = 5

    file_path = get_file_from_speed(args.data_dir, args.speed)

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    t, x, y, radius, area = load_csv(file_path)

    if len(t) == 0:
        print(f"No data found for {file_path}.")
        return

    plt.figure(figsize=(14, 8))
    plt.plot(x, y)
    plt.xlabel("x [px]")
    plt.ylabel("y [px]")
    plt.axis("equal")
    plt.grid(True)
    plt.title(f"Bead trajectory | speed = {args.speed}")

    plt.figure(figsize=(14, 8))
    plt.plot(t, x, label="x")
    plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("position [px]")
    plt.grid(True)
    plt.legend()
    plt.title(f"Position vs time | speed = {args.speed}")

    plt.show()


def run_produce(args):
    """
    Produce mode: one file only.

    This is intentionally atomic. Batch iteration belongs to
    automatic_produce.py.
    """

    if args.speed is None:
        args.speed = 5

    file_path = get_file_from_speed(args.data_dir, args.speed)

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    t, x, y, radius, area = load_csv(file_path)

    if len(t) == 0:
        print(f"No data found for {file_path}.")
        sys.exit(1)

    signal = select_signal(args.signal, x, y, radius)

    result = analyze_single_file(
        speed=args.speed,
        data_dir=args.data_dir,
        method=args.method,
        signal_name=args.signal,
        bin_sec=args.bin_sec,
        fmin=args.fmin,
        fmax=args.fmax,
    )

    bead_rpm = result["bead_rpm_fft"]
    bead_rpm_std = result["bead_rpm_fft_std"]

    print(
        "RESULT "
        f"steps_per_second={result['steps_per_second']} "
        f"bead_rpm_fft={bead_rpm:.6g} "
        f"bead_rpm_fft_std={bead_rpm_std:.6g} "
        f"method={result['method']} "
        f"signal={result['signal']} "
        f"file={result['file']}"
    )

    if args.output is not None:
        write_single_result_csv(args.output, result)
        print(f"Saved single-result CSV to: {args.output}")

    if args.no_show:
        return

    if args.method == "raw":
        rpm, freq_hz, freqs, spectrum = estimate_fft_raw(
            t,
            signal,
            fmin=args.fmin,
            fmax=args.fmax,
        )

        plt.figure(figsize=(14, 8))
        plt.plot(freqs, spectrum)
        plt.xlabel("frequency [Hz]")
        plt.ylabel("FFT amplitude")
        plt.grid(True)
        plt.title(
            f"Raw FFT | speed = {args.speed} | "
            f"peak = {freq_hz:.4g} Hz = {rpm:.4g} cycles/min"
        )
        plt.tight_layout()

    elif args.method == "bins":
        rpm, rpm_std, bin_rpms = estimate_fft_bins(
            t,
            signal,
            bin_sec=args.bin_sec,
            fmin=args.fmin,
            fmax=args.fmax,
        )

        plt.figure(figsize=(14, 8))
        plt.plot(np.arange(len(bin_rpms)), bin_rpms, marker="o")
        plt.xlabel("non-overlapping bin index")
        plt.ylabel("bead dominant frequency [cycles/min]")
        plt.grid(True)
        plt.title(
            f"Binned FFT | speed = {args.speed} | "
            f"median = {rpm:.4g}, std = {rpm_std:.4g}"
        )
        plt.tight_layout()

    plt.show()


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Explore one run or produce FFT RPM estimate for one file."
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="produce",
        choices=["explore", "produce"],
        help="Working mode.",
    )

    parser.add_argument(
        "--speed",
        type=int,
        default=None,
        help="Speed/command. If omitted, speed=5 is used.",
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data/mapping_RPM_submerged/mapping_RMP3",
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
        default=None,
        help="Optional output CSV for single-file produce mode.",
    )

    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not show plots. Useful when called by automatic_produce.py.",
    )

    args = parser.parse_args()

    apply_screen_scale(args.scale)

    if args.mode == "explore":
        run_explore(args)

    elif args.mode == "produce":
        run_produce(args)

    else:
        raise ValueError(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
