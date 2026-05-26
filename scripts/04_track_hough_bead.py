import argparse
import time

import cv2
import numpy as np

from _common import (
    open_camera,
    draw_detection,
    draw_track,
    save_tracking_csv,
    timestamp_string,
)


def detect_hough_circle(
    frame,
    dp=1.2,
    min_dist=30,
    param1=100,
    param2=20,
    min_radius=3,
    max_radius=40,
):
    """
    Detect circular objects using the Hough Circle Transform.

    Returns the largest detected circle as:
    {
        "x": float,
        "y": float,
        "radius": float,
        "area": float
    }

    If no circle is detected, returns None.
    """

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Blur is important: Hough is very sensitive to noise.
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=float(dp),
        minDist=float(min_dist),
        param1=float(param1),
        param2=float(param2),
        minRadius=int(min_radius),
        maxRadius=int(max_radius),
    )

    if circles is None:
        return None

    circles = np.round(circles[0, :]).astype(int)

    # Choose the largest detected circle.
    best = max(circles, key=lambda c: c[2])

    x, y, r = best

    return {
        "x": float(x),
        "y": float(y),
        "radius": float(r),
        "area": float(np.pi * r * r),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Track a circular bead using Hough Circle Transform."
    )

    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--output", type=str, default=None)

    parser.add_argument("--dp", type=float, default=1.2)
    parser.add_argument("--min-dist", type=float, default=60)
    parser.add_argument("--param1", type=float, default=100)
    parser.add_argument("--param2", type=float, default=30)
    parser.add_argument("--min-radius", type=int, default=10)
    parser.add_argument("--max-radius", type=int, default=50)

    args = parser.parse_args()

    if args.output is None:
        args.output = f"data/processed/hough_track_{timestamp_string()}.csv"

    cap = open_camera(camera_index=args.camera)

    ts = []
    xs = []
    ys = []
    radii = []
    areas = []

    print("Hough tracking started.")
    print("Press q to save and quit.")
    print("Press ESC to quit without saving.")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Could not read frame.")
            break

        now = time.time()

        detection = detect_hough_circle(
            frame,
            dp=args.dp,
            min_dist=args.min_dist,
            param1=args.param1,
            param2=args.param2,
            min_radius=args.min_radius,
            max_radius=args.max_radius,
        )

        if detection is not None:
            ts.append(now)
            xs.append(detection["x"])
            ys.append(detection["y"])
            radii.append(detection["radius"])
            areas.append(detection["area"])

        display = frame.copy()
        draw_detection(display, detection)
        draw_track(display, xs, ys)

        cv2.imshow("hough_tracking", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            if len(ts) > 0:
                save_tracking_csv(args.output, ts, xs, ys, radii, areas)
                print(f"Saved {len(ts)} points to: {args.output}")
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
