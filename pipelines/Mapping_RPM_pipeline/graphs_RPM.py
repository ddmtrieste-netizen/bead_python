# pipelines/Mapping_RPM_pipeline/graphs_RPM.py

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


# =============================================================================
# IO
# =============================================================================

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
    return Path(data_dir) / f"{speed}_RPM.csv"


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


# =============================================================================
# Plot style
# =============================================================================

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


# =============================================================================
# Signal utilities
# =============================================================================

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


# =============================================================================
# FFT core
# =============================================================================

def estimate_fft_raw(t, signal, fmin=0.0, fmax=None):
    """
    FFT sull'intero segnale.

    Ritorna:
        rpm       frequenza dominante in cicli/min
        freq_hz   frequenza dominante in Hz
        freqs     asse frequenze
        spectrum  ampiezza FFT
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

    # Resampling uniforme: utile perché il timestamp reale della camera può jitterare.
    t_uniform = np.linspace(t[0], t[-1], n_uniform)
    signal_uniform = np.interp(t_uniform, t, signal)

    # Rimozione componente media/DC.
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

    peak_index = np.argmax(spectrum_selected)

    freq_hz = freqs_selected[peak_index]
    rpm = 60.0 * freq_hz

    return rpm, freq_hz, freqs, spectrum


def compute_bin_ffts(t, signal, bin_sec=20.0, fmin=0.0, fmax=None):
    """
    Divide il segnale in bin non-overlapping.
    Per ogni bin calcola:
        - FFT
        - picco dominante
        - RPM equivalente

    Ritorna una lista di dizionari, uno per bin valido.
    """

    t, signal = clean_and_sort_time_signal(t, signal)

    if len(t) < 4:
        return []

    t0 = t[0]
    t1 = t[-1]
    duration = t1 - t0

    if duration <= 0:
        return []

    bins = []

    # Se il file è più corto del bin richiesto, faccio una sola FFT.
    if duration < bin_sec:
        rpm, freq_hz, freqs, spectrum = estimate_fft_raw(
            t,
            signal,
            fmin=fmin,
            fmax=fmax,
        )

        if np.isfinite(rpm):
            bins.append({
                "start": t0,
                "end": t1,
                "rpm": rpm,
                "freq_hz": freq_hz,
                "freqs": freqs,
                "spectrum": spectrum,
            })

        return bins

    start = t0

    while start + bin_sec <= t1:
        end = start + bin_sec
        mask = (t >= start) & (t < end)

        if np.count_nonzero(mask) >= 4:
            rpm, freq_hz, freqs, spectrum = estimate_fft_raw(
                t[mask],
                signal[mask],
                fmin=fmin,
                fmax=fmax,
            )

            if np.isfinite(rpm):
                bins.append({
                    "start": start,
                    "end": end,
                    "rpm": rpm,
                    "freq_hz": freq_hz,
                    "freqs": freqs,
                    "spectrum": spectrum,
                })

        start = end

    return bins


def estimate_fft_bins(t, signal, bin_sec=20.0, fmin=0.0, fmax=None):
    """
    Stima finale con bin non-overlapping.

    Per ogni bin si prende il picco FFT.
    Come valore rappresentativo finale si usa la mediana degli RPM dei bin.
    """

    bins = compute_bin_ffts(
        t,
        signal,
        bin_sec=bin_sec,
        fmin=fmin,
        fmax=fmax,
    )

    if len(bins) == 0:
        return np.nan, np.nan, []

    bin_rpms = np.asarray([b["rpm"] for b in bins], dtype=float)

    rpm_median = float(np.median(bin_rpms))
    rpm_std = float(np.std(bin_rpms))

    return rpm_median, rpm_std, list(bin_rpms)


def aggregate_bin_spectra(bins, aggregate="mean"):
    """
    Aggrega gli spettri FFT dei singoli bin.

    Questo produce uno spettro simile alla raw FFT come assi:
        x = frequency [Hz]
        y = aggregated FFT amplitude

    aggregate:
        "mean"  consigliato, scala più confrontabile
        "sum"   somma pura degli spettri
    """

    if len(bins) == 0:
        return np.array([]), np.array([])

    freq_common = bins[0]["freqs"]

    if len(freq_common) == 0:
        return np.array([]), np.array([])

    spectra = []

    for b in bins:
        freqs = b["freqs"]
        spectrum = b["spectrum"]

        if len(freqs) == 0 or len(spectrum) == 0:
            continue

        spectrum_interp = np.interp(
            freq_common,
            freqs,
            spectrum,
            left=0.0,
            right=0.0,
        )

        spectra.append(spectrum_interp)

    if len(spectra) == 0:
        return np.array([]), np.array([])

    spectra = np.asarray(spectra, dtype=float)

    if aggregate == "mean":
        spectrum_agg = np.mean(spectra, axis=0)

    elif aggregate == "sum":
        spectrum_agg = np.sum(spectra, axis=0)

    else:
        raise ValueError(f"Unknown aggregate: {aggregate}")

    return freq_common, spectrum_agg


# =============================================================================
# Atomic analysis: one file
# =============================================================================

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
    Analisi atomica:
        speed -> speed_RPM.csv -> valore RPM stimato

    Se speed non è specificata, usa speed=5.
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
        final_bin_sec = np.nan

    elif method == "bins":
        bead_rpm, bead_rpm_std, bin_rpms = estimate_fft_bins(
            t,
            signal,
            bin_sec=bin_sec,
            fmin=fmin,
            fmax=fmax,
        )

        n_bins = len(bin_rpms)
        final_bin_sec = float(bin_sec)

    else:
        raise ValueError(f"Unknown method: {method}")

    duration_s = float(t[-1] - t[0]) if len(t) > 1 else np.nan

    return {
        "steps_per_second": int(speed),
        "file": str(file_path),
        "method": method,
        "signal": signal_name,
        "bead_rpm_fft": bead_rpm,
        "bead_rpm_fft_std": bead_rpm_std,
        "duration_s": duration_s,
        "n_points": int(len(t)),
        "n_bins": int(n_bins),
        "bin_sec": final_bin_sec,
    }


# =============================================================================
# Modes
# =============================================================================

def run_explore(args):
    """
    Modalità esplorativa.
    Volutamente semplice:
        - traiettoria x-y
        - x(t), y(t)
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
        return

    plt.figure(figsize=(14, 8))
    plt.plot(x, y)
    plt.xlabel("x [px]")
    plt.ylabel("y [px]")
    plt.axis("equal")
    plt.grid(True)
    plt.title(f"Bead trajectory | speed = {args.speed}")
    plt.tight_layout()

    plt.figure(figsize=(14, 8))
    plt.plot(t, x, label="x")
    plt.plot(t, y, label="y")
    plt.xlabel("t [s]")
    plt.ylabel("position [px]")
    plt.grid(True)
    plt.legend()
    plt.title(f"Position vs time | speed = {args.speed}")
    plt.tight_layout()

    plt.show()


