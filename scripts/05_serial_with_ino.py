"""Send interactive commands to an Arduino over a serial connection."""

import argparse
import threading
import time

import serial

from beadtrack import messages
from beadtrack.serial_io import log_serial_messages

DEFAULT_SERIAL_PORT = "/dev/ttyACM0"
DEFAULT_BAUD_RATE = 9600


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_SERIAL_PORT, help="Serial port.")
    parser.add_argument("--baud-rate", type=int, default=DEFAULT_BAUD_RATE)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    serial_port = None

    try:
        serial_port = serial.Serial(args.port, args.baud_rate, timeout=1)
        messages.success(f"Connected to {args.port} at {args.baud_rate} baud.")
        messages.info("Enter a command, or type 'exit' to quit.")

        read_thread = threading.Thread(
            target=log_serial_messages,
            args=(serial_port,),
            daemon=True,
        )
        read_thread.start()

        while True:
            time.sleep(0.01)
            messages.arduino_prompt()
            user_input = input().strip()
            if user_input.lower() == "exit":
                messages.info("Closing serial communication...")
                return 0
            if user_input:
                serial_port.write(f"{user_input}\n".encode())
    except serial.SerialException as exc:
        messages.error(f"Serial communication error: {exc}")
        messages.warning("Check the serial port name and device connection.")
        return 1
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
