#!/usr/bin/env python3
"""
Test MLX90393 magnetic sensor through MCP2221 USB-I2C bridge.

Architecture:
    Jetson/PC -> USB -> MCP2221 -> I2C -> MLX90393

This is a diagnostic script. It reads raw magnetic field counts from the
MLX90393 using the same repeated-start transaction pattern used by the
working C implementation.

Usage:
    sudo ../../venv/bin/python scripts/test_mlx90393_mcp2221.py

Optional:
    sudo ../../venv/bin/python scripts/test_mlx90393_mcp2221.py --out data/hall_sensor/test_001.csv
    sudo ../../venv/bin/python scripts/test_mlx90393_mcp2221.py --n 100 --dt 0.25
"""

import argparse
import csv
import time
from pathlib import Path

import EasyMCP2221


ADDR = 0x10

CMD_SM_ALL = 0x3F   # Start measurement: T + X + Y + Z
CMD_RM_ALL = 0x4F   # Read measurement:  T + X + Y + Z

I2C_SPEED_HZ = 100_000
MEASUREMENT_WAIT_S = 0.203


class Style:
    RESET = "\033[0m"
    WHITE = "\033[97m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    PURPLE = "\033[95m"
    DIM = "\033[2m"


def log(tag, message, color=Style.WHITE):
    print(f"{color}[{tag}]{Style.RESET} {message}")


def debug(message):
    log("DEBUG", message, Style.PURPLE)


def ok(message):
    log("OK", message, Style.GREEN)


def warn(message):
    log("WARN", message, Style.YELLOW)


def error(message):
    log("ERROR", message, Style.RED)


def s16(msb, lsb):
    """Convert two big-endian bytes to signed int16."""
    value = (msb << 8) | lsb
    return value - 65536 if value & 0x8000 else value


def connect_mcp2221(retry_dt=1.0):
    """Open MCP2221 and configure I2C speed. Retry until available."""
    while True:
        try:
            debug("Opening MCP2221 USB-I2C bridge...")
            mcp = EasyMCP2221.Device()
            mcp.I2C_speed(I2C_SPEED_HZ)
            ok(f"MCP2221 connected. I2C speed set to {I2C_SPEED_HZ // 1000} kHz.")
            return mcp

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            warn(f"MCP2221 not available: {type(exc).__name__}: {exc}")
            warn(f"Retrying in {retry_dt:.1f} s...")
            time.sleep(retry_dt)


def i2c_cmd_read(mcp, addr, cmd, nbytes):
    """
    Combined I2C transaction:

        START + addr(W) + cmd + REPEATED START + addr(R) + nbytes + STOP

    This is required for the MLX90393 read-measurement command.
    """
    mcp.I2C_write(addr, bytes([cmd]), kind="nonstop")
    return mcp.I2C_read(addr, nbytes, kind="restart")


def read_mlx90393_raw(mcp):
    """Read one T, X, Y, Z sample from MLX90393."""
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

    # Same conversion used in the legacy C implementation.
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


def open_csv(path):
    """Open CSV in append mode and write header only if file is empty."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    f = path.open("a", newline="")

    fieldnames = [
        "time_s",
        "sample_id",
        "valid",
        "sm_status",
        "rm_status",
        "t_raw",
        "x_raw",
        "y_raw",
        "z_raw",
        "temperature_c",
        "raw_bytes",
        "error",
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)

    if f.tell() == 0:
        writer.writeheader()

    ok(f"CSV logging enabled: {path}")
    return f, writer


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostic test for MLX90393 through MCP2221 USB-I2C bridge."
    )
    parser.add_argument("--out", default=None, help="Optional CSV output path.")
    parser.add_argument("--dt", type=float, default=0.25, help="Sampling interval in seconds.")
    parser.add_argument("--n", type=int, default=0, help="Number of samples. 0 = infinite.")
    parser.add_argument("--reconnect-dt", type=float, default=1.0, help="Reconnect retry interval.")
    args = parser.parse_args()

    if args.dt < MEASUREMENT_WAIT_S:
        warn(
            f"--dt={args.dt:.3f} s is smaller than measurement wait "
            f"{MEASUREMENT_WAIT_S:.3f} s. Effective rate will be limited."
        )

    csv_file = None
    writer = None

    if args.out:
        csv_file, writer = open_csv(args.out)

    debug("Starting MLX90393 diagnostic test.")
    debug(f"Target I2C address: 0x{ADDR:02X}")
    debug("Press Ctrl+C to stop.")

    mcp = connect_mcp2221(retry_dt=args.reconnect_dt)

    t0 = time.time()
    sample_id = 0

    try:
        while args.n == 0 or sample_id < args.n:
            loop_start = time.time()
            t = loop_start - t0

            try:
                sample = read_mlx90393_raw(mcp)

                ok(
                    f"{t:8.3f} s | "
                    f"X={sample['x_raw']:7d} "
                    f"Y={sample['y_raw']:7d} "
                    f"Z={sample['z_raw']:7d} "
                    f"T={sample['temperature_c']:6.2f} °C "
                    f"| SM=0x{sample['sm_status']:02X} "
                    f"RM=0x{sample['rm_status']:02X}"
                )

                row = {
                    "time_s": f"{t:.6f}",
                    "sample_id": sample_id,
                    "valid": 1,
                    "sm_status": f"0x{sample['sm_status']:02X}",
                    "rm_status": f"0x{sample['rm_status']:02X}",
                    "t_raw": sample["t_raw"],
                    "x_raw": sample["x_raw"],
                    "y_raw": sample["y_raw"],
                    "z_raw": sample["z_raw"],
                    "temperature_c": f"{sample['temperature_c']:.6f}",
                    "raw_bytes": sample["raw_bytes"],
                    "error": "",
                }

            except KeyboardInterrupt:
                raise

            except Exception as exc:
                error(f"Read failed: {type(exc).__name__}: {exc}")
                warn("Trying to reconnect MCP2221...")

                row = {
                    "time_s": f"{t:.6f}",
                    "sample_id": sample_id,
                    "valid": 0,
                    "sm_status": "",
                    "rm_status": "",
                    "t_raw": "",
                    "x_raw": "",
                    "y_raw": "",
                    "z_raw": "",
                    "temperature_c": "",
                    "raw_bytes": "",
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
        warn("Stopped by user.")

    finally:
        if csv_file:
            csv_file.close()
            ok("CSV file closed.")


if __name__ == "__main__":
    main()