def run_produce(args):
    """
    Modalità produce.
    Analizza un solo file e mostra la diagnostica FFT.
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
        f"n_bins={result['n_bins']} "
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
        bins = compute_bin_ffts(
            t,
            signal,
            bin_sec=args.bin_sec,
            fmin=args.fmin,
            fmax=args.fmax,
        )

        if len(bins) == 0:
            print("No valid bins found.")
            return

        bin_rpms = np.asarray([b["rpm"] for b in bins], dtype=float)
        bin_starts = np.asarray([b["start"] - bins[0]["start"] for b in bins], dtype=float)

        rpm_median = float(np.median(bin_rpms))
        rpm_std = float(np.std(bin_rpms))

        # Plot 1: picco dominante per ogni bin.
        plt.figure(figsize=(14, 8))
        plt.plot(bin_starts, bin_rpms, marker="o")
        plt.xlabel("bin start time [s]")
        plt.ylabel("bead dominant frequency [cycles/min]")
        plt.grid(True)
        plt.title(
            f"Binned FFT peaks | speed = {args.speed} | "
            f"median = {rpm_median:.4g}, std = {rpm_std:.4g}, "
            f"bin = {args.bin_sec:g}s"
        )
        plt.tight_layout()

        # Plot 2: spettro aggregato dei bin.
        freqs_agg, spectrum_agg = aggregate_bin_spectra(
            bins,
            aggregate=args.bin_spectrum_aggregate,
        )

        if len(freqs_agg) > 0 and len(spectrum_agg) > 0:
            peak_index = np.argmax(spectrum_agg)
            peak_freq = freqs_agg[peak_index]
            peak_rpm = 60.0 * peak_freq

            plt.figure(figsize=(14, 8))
            plt.plot(freqs_agg, spectrum_agg)
            plt.xlabel("frequency [Hz]")
            plt.ylabel(f"{args.bin_spectrum_aggregate} FFT amplitude")
            plt.grid(True)
            plt.title(
                f"Aggregated binned FFT spectrum | speed = {args.speed} | "
                f"peak = {peak_freq:.4g} Hz = {peak_rpm:.4g} cycles/min"
            )
            plt.tight_layout()

        else:
            print("No valid aggregated binned spectrum.")

    plt.show()


# =============================================================================
# Main
# =============================================================================

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
        "--bin-spectrum-aggregate",
        type=str,
        default="mean",
        choices=["mean", "sum"],
        help="How to aggregate FFT spectra from bins.",
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
