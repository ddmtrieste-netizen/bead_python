import argparse
import time
import subprocess

import cv2
import numpy as np

from _common import (
    open_camera,
    create_background_subtractor,
    compute_foreground_masks,
    detect_largest_contour_circle,
    draw_detection,
    draw_track,
    save_tracking_csv,
    timestamp_string,
)


def main():
    parser = argparse.ArgumentParser(description="Track largest moving bead using background subtraction.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--save", type=bool, default=1, help="Save data to CSV.")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path.")

    parser.add_argument("--history", type=int, default=500, help="MOG2 history.")
    parser.add_argument("--var-threshold", type=float, default=100, help="MOG2 variance threshold.")
    parser.add_argument("--threshold", type=int, default=120, help="Binary threshold.")
    parser.add_argument("--kernel", type=int, default=3, help="Morphological kernel size.")
    parser.add_argument("--dilate", type=int, default=2, help="Dilation iterations.")

    parser.add_argument("--min-area", type=float, default=50, help="Minimum contour area.")
    parser.add_argument("--max-area", type=float, default=None, help="Maximum contour area.")
    parser.add_argument("--no-debug", action="store_true", help="Hide mask debug windows.")

    args = parser.parse_args()

    if args.output is None:
        args.output = f"data/processed/track_{timestamp_string()}.csv"

    cap = open_camera(camera_index=args.camera)

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

    flag_system_time = False

    print("Tracking started.")
    print("Press q to save and quit.")
    print("Press ESC to quit without saving.")
    while True:
        ret, frame = cap.read()

        if not ret:
            print("Could not read frame.")
            break

        now = time.time()
        if not flag_system_time:
            print(f"System time - frame 1 {now}")
            flag_system_time  = True
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

        if key == ord("q"):
            if len(ts) > 0 and args.save:
                save_tracking_csv(args.output, ts, xs, ys, radii, areas)
                print(f"Saved {len(ts)} points to: {args.output}")
                print(f"System end time {time.time()}")
            else:
                print("No detections saved.")
            break

        if key == 27:
            print("ESC pressed. Exiting without saving.")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
