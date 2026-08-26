"""Acquire bead trajectories over a persistent camera and motor connection."""

from __future__ import annotations

import argparse
import csv
import threading
import time
from pathlib import Path

import cv2
import serial

from beadtrack import messages
from beadtrack.camera import iter_frames, open_camera, read_frame_or_raise
from beadtrack.io import load_tracking_csv, save_tracking_csv_atomic
from beadtrack.models import TrackingData
from beadtrack.remote_view import Action, RemoteView, compose_grid
from beadtrack.serial_io import log_serial_messages
from beadtrack.tracking import SegmentTracker, TrackingParameters

DEFAULT_SERIAL_PORT = "/dev/ttyACM0"
DEFAULT_BAUD_RATE = 9600
DEFAULT_RECORDING_DURATION = 60.0
DEFAULT_OUTPUT_DIRECTORY = Path("data/processed/mapping_RPM")
DEFAULT_REMOTE_PORT = 8765


class SweepAborted(RuntimeError):
    """Raised when the operator stops the sweep from the remote page."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_SERIAL_PORT, help="Arduino port.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE)
    parser.add_argument(
        "--arduino-ready-wait",
        type=float,
        default=2.0,
        help="Seconds allowed for Arduino reset after opening the serial port.",
    )
    parser.add_argument(
        "--speed-mode-command",
        default="SPEED",
        help="Command sent once before numeric speed values.",
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--duration", type=float, default=DEFAULT_RECORDING_DURATION)
    parser.add_argument(
        "--settle",
        type=float,
        default=2.0,
        help="Seconds to wait and drain camera frames after each speed command.",
    )
    parser.add_argument("--speeds", nargs="*", type=float, default=None)
    parser.add_argument("--speed-start", type=float, default=1.0)
    parser.add_argument("--speed-stop", type=float, default=79.5)
    parser.add_argument("--speed-step", type=float, default=0.5)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Record again even when an existing output CSV is valid.",
    )
    parser.add_argument(
        "--min-detections",
        type=int,
        default=4,
        help="Minimum detections required before a run is accepted.",
    )
    parser.add_argument(
        "--display",
        choices=("none", "remote"),
        default="none",
        help="Run headless or keep one browser view open for the whole sweep.",
    )
    parser.add_argument("--remote-port", type=int, default=DEFAULT_REMOTE_PORT)
    parser.add_argument(
        "--remote-debug",
        action="store_true",
        help="Stream tracking and all three masks instead of tracking only.",
    )
    parser.add_argument(
        "--stop-command",
        default="STOP",
        help="Arduino command sent in finally, including after errors.",
    )
    parser.add_argument("--history", type=int, default=500)
    parser.add_argument("--var-threshold", type=float, default=100)
    parser.add_argument("--threshold", type=int, default=120)
    parser.add_argument("--kernel", type=int, default=3)
    parser.add_argument("--dilate", type=int, default=2)
    parser.add_argument("--min-area", type=float, default=50)
    parser.add_argument("--max-area", type=float, default=None)
    return parser


def parse_speeds(args: argparse.Namespace) -> list[float]:
    if args.speeds is not None:
        return [float(speed) for speed in args.speeds]
    if args.speed_step == 0:
        raise ValueError("--speed-step cannot be zero")
    if args.speed_step > 0 and args.speed_start > args.speed_stop:
        raise ValueError("positive --speed-step requires start <= stop")
    if args.speed_step < 0 and args.speed_start < args.speed_stop:
        raise ValueError("negative --speed-step requires start >= stop")

    speeds = []
    speed = args.speed_start
    if args.speed_step > 0:
        while speed <= args.speed_stop + 1e-12:
            speeds.append(float(speed))
            speed += args.speed_step
    else:
        while speed >= args.speed_stop - 1e-12:
            speeds.append(float(speed))
            speed += args.speed_step
    return speeds


def format_speed(speed: float) -> str:
    """Return the shared filename representation used by analysis scripts."""
    return f"{speed:g}"


def output_path_for_speed(output_dir: Path, speed: float) -> Path:
    return output_dir / f"{format_speed(speed)}_RPM.csv"


def existing_run_is_valid(path: Path, minimum_detections: int) -> bool:
    if not path.exists():
        return False
    try:
        return len(load_tracking_csv(path)) >= minimum_detections
    except (OSError, KeyError, TypeError, ValueError):
        return False


def save_status(path: Path, rows: list[dict[str, object]]) -> None:
    """Atomically replace the sweep status CSV after every condition."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fieldnames = ["speed", "status", "detections", "file", "detail"]
    try:
        with temporary.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def send_command(serial_port: serial.Serial, command: str) -> None:
    serial_port.write(f"{command.rstrip()}\n".encode("utf-8"))
    serial_port.flush()


