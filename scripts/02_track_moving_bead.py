"""Track the largest moving bead using background subtraction."""

import argparse
import time

import cv2
import numpy as np

from beadtrack.camera import open_camera
from beadtrack.console import error, info, ok, result, warn
from beadtrack.data import save_tracking_csv, timestamp_string
from beadtrack.tracking import (
    compute_foreground_masks,
    create_background_subtractor,
    detect_largest_contour_circle,
    draw_detection,
    draw_track,
)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--save", action="store_true", help="Save detections to CSV.")
    parser.add_argument("--output", default=None, help="Output CSV path.")
    parser.add_argument("--history", type=int, default=500, help="MOG2 history.")
    parser.add_argument(
        "--var-threshold",
        type=float,
        default=100,
        help="MOG2 variance threshold.",
    )
    parser.add_argument("--threshold", type=int, default=120, help="Binary threshold.")
    parser.add_argument("--kernel", type=int, default=3, help="Morphological kernel size.")
    parser.add_argument("--dilate", type=int, default=2, help="Dilation iterations.")
    parser.add_argument("--min-area", type=float, default=50, help="Minimum contour area.")
    parser.add_argument("--max-area", type=float, default=None, help="Maximum contour area.")
    parser.add_argument("--no-debug", action="store_true", help="Hide mask windows.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.output is not None and not args.save:
        parser.error("--output requires --save")

    output = args.output or f"data/processed/track_{timestamp_string()}.csv"
    cap = None
    ts = []
    xs = []
    ys = []
    radii = []
    areas = []

    try:
        cap = open_camera(camera_index=args.camera)
        background = create_background_subtractor(
            history=args.history,
            var_threshold=args.var_threshold,
            detect_shadows=True,
        )
        info("Tracking started. Press q to stop or ESC to discard the run.")

        while True:
            received, frame = cap.read()
            if not received or frame is None:
                error("Could not read frame from camera")
                return 1

            now = time.monotonic()
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
                ts.append(now)
                xs.append(detection["x"])
                ys.append(detection["y"])
                radii.append(detection["radius"])
                area = detection["area"]
                areas.append(np.nan if area is None else area)

            display = frame.copy()
            draw_detection(display, detection)
            draw_track(display, xs, ys)
            if not args.no_debug:
                cv2.imshow("foreground", foreground)
                cv2.imshow("threshold", threshold)
                cv2.imshow("clean_mask", clean)
            cv2.imshow("tracking", display)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                result(f"detections={len(ts)} saved=false stopped_by=escape")
                return 0
            if key == ord("q"):
                if not args.save:
                    result(f"detections={len(ts)} saved=false stopped_by=q")
                    return 0
                if not ts:
                    error("No bead detections were available to save.")
                    return 1

                saved_path = save_tracking_csv(output, ts, xs, ys, radii, areas)
                ok(f"Saved {len(ts)} detections to {saved_path}")
                result(f"detections={len(ts)} saved=true path={saved_path}")
                return 0
    except KeyboardInterrupt:
        warn("Tracking interrupted; no data were saved.")
        result(f"detections={len(ts)} saved=false stopped_by=interrupt")
        return 0
    except (OSError, RuntimeError, cv2.error) as exc:
        error(str(exc))
        return 1
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
