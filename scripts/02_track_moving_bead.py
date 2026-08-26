"""Track the largest moving bead using MOG2 background subtraction."""

import argparse

import cv2

from beadtrack import messages
from beadtrack.camera import iter_frames, open_camera
from beadtrack.io import save_tracking_csv, timestamp_for_filename
from beadtrack.remote_view import (
    Action,
    RemoteView,
    add_display_arguments,
    compose_grid,
)
from beadtrack.tracking import SegmentTracker, TrackingParameters


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument(
        "--no-save",
        action="store_false",
        dest="save",
        help="Do not save tracking data when recording stops.",
    )
    parser.add_argument("--output", default=None, help="Output CSV path.")
    parser.add_argument("--history", type=int, default=500, help="MOG2 history.")
    parser.add_argument(
        "--var-threshold",
        type=float,
        default=100,
        help="MOG2 variance threshold.",
    )
    parser.add_argument("--threshold", type=int, default=120, help="Binary threshold.")
    parser.add_argument(
        "--kernel", type=int, default=3, help="Morphological kernel size."
    )
    parser.add_argument("--dilate", type=int, default=2, help="Dilation iterations.")
    parser.add_argument(
        "--min-area", type=float, default=50, help="Minimum contour area."
    )
    parser.add_argument(
        "--max-area", type=float, default=None, help="Maximum contour area."
    )
    parser.add_argument(
        "--no-debug", action="store_true", help="Hide mask debug windows."
    )
    parser.add_argument(
        "--rec-time",
        type=float,
        default=None,
        help="Automatically stop after this many seconds.",
    )
    add_display_arguments(parser)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or f"data/processed/track_{timestamp_for_filename()}.csv"

    capture = None
    remote = None

    try:
        capture = open_camera(camera_index=args.camera)
        tracker = SegmentTracker(
            TrackingParameters(
                history=args.history,
                var_threshold=args.var_threshold,
                threshold=args.threshold,
                kernel=args.kernel,
                dilate=args.dilate,
                min_area=args.min_area,
                max_area=args.max_area,
            )
        )
        if args.display == "remote":
            remote = RemoteView(
                "Beadtrack moving bead",
                port=args.remote_port,
                actions=(
                    Action("stop_save", "Save and stop", ("q",)),
                    Action(
                        "stop_discard",
                        "Stop without saving",
                        ("Escape",),
                        danger=True,
                    ),
                ),
            )
            remote.start()
            messages.info(f"Remote tracking view: {remote.url}")
        messages.info("Tracking started.", end=" ")
        if args.display == "local":
            print(
                f"Press {messages.bold('q')} to save and quit. "
                f"Press {messages.bold('ESC')} to quit without saving."
            )

        for captured in iter_frames(capture):
            processed = tracker.process(captured)

            if remote is not None:
                remote_frame = processed.display
                if not args.no_debug:
                    remote_frame = compose_grid(
                        [
                            ("TRACKING", processed.display),
                            ("FOREGROUND", processed.foreground),
                            ("THRESHOLD", processed.threshold),
                            ("CLEAN MASK", processed.clean),
                        ]
                    )
                remote.update_state(detections=processed.sample_count)
                remote.publish_frame(remote_frame)
                event_names = {event.name for event in remote.drain_events()}
                if "stop_discard" in event_names:
                    key = 27
                elif "stop_save" in event_names:
                    key = ord("q")
                else:
                    key = 255
            else:
                if not args.no_debug:
                    cv2.imshow("foreground", processed.foreground)
                    cv2.imshow("threshold", processed.threshold)
                    cv2.imshow("clean_mask", processed.clean)
                cv2.imshow("tracking", processed.display)
                key = cv2.waitKey(1) & 0xFF

            time_is_up = (
                args.rec_time is not None
                and processed.elapsed >= args.rec_time
            )
            if key == ord("q") or time_is_up:
                if tracker.sample_count and args.save:
                    data = tracker.data()
                    save_tracking_csv(output, data)
                    messages.success(
                        f"Saved {len(data)} points to {messages.bold(output)}"
                    )
                elif not tracker.sample_count:
                    messages.warning("No detections saved.")
                return 0

            if key == 27:
                messages.warning("ESC pressed. Exiting without saving.")
                return 0

        return 0
    except KeyboardInterrupt:
        messages.warning("Tracking interrupted without saving.")
        return 0
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:
        messages.error(exc)
        return 1
    finally:
        if capture is not None:
            capture.release()
        if remote is not None:
            remote.close()
        if args.display == "local":
            cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