def remote_abort_requested(remote: RemoteView | None) -> bool:
    return remote is not None and any(
        event.name == "abort" for event in remote.drain_events()
    )


def settle_camera(
    capture: cv2.VideoCapture,
    duration: float,
    remote: RemoteView | None,
    speed: float,
) -> None:
    """Wait for the motor while draining frames from the persistent camera."""
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        frame = read_frame_or_raise(capture)
        if remote is not None:
            remote.update_state(speed=format_speed(speed), phase="settling")
            remote.publish_frame(frame)
        if remote_abort_requested(remote):
            raise SweepAborted("remote stop requested")


def record_segment(
    capture: cv2.VideoCapture,
    duration: float,
    parameters: TrackingParameters,
    remote: RemoteView | None,
    remote_debug: bool,
    speed: float,
) -> TrackingData:
    """Record one speed condition with a fresh tracker and persistent camera."""
    tracker = SegmentTracker(parameters)
    for captured in iter_frames(capture):
        processed = tracker.process(captured)
        if remote is not None:
            remote_frame = processed.display
            if remote_debug:
                remote_frame = compose_grid(
                    [
                        ("TRACKING", processed.display),
                        ("FOREGROUND", processed.foreground),
                        ("THRESHOLD", processed.threshold),
                        ("CLEAN MASK", processed.clean),
                    ]
                )
            remote.update_state(
                speed=format_speed(speed),
                phase="recording",
                elapsed_s=round(processed.elapsed, 1),
                detections=processed.sample_count,
            )
            remote.publish_frame(remote_frame)
        if remote_abort_requested(remote):
            raise SweepAborted("remote stop requested")
        if processed.elapsed >= duration:
            return tracker.data()
    raise RuntimeError("camera frame iterator ended unexpectedly")


