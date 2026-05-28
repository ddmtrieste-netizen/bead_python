#!/usr/bin/env python3
"""
Acquire and plot MLX90393 magnetic field in the yz-plane through MCP2221.

Architecture:
    Jetson/PC -> USB -> MCP2221 -> I2C -> MLX90393

Quantities:
    By(t), Bz(t)
    rho_yz(t)   = sqrt(By^2 + Bz^2)
    theta_yz(t) = atan2(Bz, By)

Default behavior:
    - acquire data
    - show plots at the end
    - do not save CSV unless --out is provided
    - do not save figures unless --save-dir is provided

Plot style follows the existing bead_python scripts:
    - apply_screen_scale(scale)
    - figsize=(14, 8)
    - grid(True)
    - legend()
    - tight_layout()
"""

import argparse
import csv
import math
import time
from pathlib import Path

import EasyMCP2221
import matplotlib.pyplot as plt


# =============================================================================
# Sensor / communication constants
# =============================================================================

ADDR = 0x10

CMD_SM_ALL = 0x3F
CMD_RM_ALL = 0x4F

I2C_SPEED_HZ = 100_000
DEFAULT_MEASUREMENT_WAIT_S = 0.203


# =============================================================================
# Terminal feedback
# =============================================================================

class Style:
    RESET = "\033[0m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    PURPLE = "\033[95m"
    WHITE = "\033[97m"


def log(tag, message, color=Style.WHITE):
    print(f"{color}[{tag}]{Style.RESET} {message}")


# =============================================================================
# Plot style: consistent with existing repository scripts
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
# Low-level sensor reading
# =============================================================================

def s16(msb, lsb):
    value = (msb << 8) | lsb
    return value - 65536 if value & 0x8000 else value


def i2c_cmd_read(mcp, addr, cmd, nbytes):
    """
    Combined I2C transaction:

        START + addr(W) + cmd + REPEATED START + addr(R) + nbytes + STOP

    This repeated-start pattern is required for the MLX90393 read-measurement
    command through MCP2221.
    """
    mcp.I2C_write(addr, bytes([cmd]), kind="nonstop")
    return mcp.I2C_read(addr, nbytes, kind="restart")


def connect_mcp2221():
    log("DEBUG", "Opening MCP2221 USB-I2C bridge...", Style.PURPLE)

    mcp = EasyMCP2221.Device()
    mcp.I2C_speed(I2C_SPEED_HZ)

    log("OK", f"MCP2221 connected. I2C = {I2C_SPEED_HZ // 1000} kHz.", Style.GREEN)
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
        "raw_bytes": data.hex(" "),
    }


# =============================================================================
# Acquisition utilities
# =============================================================================

def compute_baseline(mcp, n_samples, wait_s):
    """
    Compute initial By/Bz baseline.

    If n_samples = 0, no baseline subtraction is applied.
    """
    if n_samples <= 0:
        return {"y": 0.0, "z": 0.0}

    log("DEBUG", f"Computing yz baseline over {n_samples} samples...", Style.PURPLE)

    ys = []
    zs = []

    for k in range(n_samples):
        sample = read_mlx90393_raw(mcp, wait_s)

        ys.append(sample["y_raw"])
        zs.append(sample["z_raw"])

        print(
            f"\r{Style.PURPLE}[DEBUG]{Style.RESET} "
            f"baseline {k + 1:03d}/{n_samples:03d} | "
            f"By={sample['y_raw']:9d} "
            f"Bz={sample['z_raw']:9d}",
            end="",
            flush=True,
        )

    print()

    baseline = {
        "y": sum(ys) / len(ys),
        "z": sum(zs) / len(zs),
    }

    log(
        "OK",
        f"Baseline: By0={baseline['y']:.2f}, Bz0={baseline['z']:.2f}",
        Style.GREEN,
    )

    return baseline


