import argparse
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import serial

from beadtrack.camera import open_camera
from beadtrack.console import error, info, ok, result, warn
from beadtrack.data import save_tracking_csv
from beadtrack.serial_io import open_serial, send_line
from beadtrack.tracking import (
    compute_foreground_masks,
    create_background_subtractor,
    detect_largest_contour_circle,
    draw_detection,
    draw_track,
)


TRACKER_COMPLETED = "completed"
TRACKER_ABORTED = "aborted"
TRACKER_FAILED = "failed"


def read_from_arduino(ser):
    """Continuously print messages received from the Arduino."""
    while ser.is_open:
        try:
            if ser.in_waiting > 0:
                data = ser.readline().decode("utf-8", errors="ignore").strip()
                if data:
                    info(f"Arduino: {data}")
        except Exception as exc:
            warn(f"Arduino read error: {exc}")
            break

        time.sleep(0.01)


def send_rpm_command(ser, rpm):
    """Send one RPM command using the firmware's ``<rpm>\\n`` protocol."""
    send_line(ser, f"{rpm:g}")
    info(f"Requested motor speed: {rpm:g} RPM")


def stop_motor(ser):
    """Best-effort emergency stop that never masks the original exception."""
    if ser is None or not ser.is_open:
        return

    try:
        send_line(ser, "0")
        ok("Motor stop command sent.")
    except Exception as exc:
        warn(f"Could not send motor stop command: {exc}")


def tracker(
    cap,
    rpm,
    recording_time_sec,
    output_dir,
    warmup_time_sec=2.0,
):
    """Track one RPM condition.

    Return a ``TRACKER_*`` status describing the outcome.
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

    info(f"Warming up the background model for {warmup_time_sec:g} s.")
    info("Press q to save this condition or ESC to abort the complete sweep.")

    def save_current_run():
        if not ts:
            error(f"No bead detections were recorded at {rpm:g} RPM.")
            return False

        save_tracking_csv(output_file, ts, xs, ys, radii, areas)
        ok(f"Saved {len(ts)} points to {output_file}")
        result(f"motor_rpm={rpm:g} detections={len(ts)} path={output_file}")
        return True

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                error("Could not read camera frame.")
                return TRACKER_FAILED

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
                warn("Sweep aborted with ESC; the current condition was not saved.")
                return TRACKER_ABORTED

            if key == ord("q"):
                return TRACKER_COMPLETED if save_current_run() else TRACKER_FAILED

            if recording and now - recording_start >= recording_time_sec:
                return TRACKER_COMPLETED if save_current_run() else TRACKER_FAILED
    finally:
        cv2.destroyAllWindows()


def build_parser():
    parser = argparse.ArgumentParser(description="Map commanded motor RPM to bead trajectory.")
    parser.add_argument(
        "--serial-port",
        required=True,
        help="Arduino port, for example COM3 or /dev/ttyACM0.",
    )
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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.rpm_step <= 0:
        parser.error("--rpm-step must be positive.")
    if args.rpm_stop < args.rpm_start:
        parser.error("--rpm-stop must be greater than or equal to --rpm-start.")
    if args.duration <= 0:
        parser.error("--duration must be positive.")
    if args.settle < 0:
        parser.error("--settle cannot be negative.")
    if args.warmup < 0:
        parser.error("--warmup cannot be negative.")
    if args.baud <= 0:
        parser.error("--baud must be positive.")

    ser = None
    cap = None
    completed_conditions = 0

    try:
        ser = open_serial(args.serial_port, args.baud, timeout=1)
        ok(f"Connected to {args.serial_port} at {args.baud} baud.")

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

            tracker_status = tracker(
                cap=cap,
                rpm=rpm,
                recording_time_sec=args.duration,
                output_dir=args.output_dir,
                warmup_time_sec=args.warmup,
            )
            if tracker_status == TRACKER_ABORTED:
                break
            if tracker_status == TRACKER_FAILED:
                return 1
            completed_conditions += 1

    except serial.SerialException as exc:
        error(f"Serial connection error: {exc}")
        return 1
    except (OSError, RuntimeError, cv2.error) as exc:
        error(str(exc))
        return 1
    except KeyboardInterrupt:
        warn("Sweep interrupted by user.")
        return 0
    finally:
        stop_motor(ser)
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        if ser is not None and ser.is_open:
            ser.close()
            ok("Serial port closed.")

    result(f"completed_conditions={completed_conditions} output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
