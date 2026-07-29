#!/usr/bin/env python3
"""
Map commanded motor RPM to measured magnetic-field rotation speed.

Architecture:
    Jetson/PC
      ├── serial USB -> Arduino motor controller
      └── USB -> MCP2221 -> I2C -> MLX90393 Hall sensor

For each imposed motor speed:
    1. send speed command to Arduino
    2. acquire Bx, By, Bz from MLX90393
    3. compute yz-plane field:
           rho_yz   = sqrt(By^2 + Bz^2)
           theta_yz = atan2(Bz, By)
    4. estimate magnetic-field rotation speed using:
           a) unwrapped theta slope
           b) FFT of complex signal By + i Bz
    5. save per-speed CSV
    6. save summary CSV

Inspired by:
    pipelines/Mapping_RPM_pipeline/mapping_RPM.py

Default Arduino protocol:
    send "<speed>\\n"
"""

import argparse
import csv
import math
import threading
import time
from pathlib import Path

import EasyMCP2221
import matplotlib.pyplot as plt
import numpy as np
import serial


# =============================================================================
# Sensor constants
# =============================================================================

ADDR = 0x10
CMD_SM_ALL = 0x3F
CMD_RM_ALL = 0x4F

I2C_SPEED_HZ = 100_000
DEFAULT_MEASUREMENT_WAIT_S = 0.203


# =============================================================================
# Cosmetics, coherent with mapping_RPM.py
# =============================================================================

ROSSO = "\033[31m"
VERDE = "\033[32m"
GIALLO = "\033[33m"
BLU = "\033[34m"
RESET = "\033[0m"
VIOLA = "\033[35m"


def msg(tag, text, color=RESET):
    print(f"{color}[{tag}] {text}{RESET}")


# =============================================================================
# Plot style, coherent with existing repo scripts
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
# Arduino serial
# =============================================================================

def read_from_arduino(ser, stop_event):
    """Read Arduino messages in a background thread."""
    while ser.is_open and not stop_event.is_set():
        try:
            if ser.in_waiting > 0:
                data = ser.readline().decode("utf-8", errors="ignore").strip()
                if data:
                    print(f"\n{VIOLA}[ARDUINO]{RESET} {data}")
        except Exception as exc:
            print(f"\n{GIALLO}[WARN] Arduino read error: {exc}{RESET}")
            break

        time.sleep(0.01)


def open_arduino(port, baud):
    msg("DEBUG", f"Opening Arduino serial port {port} at {baud} baud...", VIOLA)
    ser = serial.Serial(port, baud, timeout=1)
    time.sleep(2.0)
    msg("OK", f"Arduino connected on {port}.", VERDE)
    return ser


def send_speed_command(ser, speed, command_template):
    """
    Send speed command to Arduino.

    Default command_template = "{speed}\\n"
    Example:
        speed = 30 -> "30\\n"
    """
    command = command_template.format(speed=speed)
    ser.write(command.encode("utf-8"))
    ser.flush()
    msg("ARDUINO", f"sent command: {command.strip()}", VIOLA)


def stop_motor(ser, command_template):
    """Best-effort stop that never masks an acquisition error."""
    if ser is None or not ser.is_open:
        return

    try:
        send_speed_command(ser, 0, command_template)
        msg("OK", "Motor stop command sent.", VERDE)
    except Exception as exc:
        msg("WARN", f"Could not send motor stop command: {exc}", GIALLO)


# =============================================================================
# MLX90393 through MCP2221
# =============================================================================

def s16(msb, lsb):
    value = (msb << 8) | lsb
    return value - 65536 if value & 0x8000 else value


def i2c_cmd_read(mcp, addr, cmd, nbytes):
    """
    Combined I2C transaction:
        START + addr(W) + cmd + REPEATED START + addr(R) + nbytes + STOP
    """
    mcp.I2C_write(addr, bytes([cmd]), kind="nonstop")
    return mcp.I2C_read(addr, nbytes, kind="restart")


def connect_mcp2221():
    msg("DEBUG", "Opening MCP2221 USB-I2C bridge...", VIOLA)
    mcp = EasyMCP2221.Device()
    mcp.I2C_speed(I2C_SPEED_HZ)
    msg("OK", f"MCP2221 connected. I2C = {I2C_SPEED_HZ // 1000} kHz.", VERDE)
    return mcp