def acquire_yz(mcp, duration_s, dt_s, wait_s, baseline):
    t_data = []
    bx_data = []
    by_data = []
    bz_data = []
    rho_data = []
    theta_data = []
    temp_data = []
    sm_status_data = []
    rm_status_data = []

    log("DEBUG", f"Acquiring for {duration_s:.2f} s...", Style.PURPLE)

    t0 = time.time()
    sample_id = 0
    skipped = 0

    while True:
        loop_start = time.time()
        t = loop_start - t0

        if t >= duration_s:
            break

        try:
            sample = read_mlx90393_raw(mcp, wait_s)

            bx = sample["x_raw"]
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
            sm_status_data.append(sample["sm_status"])
            rm_status_data.append(sample["rm_status"])

            print(
                f"\r{Style.GREEN}[ACQ]{Style.RESET} "
                f"n={sample_id:05d} "
                f"t={t:8.3f} s | "
                f"By={by:10.1f} "
                f"Bz={bz:10.1f} "
                f"rho={rho:10.1f} "
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
            log("WARN", f"Sample skipped: {type(exc).__name__}: {exc}", Style.YELLOW)

        elapsed = time.time() - loop_start
        time.sleep(max(0.0, dt_s - elapsed))

    print()
    log("OK", f"Acquired {len(t_data)} valid samples. Skipped {skipped}.", Style.GREEN)

    return {
        "t": t_data,
        "bx": bx_data,
        "by": by_data,
        "bz": bz_data,
        "rho": rho_data,
        "theta": theta_data,
        "temperature_c": temp_data,
        "sm_status": sm_status_data,
        "rm_status": rm_status_data,
    }


# =============================================================================
# Optional saving
# =============================================================================

def save_csv(path, data, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow(["# MLX90393 yz-plane acquisition through MCP2221"])
        for key, value in metadata.items():
            writer.writerow([f"# {key}", value])

        writer.writerow([])
        writer.writerow([
            "time_s",
            "Bx_raw",
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

    log("OK", f"CSV saved: {path}", Style.GREEN)


def save_current_figure(save_dir, filename):
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    output_path = save_dir / filename
    plt.savefig(output_path, dpi=200, bbox_inches="tight")

    log("OK", f"Figure saved: {output_path}", Style.GREEN)


# =============================================================================
# Plotting
# =============================================================================

def plot_time_traces(data, title, save_dir=None):
    plt.figure(figsize=(14, 8))

    plt.plot(data["t"], data["by"], label="By")
    plt.plot(data["t"], data["bz"], label="Bz")

    plt.xlabel("t [s]")
    plt.ylabel("raw magnetic field counts")
    plt.grid(True)
    plt.legend()
    plt.title(f"{title} | By/Bz vs time")
    plt.tight_layout()

    if save_dir is not None:
        save_current_figure(save_dir, "hall_yz_time_traces.png")

def plot_bx_trace(data, title, save_dir=None):
    plt.figure(figsize=(14, 8))

    plt.plot(data["t"], data["bx"], label="Bx")

    plt.xlabel("t [s]")
    plt.ylabel("raw magnetic field counts")
    plt.grid(True)
    plt.legend()
    plt.title(f"{title} | Bx vs time")
    plt.tight_layout()

    if save_dir is not None:
        save_current_figure(save_dir, "hall_bx_time_trace.png")


def plot_polar_yz(data, title, save_dir=None):
    fig = plt.figure(figsize=(14, 8))
    ax = fig.add_subplot(111, projection="polar")

    ax.plot(data["theta"], data["rho"], marker=".", linestyle="-")

    ax.set_title(f"{title} | polar field in yz plane")
    ax.set_theta_zero_location("E")   # theta = 0 along +By
    ax.set_theta_direction(1)         # positive theta toward +Bz
    ax.grid(True)

    plt.tight_layout()

    if save_dir is not None:
        save_current_figure(save_dir, "hall_yz_polar.png")


def plot_results(data, title, save_dir=None):
    if len(data["t"]) == 0:
        log("ERROR", "No valid samples to plot.", Style.RED)
        return

    plot_time_traces(data, title, save_dir=save_dir)
    plot_bx_trace(data, title, save_dir=save_dir)

    plt.show()


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Acquire and plot MLX90393 magnetic field in the yz-plane via MCP2221."
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Acquisition duration in seconds.",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.25,
        help="Requested sampling interval in seconds.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=DEFAULT_MEASUREMENT_WAIT_S,
        help="Wait between SM and RM commands.",
    )
    parser.add_argument(
        "--baseline-samples",
        type=int,
        default=0,
        help="Initial samples used to subtract By/Bz baseline. Default: 0.",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.6,
        help="Visual scale factor, consistent with existing plotting scripts.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional CSV output path. Default: no CSV saving.",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default=None,
        help="Optional folder where figures are saved. Default: no figure saving.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Hall yz field",
        help="Plot title prefix.",
    )
    parser.add_argument(
        "--motor-speed",
        type=str,
        default=None,
        help="Optional motor speed metadata.",
    )
    parser.add_argument(
        "--motor-speed-unit",
        type=str,
        default=None,
        help="Optional motor speed unit metadata, e.g. rpm, Hz, steps/s.",
    )

    args = parser.parse_args()

    apply_screen_scale(args.scale)

    if args.dt < args.wait:
        log(
            "WARN",
            f"--dt={args.dt:.3f} s is smaller than --wait={args.wait:.3f} s. "
            "Effective sampling will be slower.",
            Style.YELLOW,
        )

    mcp = connect_mcp2221()

    baseline = compute_baseline(
        mcp=mcp,
        n_samples=args.baseline_samples,
        wait_s=args.wait,
    )

    data = acquire_yz(
        mcp=mcp,
        duration_s=args.duration,
        dt_s=args.dt,
        wait_s=args.wait,
        baseline=baseline,
    )

    metadata = {
        "address": f"0x{ADDR:02X}",
        "i2c_speed_hz": I2C_SPEED_HZ,
        "duration_s": args.duration,
        "dt_s": args.dt,
        "measurement_wait_s": args.wait,
        "baseline_samples": args.baseline_samples,
        "baseline_by": baseline["y"],
        "baseline_bz": baseline["z"],
        "motor_speed": args.motor_speed if args.motor_speed is not None else "",
        "motor_speed_unit": args.motor_speed_unit if args.motor_speed_unit is not None else "",
    }

    if args.out is not None:
        save_csv(args.out, data, metadata)
    else:
        log("DEBUG", "CSV saving disabled. Use --out to save data.", Style.PURPLE)

    if args.save_dir is None:
        log("DEBUG", "Figure saving disabled. Use --save-dir to save plots.", Style.PURPLE)

    plot_results(
        data=data,
        title=args.title,
        save_dir=args.save_dir,
    )


if __name__ == "__main__":
    main()
