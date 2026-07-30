"""Small serial helpers shared by supported commands."""

import serial


def open_serial(port, baud=9600, timeout=1):
    """Open a serial port with explicit, cross-platform configuration."""
    return serial.Serial(port=port, baudrate=baud, timeout=timeout)


def send_line(serial_port, text):
    """Send one UTF-8 command terminated by a newline."""
    payload = f"{text.rstrip()}\n".encode("utf-8")
    serial_port.write(payload)
    serial_port.flush()
    return payload
