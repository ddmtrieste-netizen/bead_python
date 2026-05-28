#!/usr/bin/env python3
"""
Live raw magnetic-field viewer for MLX90393 through MCP2221 USB-I2C bridge.

Architecture:
    Jetson/PC -> USB -> MCP2221 -> I2C -> MLX90393

This script shows a primitive but effective realtime terminal dashboard:
    - raw X, Y, Z counts
    - smoothed values
    - |B|
    - delta relative to initial baseline
    - dominant field axis
    - ASCII bars

Run:
    sudo ../../venv/bin/python scripts/live_hall_view_mcp2221.py

Optional:
    sudo ../../venv/bin/python scripts/live_hall_view_mcp2221.py --out data/hall_sensor/live_001.csv
    sudo ../../venv/bin/python scripts/live_hall_view_mcp2221.py --dt 0.30
"""

import argparse
import csv
import math
import os
import time
from pathlib import Path

import EasyMCP2221


ADDR = 0x10

CMD_SM_ALL = 0x3F
CMD_RM_ALL = 0x4F

I2C_SPEED_HZ = 100_000
MEASUREMENT_WAIT_S = 0.203


class Style:
    RESET = "\033[0m"
    WHITE = "\033[97m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"


def tag(name, color):
    return f"{color}[{name}]{Style.RESET}"


def log(name, message, color=Style.WHITE):
    print(f"{tag(name, color)} {message}")


def clear_screen():
    print("\033[2J\033[H", end="")


def s16(msb, lsb):
    value = (msb << 8) | lsb
    return value - 65536 if value & 0x8000 else value


def magnitude(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


def i2c_cmd_read(mcp, addr, cmd, nbytes):
    """
    Combined I2C transaction:
        START + addr(W) + cmd + REPEATED START + addr(R) + nbytes + STOP
    """
    mcp.I2C_write(addr, bytes([cmd]), kind="nonstop")
    return mcp.I2C_read(addr, nbytes, kind="restart")


def connect_mcp2221(retry_dt=1.0):
    while True:
        try:
            log("DEBUG", "Opening MCP2221 USB-I2C bridge...", Style.PURPLE)
            mcp = EasyMCP2221.Device()
            mcp.I2C_speed(I2C_SPEED_HZ)
            log("OK", f"MCP2221 connected. I2C = {I2C_SPEED_HZ // 1000} kHz.", Style.GREEN)
            return mcp

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            log("WARN", f"MCP2221 unavailable: {type(exc).__name__}: {exc}", Style.YELLOW)
            time.sleep(retry_dt)


def read_mlx90393_raw(mcp):
    sm_status = i2c_cmd_read(mcp, ADDR, CMD_SM_ALL, 1)[0]

    if not (sm_status & 0x20):
        raise RuntimeError(f"Measurement not accepted. SM status = 0x{sm_status:02X}")

    time.sleep(MEASUREMENT_WAIT_S)

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
        "b_raw": magnitude(x_raw, y_raw, z_raw),
        "temperature_c": temperature_c,
        "raw_bytes": data.hex(" "),
    }


def compute_baseline(mcp, n_samples):
    log("DEBUG", f"Computing baseline over {n_samples} samples...", Style.PURPLE)

    xs, ys, zs, bs = [], [], [], []

    for k in range(n_samples):
        sample = read_mlx90393_raw(mcp)
        xs.append(sample["x_raw"])
        ys.append(sample["y_raw"])
        zs.append(sample["z_raw"])
        bs.append(sample["b_raw"])

        print(
            f"\r{tag('DEBUG', Style.PURPLE)} baseline "
            f"{k + 1:03d}/{n_samples:03d} | "
            f"X={sample['x_raw']:7d} "
            f"Y={sample['y_raw']:7d} "
            f"Z={sample['z_raw']:7d}",
            end="",
            flush=True,
        )

    print()

    baseline = {
        "x": sum(xs) / len(xs),
        "y": sum(ys) / len(ys),
        "z": sum(zs) / len(zs),
        "b": sum(bs) / len(bs),
    }

    log(
        "OK",
        f"Baseline: X={baseline['x']:.1f}, "
        f"Y={baseline['y']:.1f}, "
        f"Z={baseline['z']:.1f}, "
        f"|B|={baseline['b']:.1f}",
        Style.GREEN,
    )

    time.sleep(0.8)
    return baseline


