import serial
import threading
import cv2
import time
import numpy as np

from scripts._common import (
    open_camera,
    create_background_subtractor,
    compute_foreground_masks,
    detect_largest_contour_circle,
    draw_detection,
    draw_track,
    save_tracking_csv,
    read_from_arduino,
    timestamp_string,
    info,
    ok,
    result,
    warn,
    error
)

SERIAL_PORT = '/dev/ttyACM0' # can switch to ttyACM0 or ttyACM1
BAUD_RATE = 9600

class CustomArgs:
    pass


def tracker(cap, speed, recording_time_sec):
    args = CustomArgs()
    args.camera = 0
    args.save = 1
    args.output = f"data/mapping_RMP_aug07/mapping_001/{speed}_RPM.csv"
    args.history = 500
    args.var_threshold = 100.0  
    args.threshold = 120        
    args.kernel = 3             
    args.dilate = 2             

    args.min_area = 50.0        
    args.max_area = None
    args.no_debug = True 


    bg = create_background_subtractor(
        history=args.history,
        var_threshold=args.var_threshold,
        detect_shadows=True,
    )

    ts = []
    xs = []
    ys = []
    radii = []
    areas = []

# aggiungere [tracker] nel message
    print(f"{VIOLA}[TRACKER] Tracking started.")
    print("Press q to save and quit.")
    print(f"Press ESC to quit without saving.{RESET}")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Could not read frame.")
            break

        now = time.time()

        foreground, threshold, clean = compute_foreground_masks(
            frame,
            bg,
            threshold_value=args.threshold,
            kernel_size=args.kernel,
            dilation_iterations=args.dilate,
        )

        detection = detect_largest_contour_circle(
            clean,
            min_area=args.min_area,
            max_area=args.max_area,
        )

        if detection is not None:
            ts.append(now)
            xs.append(detection["x"])
            ys.append(detection["y"])
            radii.append(detection["radius"])

            area = detection["area"]
            if area is None:
                area = np.nan

            areas.append(area)

        display = frame.copy()
        draw_detection(display, detection)
        draw_track(display, xs, ys)

        if not args.no_debug:
            cv2.imshow("foreground", foreground)
            cv2.imshow("threshold", threshold)
            cv2.imshow("clean_mask", clean)

        cv2.imshow("tracking", display)

        key = cv2.waitKey(1) & 0xFF
        if now - ts[0] > recording_time_sec:
            if len(ts) > 0 and args.save:
                save_tracking_csv(args.output, ts, xs, ys, radii, areas)
                print(f"Saved {len(ts)} points to: {args.output}")
            else:
                print("No detections saved.")
            break

        if key == 27:
            print("ESC pressed. Exiting without saving.")
            break
        
        cv2.destroyAllWindows()



def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connesso a {SERIAL_PORT} a {BAUD_RATE} baud.")
        
        read_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        read_thread.start()
        
        cap = open_camera(camera_index=0)
        # Routine di cambio di motor speed
        try:
            for ii in np.arange(1, 110, 0.5):

                command = str(ii) + "\n"
                ser.write(command.encode('utf-8'))
                tracker(cap, ii, 60)
        finally:
            cap.release()            
                
    except serial.SerialException as e:
        print(f"Errore di connessione seriale: {e}")
    except KeyboardInterrupt:
        print("\nProgramma interrotto dall'utente.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("Porta seriale chiusa.")

if __name__ == "__main__":
    main()       

