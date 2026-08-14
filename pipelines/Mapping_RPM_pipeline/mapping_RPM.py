import serial
import threading
import numpy as np
import sys
import subprocess


from scripts._common import (
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
    
    rec_time = 10 # sec
    save_path = "data/14082026_mapping"
    
    try:
        # Serial port initialization
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        ok(f"Connected to{SERIAL_PORT} at {BAUD_RATE} baud.")

        read_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        read_thread.start()

        cap = open_camera(camera_index=0)
        try:
            for ii in np.arange(1, 110, 0.5):
                command = str(ii) + "\n"
                save_file = save_path + str(ii) + "steps_s"
                ser.write(command.encode('utf-8'))
                cmd = [
                    sys.executable,
                    "scripts/02_track_moving_bead.py",
                    "--rec-time", str(rec_time),
                    "--save", save_file
                ]
        finally:
            cap.release()   
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