def smooth_update(previous, new, alpha):
    if previous is None:
        return dict(new)

    return {
        key: alpha * new[key] + (1.0 - alpha) * previous[key]
        for key in previous
    }


def signed_bar(value, scale, width=28):
    """
    ASCII signed bar centered around zero.

    Example:
        negative:  ████████████|..............
        positive:  ..............|████████████
    """
    if scale <= 0:
        scale = 1.0

    half = width // 2
    clipped = max(-scale, min(scale, value))
    n = int(round(abs(clipped) / scale * half))

    left_empty = "." * half
    right_empty = "." * half

    if value < 0:
        left = "." * (half - n) + "█" * n
        right = right_empty
    else:
        left = left_empty
        right = "█" * n + "." * (half - n)

    return f"{left}|{right}"


def magnitude_bar(value, scale, width=28):
    if scale <= 0:
        scale = 1.0

    clipped = max(0.0, min(scale, value))
    n = int(round(clipped / scale * width))
    return "█" * n + "." * (width - n)


def dominant_axis(x, y, z):
    values = {"X": x, "Y": y, "Z": z}
    axis = max(values, key=lambda a: abs(values[a]))
    sign = "+" if values[axis] >= 0 else "-"
    return f"{axis}{sign}"


def open_csv(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    f = path.open("a", newline="")

    fieldnames = [
        "time_s",
        "sample_id",
        "valid",
        "x_raw",
        "y_raw",
        "z_raw",
        "b_raw",
        "x_smooth",
        "y_smooth",
        "z_smooth",
        "b_smooth",
        "dx",
        "dy",
        "dz",
        "db",
        "temperature_c",
        "sm_status",
        "rm_status",
        "error",
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)

    if f.tell() == 0:
        writer.writeheader()

    log("OK", f"CSV logging: {path}", Style.GREEN)
    return f, writer


def print_dashboard(
    sample,
    smooth,
    baseline,
    sample_id,
    t,
    dt,
    scale,
    csv_enabled,
):
    x = smooth["x"]
    y = smooth["y"]
    z = smooth["z"]
    b = magnitude(x, y, z)

    dx = x - baseline["x"]
    dy = y - baseline["y"]
    dz = z - baseline["z"]
    db = b - baseline["b"]

    axis = dominant_axis(dx, dy, dz)

    clear_screen()

    print(f"{tag('LIVE', Style.PURPLE)} MLX90393 raw field viewer via MCP2221")
    print(f"{Style.DIM}{'-' * 72}{Style.RESET}")
    print(
        f"{tag('OK', Style.GREEN)} addr=0x{ADDR:02X} | "
        f"I2C={I2C_SPEED_HZ // 1000} kHz | "
        f"dt={dt:.3f} s | "
        f"sample={sample_id} | "
        f"t={t:.2f} s | "
        f"CSV={'on' if csv_enabled else 'off'}"
    )
    print()

    print(f"{Style.WHITE}Smoothed raw field counts{Style.RESET}")
    print(f"  X {x:10.1f}  {signed_bar(dx, scale)}  ΔX={dx:+10.1f}")
    print(f"  Y {y:10.1f}  {signed_bar(dy, scale)}  ΔY={dy:+10.1f}")
    print(f"  Z {z:10.1f}  {signed_bar(dz, scale)}  ΔZ={dz:+10.1f}")

    print()
    print(f"{Style.WHITE}Magnitude{Style.RESET}")
    print(f"  |B|       {b:10.1f}  {magnitude_bar(abs(db), scale)}")
    print(f"  baseline  {baseline['b']:10.1f}")
    print(f"  Δ|B|      {db:+10.1f}")

    print()
    print(f"{Style.WHITE}State{Style.RESET}")
    print(f"  dominant axis relative to baseline: {Style.CYAN}{axis}{Style.RESET}")
    print(f"  temperature: {sample['temperature_c']:.2f} °C")
    print(f"  SM=0x{sample['sm_status']:02X} | RM=0x{sample['rm_status']:02X}")

    print()
    print(f"{Style.DIM}Ctrl+C to stop. Values are raw counts, not calibrated µT/mT.{Style.RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Live terminal viewer for MLX90393 raw magnetic field through MCP2221."
    )
    parser.add_argument("--out", default=None, help="Optional CSV output path.")
    parser.add_argument("--dt", type=float, default=0.30, help="Sampling interval in seconds.")
    parser.add_argument("--n", type=int, default=0, help="Number of samples. 0 = infinite.")
    parser.add_argument("--baseline-samples", type=int, default=20, help="Initial baseline samples.")
    parser.add_argument("--alpha", type=float, default=0.25, help="Exponential smoothing factor.")
    parser.add_argument("--scale", type=float, default=12000.0, help="ASCII bar full-scale delta.")
    parser.add_argument("--reconnect-dt", type=float, default=1.0, help="Reconnect retry interval.")
    args = parser.parse_args()

    if not (0.0 < args.alpha <= 1.0):
        raise ValueError("--alpha must be in (0, 1].")

    if args.dt < MEASUREMENT_WAIT_S:
        log(
            "WARN",
            f"--dt={args.dt:.3f} s is below measurement wait {MEASUREMENT_WAIT_S:.3f} s. "
            "Effective rate will be limited.",
            Style.YELLOW,
        )

    csv_file = None
    writer = None

    if args.out:
        csv_file, writer = open_csv(args.out)

    mcp = connect_mcp2221(retry_dt=args.reconnect_dt)
    baseline = compute_baseline(mcp, args.baseline_samples)

    smooth = None
    sample_id = 0
    t0 = time.time()

    try:
        while args.n == 0 or sample_id < args.n:
            loop_start = time.time()
            t = loop_start - t0

            try:
                sample = read_mlx90393_raw(mcp)

                raw_vector = {
                    "x": sample["x_raw"],
                    "y": sample["y_raw"],
                    "z": sample["z_raw"],
                }

                smooth = smooth_update(smooth, raw_vector, args.alpha)

                print_dashboard(
                    sample=sample,
                    smooth=smooth,
                    baseline=baseline,
                    sample_id=sample_id,
                    t=t,
                    dt=args.dt,
                    scale=args.scale,
                    csv_enabled=writer is not None,
                )

                b_smooth = magnitude(smooth["x"], smooth["y"], smooth["z"])

                row = {
                    "time_s": f"{t:.6f}",
                    "sample_id": sample_id,
                    "valid": 1,
                    "x_raw": sample["x_raw"],
                    "y_raw": sample["y_raw"],
                    "z_raw": sample["z_raw"],
                    "b_raw": f"{sample['b_raw']:.6f}",
                    "x_smooth": f"{smooth['x']:.6f}",
                    "y_smooth": f"{smooth['y']:.6f}",
                    "z_smooth": f"{smooth['z']:.6f}",
                    "b_smooth": f"{b_smooth:.6f}",
                    "dx": f"{smooth['x'] - baseline['x']:.6f}",
                    "dy": f"{smooth['y'] - baseline['y']:.6f}",
                    "dz": f"{smooth['z'] - baseline['z']:.6f}",
                    "db": f"{b_smooth - baseline['b']:.6f}",
                    "temperature_c": f"{sample['temperature_c']:.6f}",
                    "sm_status": f"0x{sample['sm_status']:02X}",
                    "rm_status": f"0x{sample['rm_status']:02X}",
                    "error": "",
                }

            except KeyboardInterrupt:
                raise

            except Exception as exc:
                log("ERROR", f"Read failed: {type(exc).__name__}: {exc}", Style.RED)
                log("WARN", "Trying to reconnect MCP2221...", Style.YELLOW)

                row = {
                    "time_s": f"{t:.6f}",
                    "sample_id": sample_id,
                    "valid": 0,
                    "x_raw": "",
                    "y_raw": "",
                    "z_raw": "",
                    "b_raw": "",
                    "x_smooth": "",
                    "y_smooth": "",
                    "z_smooth": "",
                    "b_smooth": "",
                    "dx": "",
                    "dy": "",
                    "dz": "",
                    "db": "",
                    "temperature_c": "",
                    "sm_status": "",
                    "rm_status": "",
                    "error": f"{type(exc).__name__}: {exc}",
                }

                mcp = connect_mcp2221(retry_dt=args.reconnect_dt)

            if writer:
                writer.writerow(row)
                csv_file.flush()

            sample_id += 1

            elapsed = time.time() - loop_start
            time.sleep(max(0.0, args.dt - elapsed))

    except KeyboardInterrupt:
        print()
        log("WARN", "Stopped by user.", Style.YELLOW)

    finally:
        if csv_file:
            csv_file.close()
            log("OK", "CSV file closed.", Style.GREEN)


if __name__ == "__main__":
    main()
