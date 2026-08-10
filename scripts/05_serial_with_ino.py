"""Open an interactive serial console for the Arduino firmware."""

import argparse
import threading
import time

import serial

from beadtrack.console import error, info, ok, result, warn
from beadtrack.serial_io import open_serial, send_line


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        required=True,
        help="Serial port, for example COM3 or /dev/ttyACM0.",
    )
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate.")
    parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds.")
    return parser


def read_from_arduino(serial_port, stop_event):
    """Print complete lines received from Arduino until asked to stop."""
    while serial_port.is_open and not stop_event.is_set():
        try:
            if serial_port.in_waiting > 0:
                text = serial_port.readline().decode("utf-8", errors="replace").strip()
                if text:
                    info(f"Arduino: {text}")
            else:
                time.sleep(0.01)
        except (OSError, serial.SerialException) as exc:
            error(f"Serial read failed: {exc}")
            stop_event.set()


def main(argv=None):
    args = build_parser().parse_args(argv)
    serial_port = None
    stop_event = threading.Event()

    try:
        serial_port = open_serial(args.port, args.baud, args.timeout)
        ok(f"Connected to {args.port} at {args.baud} baud.")
        info("Enter a command, or type 'exit' to close the console.")
        reader = threading.Thread(
            target=read_from_arduino,
            args=(serial_port, stop_event),
            daemon=True,
        )
        reader.start()

        while not stop_event.is_set():
            command = input("Command > ").strip()
            if command.lower() == "exit":
                result("serial_console=closed stopped_by=user")
                return 0
            if command:
                send_line(serial_port, command)

        error("Serial reader stopped after an I/O error.")
        return 1
    except KeyboardInterrupt:
        warn("Serial console interrupted by user.")
        result("serial_console=closed stopped_by=interrupt")
        return 0
    except EOFError:
        warn("Serial console reached end of input.")
        result("serial_console=closed stopped_by=eof")
        return 0
    except (OSError, serial.SerialException) as exc:
        error(f"Could not use serial port {args.port}: {exc}")
        return 1
    finally:
        stop_event.set()
        if serial_port is not None and serial_port.is_open:
            serial_port.close()
            ok("Serial port closed.")


if __name__ == "__main__":
    raise SystemExit(main())
