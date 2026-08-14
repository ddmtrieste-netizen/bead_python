import serial
import threading
import numpy as np
import sys
import subprocess

from pathlib import Path
from beadtrack._common import (
    open_camera,
    read_from_arduino,
    ok,
    result,
    warn,
    error,
    ino_mess
)

SERIAL_PORT = '/dev/ttyACM0' # can switch to ttyACM0 or ttyACM1
BAUD_RATE = 9600

class CustomArgs:
    pass

def main():
    
    rec_time = 60 # sec
    save_path = "data/14082026_mapping"
    
    try:
        # Serial port initialization
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ok(f"Connected to{SERIAL_PORT} at {BAUD_RATE} baud.")

        read_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        read_thread.start()

        try:
            for ii in np.arange(1, 80, 0.5):
                command = str(ii) + "\n"
                save_file = save_path + str(ii).replace(".", "_") + "steps_s"
                Path(save_file).parent.mkdir(parents=True, exist_ok=True)
                ser.write(command.encode('utf-8'))
                cmd = [
                    sys.executable,
                    "scripts/02_track_moving_bead.py",
                    "--rec-time", str(rec_time),
                    "--output", save_file,
                    "--no-debug"
                ]
                recording_rsesult = subprocess.run(cmd, check=True)
                ok(f"Step {ii} succesfully completed")
        finally: 
            result("All data successfully acquired.")     
                
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