def read_mlx90393_raw(mcp, wait_s):
    sm_status = i2c_cmd_read(mcp, ADDR, CMD_SM_ALL, 1)[0]

    if not (sm_status & 0x20):
        raise RuntimeError(f"Measurement not accepted. SM status = 0x{sm_status:02X}")

    time.sleep(wait_s)

    data = i2c_cmd_read(mcp, ADDR, CMD_RM_ALL, 9)

    if len(data) != 9:
        raise RuntimeError(f"Expected 9 bytes, received {len(data)} bytes.")

    rm_status = data[0]

    t_raw = (data[1] << 8) | data[2]
    x_raw = s16(data[3], data[4])
    y_raw = s16(data[5], data[6])
    z_raw = s16(data[7], data[8])

    temperature_c = t_raw / 45.2 + (25 - 46244 / 45.2)

    return {
        "sm_status": sm_status,
        "rm_status": rm_status,
        "t_raw": t_raw,
        "x_raw": x_raw,
        "y_raw": y_raw,
        "z_raw": z_raw,
        "temperature_c": temperature_c,
    }


# =============================================================================
# Acquisition
# =============================================================================

def compute_baseline(mcp, n_samples, wait_s):
    if n_samples <= 0:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    msg("DEBUG", f"Computing baseline over {n_samples} samples...", VIOLA)

    xs, ys, zs = [], [], []

    for k in range(n_samples):
        sample = read_mlx90393_raw(mcp, wait_s)

        xs.append(sample["x_raw"])
        ys.append(sample["y_raw"])
        zs.append(sample["z_raw"])

        print(
            f"\r{VIOLA}[BASELINE]{RESET} "
            f"{k + 1:03d}/{n_samples:03d} | "
            f"Bx={sample['x_raw']:9d} "
            f"By={sample['y_raw']:9d} "
            f"Bz={sample['z_raw']:9d}",
            end="",
            flush=True,
        )

    print()

    baseline = {
        "x": float(np.mean(xs)),
        "y": float(np.mean(ys)),
        "z": float(np.mean(zs)),
    }

    msg(
        "OK",
        f"Baseline: Bx0={baseline['x']:.2f}, "
        f"By0={baseline['y']:.2f}, "
        f"Bz0={baseline['z']:.2f}",
        VERDE,
    )

    return baseline


def acquire_field(mcp, speed, duration_s, dt_s, wait_s, baseline):
    """
    Acquire Hall data for one imposed Arduino speed.
    """
    t_data = []
    bx_data = []
    by_data = []
    bz_data = []
    rho_data = []
    theta_data = []
    temp_data = []
    sm_data = []
    rm_data = []

    msg("TRACKER", f"Magnetic acquisition started for speed={speed}.", VIOLA)

    t0 = time.monotonic()
    sample_id = 0
    skipped = 0

    while True:
        loop_start = time.monotonic()
        t = loop_start - t0

        if t >= duration_s:
            break

        try:
            sample = read_mlx90393_raw(mcp, wait_s)

            bx = sample["x_raw"] - baseline["x"]
            by = sample["y_raw"] - baseline["y"]
            bz = sample["z_raw"] - baseline["z"]

            rho = math.sqrt(by * by + bz * bz)
            theta = math.atan2(bz, by)

            t_data.append(t)
            bx_data.append(bx)
            by_data.append(by)
            bz_data.append(bz)
            rho_data.append(rho)
            theta_data.append(theta)
            temp_data.append(sample["temperature_c"])
            sm_data.append(sample["sm_status"])
            rm_data.append(sample["rm_status"])

            print(
                f"\r{VERDE}[ACQ]{RESET} "
                f"speed={speed} "
                f"n={sample_id:05d} "
                f"t={t:8.3f}/{duration_s:.1f} s | "
                f"By={by:10.1f} "
                f"Bz={bz:10.1f} "
                f"theta={math.degrees(theta):8.2f} deg",
                end="",
                flush=True,
            )

            sample_id += 1

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            skipped += 1
            print()
            msg("WARN", f"Sample skipped: {type(exc).__name__}: {exc}", GIALLO)

        elapsed = time.monotonic() - loop_start
        time.sleep(max(0.0, dt_s - elapsed))

    print()
    msg("OK", f"Acquired {len(t_data)} valid samples for speed={speed}. Skipped {skipped}.", VERDE)

    return {
        "motor_rpm_command": speed,
        "t": np.asarray(t_data, dtype=float),
        "bx": np.asarray(bx_data, dtype=float),
        "by": np.asarray(by_data, dtype=float),
        "bz": np.asarray(bz_data, dtype=float),
        "rho": np.asarray(rho_data, dtype=float),
        "theta": np.asarray(theta_data, dtype=float),
        "temperature_c": np.asarray(temp_data, dtype=float),
        "sm_status": np.asarray(sm_data, dtype=int),
        "rm_status": np.asarray(rm_data, dtype=int),
        "skipped": skipped,
    }


