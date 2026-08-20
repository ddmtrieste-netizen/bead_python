"""Track the largest moving bead using MOG2 background subtraction."""

import argparse
import time

import cv2

from beadtrack import messages
from beadtrack.camera import iter_frames, open_camera
from beadtrack.detection import (
    compute_foreground_masks,
    create_background_subtractor,
    detect_largest_contour_circle,
)
from beadtrack.drawing import draw_detection, draw_sample_track
from beadtrack.io import save_tracking_csv, timestamp_for_filename
from beadtrack.models import TrackingData, TrackingSample


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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = args.output or f"data/processed/track_{timestamp_for_filename()}.csv"

    capture = None
    samples: list[TrackingSample] = []

    try:
        capture = open_camera(camera_index=args.camera)
        background = create_background_subtractor(
            history=args.history,
            var_threshold=args.var_threshold,
            detect_shadows=True,
        )
        recording_started_at = time.monotonic()

        messages.info("Tracking started.", end=" ")
        print(
            f"Press {messages.bold('q')} to save and quit. "
            f"Press {messages.bold('ESC')} to quit without saving."
        )

        for captured in iter_frames(capture):
            frame = captured.image
            now = captured.time

            foreground, threshold, clean = compute_foreground_masks(
                frame,
                background,
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
                samples.append(TrackingSample(time=now, detection=detection))

            display = frame.copy()
            draw_detection(display, detection)
            draw_sample_track(display, samples)

            if not args.no_debug:
                cv2.imshow("foreground", foreground)
                cv2.imshow("threshold", threshold)
                cv2.imshow("clean_mask", clean)
            cv2.imshow("tracking", display)

            key = cv2.waitKey(1) & 0xFF
            time_is_up = (
                args.rec_time is not None
                and now - recording_started_at >= args.rec_time
            )
            if key == ord("q") or time_is_up:
                if samples and args.save:
                    data = TrackingData.from_samples(samples)
                    save_tracking_csv(output, data)
                    messages.success(
                        f"Saved {len(data)} points to {messages.bold(output)}"
                    )
                elif not samples:
                    messages.warning("No detections saved.")
                return 0

            if key == 27:
                messages.warning("ESC pressed. Exiting without saving.")
                return 0

        return 0
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:
        messages.error(exc)
        return 1
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
