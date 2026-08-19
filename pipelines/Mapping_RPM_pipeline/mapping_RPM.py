"""Acquire bead trajectories over a sweep of stepper-motor speeds."""

import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import serial

from beadtrack import messages
from beadtrack.serial_io import log_serial_messages

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 9600
RECORDING_DURATION = 60.0
OUTPUT_DIRECTORY = Path("data/14082026_mapping")


def main() -> int:
    serial_port = None

    try:
        serial_port = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        messages.success(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")

        read_thread = threading.Thread(
            target=log_serial_messages,
            args=(serial_port,),
            daemon=True,
        )
        read_thread.start()

        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        for speed in np.arange(1, 80, 0.5):
            serial_port.write(f"{speed}\n".encode())
            speed_label = str(speed).replace(".", "_")
            output = OUTPUT_DIRECTORY / f"{speed_label}_steps_s.csv"
            command = [
                sys.executable,
                "scripts/02_track_moving_bead.py",
                "--rec-time",
                str(RECORDING_DURATION),
                "--output",
                str(output),
                "--no-debug",
            ]
            subprocess.run(command, check=True)
            messages.success(f"Completed speed step {speed}")

        messages.result("All data successfully acquired.")
        return 0
    except serial.SerialException as exc:
        messages.error(f"Serial communication error: {exc}")
        messages.warning("Check the serial port name and device connection.")
        return 1
    except subprocess.CalledProcessError as exc:
        messages.error(f"Tracking subprocess failed with exit code {exc.returncode}")
        return exc.returncode or 1
    except KeyboardInterrupt:
        print()
        messages.warning("User interruption detected.")
        return 0
    finally:
        if serial_port is not None and serial_port.is_open:
            serial_port.close()
            messages.info("Serial port closed.")


if __name__ == "__main__":
    raise SystemExit(main())
