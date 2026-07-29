import argparse
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import serial

from _common import (
    compute_foreground_masks,
    create_background_subtractor,
    detect_largest_contour_circle,
    draw_detection,
    draw_track,
    open_camera,
    save_tracking_csv,
)


ROSSO = "\033[31m"
VERDE = "\033[32m"
GIALLO = "\033[33m"
RESET = "\033[0m"
VIOLA = "\033[35m"


def read_from_arduino(ser):
    """Continuously print messages received from the Arduino."""
    while ser.is_open:
        try:
            if ser.in_waiting > 0:
                data = ser.readline().decode("utf-8", errors="ignore").strip()
                if data:
                    print(f"\n[Arduino]: {data}")
        except Exception as exc:
            print(f"\n{GIALLO}Arduino read error: {exc}{RESET}")
            break

        time.sleep(0.01)


def send_rpm_command(ser, rpm):
    """Send one RPM command using the firmware's ``<rpm>\\n`` protocol."""
    command = f"{rpm:g}\n"
    ser.write(command.encode("utf-8"))
    ser.flush()
    print(f"{VIOLA}[ARDUINO] requested RPM: {rpm:g}{RESET}")


def stop_motor(ser):
    """Best-effort emergency stop that never masks the original exception."""
    if ser is None or not ser.is_open:
        return

    try:
        ser.write(b"0\n")
        ser.flush()
        print(f"{VERDE}[ARDUINO] stop command sent.{RESET}")
    except Exception as exc:
        print(f"{ROSSO}[WARN] Could not send motor stop command: {exc}{RESET}")


def tracker(
    cap,
    rpm,
    recording_time_sec,
    output_dir,
    warmup_time_sec=2.0,
):
    """Track one RPM condition.

    Returns ``True`` when the sweep may continue and ``False`` when the user
    requests a complete abort with ESC or the camera stops.
    """
    output_dir = Path(output_dir)
    output_file = output_dir / f"{rpm:g}_RPM.csv"
    bg = create_background_subtractor(
        history=500,
        var_threshold=100.0,
        detect_shadows=True,
    )

    ts = []
    xs = []
    ys = []
    radii = []
    areas = []

    warmup_end = time.monotonic() + max(0.0, warmup_time_sec)
    recording_start = warmup_end

    print(f"{VIOLA}[TRACKER] Warming up background model for {warmup_time_sec:g} s.")
    print("Press q to save the current condition and continue.")
    print(f"Press ESC to abort the complete sweep.{RESET}")

    def save_current_run():
        if not ts:
            print(f"{GIALLO}[TRACKER] No detections to save for {rpm:g} RPM.{RESET}")
            return

        save_tracking_csv(output_file, ts, xs, ys, radii, areas)
        print(f"{VERDE}[TRACKER] Saved {len(ts)} points to: {output_file}{RESET}")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"{ROSSO}[TRACKER] Could not read camera frame.{RESET}")
                return False

            now = time.monotonic()
            foreground, threshold, clean = compute_foreground_masks(
                frame,
                bg,
                threshold_value=120,
                kernel_size=3,
                dilation_iterations=2,
            )

            detection = detect_largest_contour_circle(
                clean,
                min_area=50.0,
                max_area=None,
            )

            recording = now >= recording_start
            if recording and detection is not None:
                ts.append(now)
                xs.append(detection["x"])
                ys.append(detection["y"])
                radii.append(detection["radius"])
                area = detection["area"]
                areas.append(np.nan if area is None else area)

            display = frame.copy()
            draw_detection(display, detection)
            draw_track(display, xs, ys)
            cv2.imshow("tracking", display)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                print(f"{GIALLO}[TRACKER] ESC pressed. Aborting sweep without saving.{RESET}")
                return False

            if key == ord("q"):
                save_current_run()
                return True

            if recording and now - recording_start >= recording_time_sec:
                save_current_run()
                return True
    finally:
        cv2.destroyAllWindows()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Map commanded motor RPM to bead trajectory."
    )
    parser.add_argument("--serial-port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--rpm-start", type=int, default=1)
    parser.add_argument("--rpm-stop", type=int, default=99)
    parser.add_argument("--rpm-step", type=int, default=1)
    parser.add_argument("--duration", type=float, default=180.0)
    parser.add_argument("--settle", type=float, default=2.0)
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--output-dir", default="data/processed/mapping_RPM")
    return parser


def main():
    args = build_parser().parse_args()
    if args.rpm_step <= 0:
        raise ValueError("--rpm-step must be positive.")
    if args.rpm_stop < args.rpm_start:
        raise ValueError("--rpm-stop must be greater than or equal to --rpm-start.")
    if args.duration <= 0:
        raise ValueError("--duration must be positive.")

    ser = None
    cap = None

    try:
        ser = serial.Serial(args.serial_port, args.baud, timeout=1)
        print(f"{VERDE}Connected to {args.serial_port} at {args.baud} baud.{RESET}")

        read_thread = threading.Thread(
            target=read_from_arduino,
            args=(ser,),
            daemon=True,
        )
        read_thread.start()
        cap = open_camera(camera_index=args.camera)

        for rpm in range(args.rpm_start, args.rpm_stop + 1, args.rpm_step):
            send_rpm_command(ser, rpm)
            if args.settle > 0:
                time.sleep(args.settle)

            continue_sweep = tracker(
                cap=cap,
                rpm=rpm,
                recording_time_sec=args.duration,
                output_dir=args.output_dir,
                warmup_time_sec=args.warmup,
            )
            if not continue_sweep:
                break

    except serial.SerialException as exc:
        print(f"{ROSSO}Serial connection error: {exc}{RESET}")
    except KeyboardInterrupt:
        print(f"\n{GIALLO}Interrupted by user.{RESET}")
    finally:
        stop_motor(ser)
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        if ser is not None and ser.is_open:
            ser.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main()