def validate_args(args: argparse.Namespace) -> TrackingParameters:
    if args.duration <= 0:
        raise ValueError("--duration must be positive")
    if args.settle < 0:
        raise ValueError("--settle cannot be negative")
    if args.arduino_ready_wait < 0:
        raise ValueError("--arduino-ready-wait cannot be negative")
    if args.min_detections <= 0:
        raise ValueError("--min-detections must be positive")
    if not 1 <= args.remote_port <= 65535:
        raise ValueError("--remote-port must be between 1 and 65535")
    if not args.stop_command.strip():
        raise ValueError("--stop-command cannot be empty")
    if not args.speed_mode_command.strip():
        raise ValueError("--speed-mode-command cannot be empty")
    return TrackingParameters(
        history=args.history,
        var_threshold=args.var_threshold,
        threshold=args.threshold,
        kernel=args.kernel,
        dilate=args.dilate,
        min_area=args.min_area,
        max_area=args.max_area,
    )


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        parameters = validate_args(args)
        speeds = parse_speeds(args)
        if not speeds:
            raise ValueError("the speed list cannot be empty")
    except ValueError as exc:
        parser.error(str(exc))

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "mapping_status.csv"
    statuses: list[dict[str, object]] = []
    serial_port = None
    capture = None
    remote = None
    read_thread = None

    try:
        serial_port = serial.Serial(args.port, args.baud, timeout=1)
        messages.success(f"Connected to {args.port} at {args.baud} baud.")
        read_thread = threading.Thread(
            target=log_serial_messages,
            args=(serial_port,),
            daemon=True,
        )
        read_thread.start()
        if args.arduino_ready_wait > 0:
            time.sleep(args.arduino_ready_wait)
        send_command(serial_port, args.speed_mode_command)

        capture = open_camera(camera_index=args.camera)
        messages.success(f"Camera {args.camera} opened for the complete sweep.")

        if args.display == "remote":
            remote = RemoteView(
                "Bead RPM mapping",
                port=args.remote_port,
                actions=(
                    Action("abort", "Stop sweep", ("q", "Escape"), danger=True),
                ),
            )
            remote.start()
            remote.update_state(total_conditions=len(speeds), phase="ready")
            messages.info(f"Remote mapping view: {remote.url}")

        for index, speed in enumerate(speeds, start=1):
            output = output_path_for_speed(output_dir, speed)
            if not args.overwrite and existing_run_is_valid(
                output, args.min_detections
            ):
                detections = len(load_tracking_csv(output))
                statuses.append(
                    {
                        "speed": format_speed(speed),
                        "status": "skipped_existing",
                        "detections": detections,
                        "file": output.name,
                        "detail": "valid existing run",
                    }
                )
                save_status(status_path, statuses)
                messages.info(f"Skipping valid existing run: {output}")
                continue

            messages.info(
                f"Condition {index}/{len(speeds)}: speed={format_speed(speed)}"
            )
            if remote is not None:
                remote.update_state(
                    condition=f"{index}/{len(speeds)}",
                    speed=format_speed(speed),
                    phase="commanding",
                    detections=0,
                )
            send_command(serial_port, format_speed(speed))
            settle_camera(capture, args.settle, remote, speed)

            try:
                data = None
                data = record_segment(
                    capture=capture,
                    duration=args.duration,
                    parameters=parameters,
                    remote=remote,
                    remote_debug=args.remote_debug,
                    speed=speed,
                )
                if len(data) < args.min_detections:
                    raise RuntimeError(
                        f"speed {format_speed(speed)} produced {len(data)} detections; "
                        f"minimum is {args.min_detections}"
                    )
                save_tracking_csv_atomic(output, data)
            except SweepAborted:
                raise
            except (OSError, RuntimeError, ValueError, cv2.error) as exc:
                statuses.append(
                    {
                        "speed": format_speed(speed),
                        "status": "failed",
                        "detections": len(data) if data is not None else 0,
                        "file": output.name,
                        "detail": str(exc),
                    }
                )
                save_status(status_path, statuses)
                raise

            statuses.append(
                {
                    "speed": format_speed(speed),
                    "status": "completed",
                    "detections": len(data),
                    "file": output.name,
                    "detail": "",
                }
            )
            save_status(status_path, statuses)
            messages.success(
                f"Saved speed {format_speed(speed)}: {len(data)} detections -> {output}"
            )

        messages.result("All data successfully acquired.")
        return 0
    except SweepAborted:
        messages.warning("Sweep stopped remotely; completed runs were preserved.")
        return 130
    except KeyboardInterrupt:
        print()
        messages.warning("Sweep interrupted; completed runs were preserved.")
        return 130
    except (OSError, RuntimeError, ValueError, serial.SerialException, cv2.error) as exc:
        messages.error(exc)
        return 1
    finally:
        if serial_port is not None and serial_port.is_open:
            try:
                send_command(serial_port, args.stop_command)
                messages.info(f"Motor stop command sent: {args.stop_command}")
            except (OSError, serial.SerialException) as exc:
                messages.error(f"Could not send motor stop command: {exc}")
        if capture is not None:
            capture.release()
            messages.info("Camera released.")
        if remote is not None:
            remote.close()
        if serial_port is not None and serial_port.is_open:
            serial_port.close()
            messages.info("Serial port closed.")
        if read_thread is not None:
            read_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
