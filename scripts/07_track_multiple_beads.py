"""Track multiple moving beads using the same MOG2 pipeline as script 02."""

import argparse
import csv
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from _common import (
    compute_foreground_masks,
    create_background_subtractor,
    open_camera,
    timestamp_string,
)


CSV_FIELDS = ("bead_id", "t", "x", "y", "radius", "area")
COLORS = [
    (0, 255, 255),
    (255, 128, 0),
    (0, 255, 0),
    (255, 0, 255),
    (0, 128, 255),
    (255, 255, 0),
    (128, 255, 128),
    (255, 128, 255),
]


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV. Default: data/multiple_beads/track_<timestamp>.csv",
    )
    parser.add_argument("--history", type=int, default=500, help="MOG2 history.")
    parser.add_argument(
        "--var-threshold",
        type=float,
        default=100,
        help="MOG2 variance threshold.",
    )
    parser.add_argument("--threshold", type=int, default=100, help="Binary mask threshold.")
    parser.add_argument("--kernel", type=int, default=3, help="Morphology kernel size.")
    parser.add_argument("--dilate", type=int, default=1, help="Dilation iterations.")
    parser.add_argument("--min-area", type=float, default=20, help="Minimum contour area [px^2].")
    parser.add_argument("--max-area", type=float, default=2000, help="Maximum contour area [px^2].")
    parser.add_argument("--min-radius", type=float, default=2, help="Minimum radius [px].")
    parser.add_argument("--max-radius", type=float, default=30, help="Maximum radius [px].")
    parser.add_argument(
        "--min-circularity",
        type=float,
        default=0.10,
        help="Minimum 4*pi*area/perimeter^2 (default: 0.10).",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=70,
        help="Maximum ID-association distance [px].",
    )
    parser.add_argument(
        "--roi-circle",
        type=parse_circle,
        default=(320, 240, 190),
        metavar="X,Y,R",
        help="Circular work area (default: 320,240,190).",
    )
    parser.add_argument("--no-roi", action="store_true", help="Disable the circular work area.")
    parser.add_argument("--no-debug", action="store_true", help="Hide mask debug windows.")
    return parser


def parse_circle(text):
    try:
        x, y, radius = (int(part.strip()) for part in text.split(","))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("circle must be X,Y,R") from exc
    if x < 0 or y < 0 or radius <= 0:
        raise argparse.ArgumentTypeError("circle center must be non-negative and radius positive")
    return x, y, radius


def validate_args(parser, args):
    if args.history <= 0:
        parser.error("--history must be positive")
    if not 0 <= args.threshold <= 255:
        parser.error("--threshold must be between 0 and 255")
    if args.kernel <= 0 or args.kernel % 2 == 0:
        parser.error("--kernel must be a positive odd number")
    if args.dilate < 0:
        parser.error("--dilate cannot be negative")
    if args.min_area <= 0 or args.max_area <= args.min_area:
        parser.error("area limits must satisfy 0 < min < max")
    if args.min_radius <= 0 or args.max_radius <= args.min_radius:
        parser.error("radius limits must satisfy 0 < min < max")
    if not 0 <= args.min_circularity <= 1:
        parser.error("--min-circularity must be between 0 and 1")
    if args.max_distance <= 0:
        parser.error("--max-distance must be positive")


def detect_all_contour_circles(
    mask,
    min_area=50,
    max_area=3000,
    min_radius=3,
    max_radius=40,
    min_circularity=0.20,
):
    """Return every MOG2 contour accepted by the geometric filters."""
    contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not min_area <= area <= max_area:
            continue

        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue
        circularity = 4.0 * math.pi * area / (perimeter * perimeter)
        if circularity < min_circularity:
            continue

        (x, y), radius = cv2.minEnclosingCircle(contour)
        if not min_radius <= radius <= max_radius:
            continue
        detections.append(
            {
                "x": float(x),
                "y": float(y),
                "radius": float(radius),
                "area": area,
                "circularity": circularity,
            }
        )
    return sorted(detections, key=lambda item: (item["x"], item["y"]))


def apply_circular_roi(mask, circle):
    if circle is None:
        return mask
    center_x, center_y, radius = circle
    roi_mask = np.zeros_like(mask)
    cv2.circle(roi_mask, (center_x, center_y), radius, 255, -1)
    return cv2.bitwise_and(mask, roi_mask)


@dataclass
class Track:
    bead_id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    missed: int = 0
    history: list = field(default_factory=list)

    def predict(self):
        # A short velocity prediction absorbs MOG2 centroid jumps without
        # extrapolating a tangent too far along the curved orbit.
        frames = min(self.missed + 1, 3)
        return self.x + self.vx * frames, self.y + self.vy * frames