# =============================================================================
# Frequency / RPM analysis
# =============================================================================

def estimate_rotation_from_theta(t, by, bz):
    """
    Estimate rotation frequency from unwrapped theta(t).

    theta = atan2(Bz, By)
    omega = slope(theta_unwrapped)
    f = omega / (2*pi)
    rpm = f * 60

    Signed rpm:
        positive if theta increases with time
        negative if theta decreases with time
    """
    if len(t) < 5:
        return {
            "theta_hz": np.nan,
            "theta_rpm": np.nan,
            "theta_r2": np.nan,
        }

    theta = np.unwrap(np.arctan2(bz, by))

    coeff = np.polyfit(t, theta, 1)
    omega = coeff[0]
    theta_fit = np.polyval(coeff, t)

    residual = theta - theta_fit
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((theta - np.mean(theta)) ** 2))

    if ss_tot > 0:
        r2 = 1.0 - ss_res / ss_tot
    else:
        r2 = np.nan

    hz = omega / (2.0 * math.pi)
    rpm = hz * 60.0

    return {
        "theta_hz": hz,
        "theta_rpm": rpm,
        "theta_r2": r2,
    }


def estimate_rotation_from_fft(t, by, bz):
    """
    Estimate dominant frequency from complex yz signal:
        q(t) = By(t) + i Bz(t)

    Uses uniform interpolation because acquisition timing is not perfectly uniform.
    """
    if len(t) < 8:
        return {
            "fft_hz": np.nan,
            "fft_rpm": np.nan,
            "fft_peak_amp": np.nan,
        }

    duration = t[-1] - t[0]
    if duration <= 0:
        return {
            "fft_hz": np.nan,
            "fft_rpm": np.nan,
            "fft_peak_amp": np.nan,
        }

    n = len(t)
    dt_uniform = duration / (n - 1)
    tu = np.linspace(t[0], t[-1], n)

    byu = np.interp(tu, t, by)
    bzu = np.interp(tu, t, bz)

    q = byu + 1j * bzu
    q = q - np.mean(q)

    freqs = np.fft.fftfreq(n, d=dt_uniform)
    Q = np.fft.fft(q)

    # The sign carries the direction of rotation for q = By + i*Bz.
    # Looking only at positive frequencies produces a false high-frequency
    # peak when the field rotates in the opposite direction.
    mask = freqs != 0

    if not np.any(mask):
        return {
            "fft_hz": np.nan,
            "fft_rpm": np.nan,
            "fft_peak_amp": np.nan,
        }

    freqs_selected = freqs[mask]
    amplitudes_selected = np.abs(Q[mask])

    idx = int(np.argmax(amplitudes_selected))
    hz = float(freqs_selected[idx])
    rpm = hz * 60.0
    peak_amp = float(amplitudes_selected[idx])

    return {
        "fft_hz": hz,
        "fft_rpm": rpm,
        "fft_peak_amp": peak_amp,
    }


def analyze_run(data):
    t = data["t"]
    by = data["by"]
    bz = data["bz"]
    rho = data["rho"]

    theta_est = estimate_rotation_from_theta(t, by, bz)
    fft_est = estimate_rotation_from_fft(t, by, bz)

    if len(t) >= 2:
        effective_fs = (len(t) - 1) / (t[-1] - t[0])
    else:
        effective_fs = np.nan

    summary = {
        "motor_rpm_command": data["motor_rpm_command"],
        "n_samples": len(t),
        "skipped": data["skipped"],
        "duration_actual_s": float(t[-1] - t[0]) if len(t) >= 2 else np.nan,
        "effective_fs_hz": effective_fs,
        "by_mean": float(np.mean(by)) if len(by) else np.nan,
        "bz_mean": float(np.mean(bz)) if len(bz) else np.nan,
        "rho_mean": float(np.mean(rho)) if len(rho) else np.nan,
        "rho_std": float(np.std(rho)) if len(rho) else np.nan,
        **theta_est,
        **fft_est,
    }

    return summary


# =============================================================================
# Saving
# =============================================================================

def speed_to_label(speed):
    return str(speed).replace(".", "p").replace("-", "m")


