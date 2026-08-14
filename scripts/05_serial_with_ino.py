import serial
import threading
import argparse
import time
import sys

from _common import(
    read_from_arduino,
    info,
    ok,
    ino_mess,
    warn,
    error
)

# Insert below Arduino port and baud rate 
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600


def main():

    try:
        # Serial port initialization
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ok(f"Connected to{SERIAL_PORT} at {BAUD_RATE} baud.")
        info("Insert a command and press ENTER. Typer 'exit' to exit.")
        read_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        read_thread.start()

        while True:
            time.sleep(0.01)
            ino_mess()
            user_input = input()
            
            if user_input.lower() == 'exit':
                info("Closing serial comunication...")
                break
                
            if user_input:
                command = user_input + "\n"
                ser.write(command.encode('utf-8'))
                
    except serial.SerialException as e:
        error(f"Serial comunication error: {e}")
        warn(f"Try SERIAL_PORT = /dev/ttyACM0 or /dev/ttyACM0")
    except KeyboardInterrupt:
        print()
        warn("User interruption detected.")
    finally:
        # Close port 
        if 'ser' in locals() and ser.is_open:
            ser.close()
        warn("Serial port closed.")

if __name__ == "__main__":
    main()