class DistanceTracker:
    """Assign persistent IDs using predicted position and nearest distance."""

    def __init__(self, max_distance=70, max_missed=30):
        self.max_distance = float(max_distance)
        self.max_missed = int(max_missed)
        self.tracks = {}
        self.next_id = 0

    def update(self, detections):
        candidates = []
        for bead_id, track in self.tracks.items():
            predicted_x, predicted_y = track.predict()
            for detection_index, detection in enumerate(detections):
                distance = math.hypot(
                    detection["x"] - predicted_x,
                    detection["y"] - predicted_y,
                )
                if distance <= self.max_distance:
                    candidates.append((distance, bead_id, detection_index))

        used_tracks = set()
        used_detections = set()
        matches = []
        for _distance, bead_id, detection_index in sorted(candidates):
            if bead_id in used_tracks or detection_index in used_detections:
                continue
            used_tracks.add(bead_id)
            used_detections.add(detection_index)
            matches.append((bead_id, detection_index))

        visible = []
        for bead_id, detection_index in matches:
            track = self.tracks[bead_id]
            detection = detections[detection_index]
            elapsed_frames = track.missed + 1
            measured_vx = (detection["x"] - track.x) / elapsed_frames
            measured_vy = (detection["y"] - track.y) / elapsed_frames
            track.vx = 0.5 * track.vx + 0.5 * measured_vx
            track.vy = 0.5 * track.vy + 0.5 * measured_vy
            track.x = detection["x"]
            track.y = detection["y"]
            track.missed = 0
            track.history.append((track.x, track.y))
            visible.append((bead_id, detection))

        for bead_id, track in list(self.tracks.items()):
            if bead_id not in used_tracks:
                track.missed += 1
                if track.missed > self.max_missed:
                    del self.tracks[bead_id]

        for detection_index, detection in enumerate(detections):
            if detection_index in used_detections:
                continue
            bead_id = self.next_id
            self.next_id += 1
            track = Track(bead_id, detection["x"], detection["y"])
            track.history.append((track.x, track.y))
            self.tracks[bead_id] = track
            visible.append((bead_id, detection))

        return sorted(visible, key=lambda item: item[0])


def draw_tracks(frame, tracker, visible):
    for bead_id, track in tracker.tracks.items():
        color = COLORS[bead_id % len(COLORS)]
        points = track.history[-300:]
        for first, second in zip(points, points[1:]):
            cv2.line(frame, tuple(map(int, first)), tuple(map(int, second)), color, 1)

    for bead_id, detection in visible:
        color = COLORS[bead_id % len(COLORS)]
        center = (int(detection["x"]), int(detection["y"]))
        cv2.circle(frame, center, int(detection["radius"]), color, 2)
        cv2.putText(
            frame,
            f"ID {bead_id}",
            (center[0] + 5, center[1] - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )


def save_long_csv(filename, records):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    return path


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    output = args.output or f"data/multiple_beads/track_{timestamp_string()}.csv"

    cap = None
    tracker = DistanceTracker(max_distance=args.max_distance)
    records = []
    start_time = time.monotonic()

    try:
        cap = open_camera(camera_index=args.camera)
        background = create_background_subtractor(
            history=args.history,
            var_threshold=args.var_threshold,
            detect_shadows=True,
        )
        print("Multiple-bead MOG2 tracking started.")
        print("Press q to save and quit; press ESC to discard.")

        while True:
            received, frame = cap.read()
            if not received or frame is None:
                raise RuntimeError("Could not read frame from camera")

            now = time.monotonic()
            foreground, threshold, clean = compute_foreground_masks(
                frame,
                background,
                threshold_value=args.threshold,
                kernel_size=args.kernel,
                dilation_iterations=args.dilate,
            )
            roi_circle = None if args.no_roi else args.roi_circle
            clean = apply_circular_roi(clean, roi_circle)
            detections = detect_all_contour_circles(
                clean,
                min_area=args.min_area,
                max_area=args.max_area,
                min_radius=args.min_radius,
                max_radius=args.max_radius,
                min_circularity=args.min_circularity,
            )
            visible = tracker.update(detections)
            elapsed = now - start_time
            for bead_id, detection in visible:
                records.append(
                    {
                        "bead_id": bead_id,
                        "t": f"{elapsed:.6f}",
                        "x": f"{detection['x']:.6f}",
                        "y": f"{detection['y']:.6f}",
                        "radius": f"{detection['radius']:.6f}",
                        "area": f"{detection['area']:.6f}",
                    }
                )

            display = frame.copy()
            draw_tracks(display, tracker, visible)
            if roi_circle is not None:
                cv2.circle(
                    display,
                    (roi_circle[0], roi_circle[1]),
                    roi_circle[2],
                    (255, 255, 255),
                    1,
                )
            cv2.putText(
                display,
                f"visible beads: {len(visible)}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            if not args.no_debug:
                cv2.imshow("foreground", foreground)
                cv2.imshow("threshold", threshold)
                cv2.imshow("clean_mask", clean)
            cv2.imshow("multiple bead tracking", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                if records:
                    saved = save_long_csv(output, records)
                    print(f"Saved {len(records)} detections to: {saved}")
                else:
                    print("No detections saved.")
                return 0
            if key == 27:
                print("ESC pressed. Exiting without saving.")
                return 0
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