def save_run_csv(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "time_s",
            "motor_rpm_command",
            "Bx_raw_plane",
            "By_raw_plane",
            "Bz_raw_plane",
            "rho_yz_raw",
            "theta_yz_rad",
            "theta_yz_deg",
            "temperature_c",
            "sm_status",
            "rm_status",
        ])

        for i in range(len(data["t"])):
            writer.writerow([
                f"{data['t'][i]:.6f}",
                data["motor_rpm_command"],
                f"{data['bx'][i]:.6f}",
                f"{data['by'][i]:.6f}",
                f"{data['bz'][i]:.6f}",
                f"{data['rho'][i]:.6f}",
                f"{data['theta'][i]:.9f}",
                f"{math.degrees(data['theta'][i]):.6f}",
                f"{data['temperature_c'][i]:.6f}",
                f"0x{data['sm_status'][i]:02X}",
                f"0x{data['rm_status'][i]:02X}",
            ])

    msg("OK", f"Saved run CSV: {path}", VERDE)


def save_summary_csv(path, summaries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not summaries:
        msg("WARN", "No summaries to save.", GIALLO)
        return

    fieldnames = list(summaries[0].keys())

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    msg("OK", f"Saved summary CSV: {path}", VERDE)


# =============================================================================
# Plotting
# =============================================================================

def plot_summary(summaries, output_dir=None):
    if not summaries:
        return

    speeds = np.asarray([s["motor_rpm_command"] for s in summaries], dtype=float)
    theta_rpm = np.asarray([s["theta_rpm"] for s in summaries], dtype=float)
    fft_rpm = np.asarray([s["fft_rpm"] for s in summaries], dtype=float)
    rho_mean = np.asarray([s["rho_mean"] for s in summaries], dtype=float)
    rho_std = np.asarray([s["rho_std"] for s in summaries], dtype=float)
    r2 = np.asarray([s["theta_r2"] for s in summaries], dtype=float)

    # Plot 1: commanded motor RPM vs measured field RPM
    plt.figure(figsize=(14, 8))
    plt.plot(speeds, theta_rpm, "o-", label="theta-slope estimate")
    plt.plot(speeds, fft_rpm, "s-", label="FFT estimate")
    plt.xlabel("commanded motor speed [RPM]")
    plt.ylabel("measured field rotation [rpm]")
    plt.title("Magnetic field rotation vs imposed motor speed")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    if output_dir is not None:
        path = Path(output_dir) / "field_rpm_vs_command.png"
        plt.savefig(path, dpi=200, bbox_inches="tight")
        msg("OK", f"Saved figure: {path}", VERDE)

    # Plot 2: mean field intensity vs speed
    plt.figure(figsize=(14, 8))
    plt.errorbar(speeds, rho_mean, yerr=rho_std, fmt="o-", capsize=4, label="rho_yz")
    plt.xlabel("commanded motor speed [RPM]")
    plt.ylabel("rho_yz raw counts")
    plt.title("Mean yz-field intensity vs imposed motor speed")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    if output_dir is not None:
        path = Path(output_dir) / "rho_yz_vs_command.png"
        plt.savefig(path, dpi=200, bbox_inches="tight")
        msg("OK", f"Saved figure: {path}", VERDE)

    # Plot 3: theta fit quality
    plt.figure(figsize=(14, 8))
    plt.plot(speeds, r2, "o-", label="theta linear-fit R²")
    plt.xlabel("commanded motor speed [RPM]")
    plt.ylabel("R²")
    plt.title("Quality of angular rotation estimate")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    if output_dir is not None:
        path = Path(output_dir) / "theta_fit_quality_vs_command.png"
        plt.savefig(path, dpi=200, bbox_inches="tight")
        msg("OK", f"Saved figure: {path}", VERDE)

    plt.show()


# =============================================================================
# Main
# =============================================================================

def parse_speeds(args):
    if args.speeds:
        return [float(s) for s in args.speeds]

    if args.speed_start is None or args.speed_stop is None:
        raise ValueError("Provide either --speeds or --speed-start/--speed-stop.")

    step = args.speed_step
    if step == 0:
        raise ValueError("--speed-step cannot be zero.")

    speeds = []
    value = args.speed_start

    if step > 0:
        while value <= args.speed_stop + 1e-12:
            speeds.append(float(value))
            value += step
    else:
        while value >= args.speed_stop - 1e-12:
            speeds.append(float(value))
            value += step

    return speeds


def main():
    parser = argparse.ArgumentParser(
        description="Map commanded motor RPM to magnetic-field rotation speed."
    )

    # Arduino
    parser.add_argument("--arduino-port", default="/dev/ttyACM1", help="Arduino serial port.")
    parser.add_argument("--baud", type=int, default=9600, help="Arduino serial baud rate.")
    parser.add_argument(
        "--command-template",
        default="{speed}\n",
        help='Command sent to Arduino. Default: "{speed}\\n".',
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=2.0,
        help="Settling time after sending each speed command.",
    )

    # Speed sweep
    parser.add_argument("--speeds", nargs="*", default=None, help="Explicit motor RPM values.")
    parser.add_argument("--speed-start", type=float, default=1.0, help="Starting motor RPM.")
    parser.add_argument("--speed-stop", type=float, default=20.0, help="Final motor RPM.")
    parser.add_argument("--speed-step", type=float, default=1.0, help="Motor RPM increment.")

    # Acquisition
    parser.add_argument("--duration", type=float, default=30.0, help="Recording time per speed.")
    parser.add_argument("--dt", type=float, default=0.25, help="Requested sampling interval.")
    parser.add_argument("--wait", type=float, default=DEFAULT_MEASUREMENT_WAIT_S, help="SM/RM wait time.")
    parser.add_argument("--baseline-samples", type=int, default=20, help="Initial baseline samples.")

    # Output
    parser.add_argument(
        "--output-dir",
        default="data/processed/mapping_Hall_RPM",
        help="Output folder.",
    )
    parser.add_argument(
        "--no-save-runs",
        action="store_true",
        help="Do not save per-speed raw CSV files.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Do not show summary plots.",
    )
    parser.add_argument(
        "--save-plots",
        action="store_true",
        help="Save summary plots in output folder.",
    )
    parser.add_argument("--scale", type=float, default=1.6, help="Plot scale factor.")

    args = parser.parse_args()

    if args.duration <= 0:
        parser.error("--duration must be positive.")
    if args.dt <= 0:
        parser.error("--dt must be positive.")
    if args.wait < 0:
        parser.error("--wait cannot be negative.")
    if args.baseline_samples < 0:
        parser.error("--baseline-samples cannot be negative.")

    apply_screen_scale(args.scale)

    if args.dt < args.wait:
        msg(
            "WARN",
            f"--dt={args.dt:.3f} is smaller than --wait={args.wait:.3f}. "
            "Effective sampling will be slower.",
            GIALLO,
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    speeds = parse_speeds(args)
    msg("DEBUG", f"Speed list: {speeds}", VIOLA)

    stop_event = threading.Event()
    ser = None

    summaries = []

    try:
        ser = open_arduino(args.arduino_port, args.baud)

        read_thread = threading.Thread(
            target=read_from_arduino,
            args=(ser, stop_event),
            daemon=True,
        )
        read_thread.start()

        mcp = connect_mcp2221()

        baseline = compute_baseline(
            mcp=mcp,
            n_samples=args.baseline_samples,
            wait_s=args.wait,
        )

        for speed in speeds:
            msg("DEBUG", f"Starting speed condition: {speed}", VIOLA)

            send_speed_command(
                ser=ser,
                speed=speed,
                command_template=args.command_template,
            )

            if args.settle > 0:
                msg("DEBUG", f"Settling for {args.settle:.2f} s...", VIOLA)
                time.sleep(args.settle)

            data = acquire_field(
                mcp=mcp,
                speed=speed,
                duration_s=args.duration,
                dt_s=args.dt,
                wait_s=args.wait,
                baseline=baseline,
            )

            summary = analyze_run(data)
            summaries.append(summary)

            msg(
                "RESULT",
                f"speed={speed} | "
                f"theta_rpm={summary['theta_rpm']:.3f} | "
                f"fft_rpm={summary['fft_rpm']:.3f} | "
                f"rho_mean={summary['rho_mean']:.1f} | "
                f"R2={summary['theta_r2']:.3f}",
                VERDE,
            )

            if not args.no_save_runs:
                label = speed_to_label(speed)
                run_path = output_dir / f"{label}_CMD_hall.csv"
                save_run_csv(run_path, data)

        # Do not leave the stator energized while saving or showing plots.
        stop_motor(ser, args.command_template)

        summary_path = output_dir / "summary_hall_RPM.csv"
        save_summary_csv(summary_path, summaries)

        if not args.no_plots:
            plot_summary(
                summaries,
                output_dir=output_dir if args.save_plots else None,
            )

    except serial.SerialException as exc:
        msg("ERROR", f"Arduino serial error: {exc}", ROSSO)

    except KeyboardInterrupt:
        print()
        msg("WARN", "Program interrupted by user.", GIALLO)

    finally:
        stop_event.set()

        stop_motor(ser, args.command_template)

        if ser is not None and ser.is_open:
            ser.close()
            msg("OK", "Arduino serial port closed.", VERDE)


if __name__ == "__main__":
    main()
