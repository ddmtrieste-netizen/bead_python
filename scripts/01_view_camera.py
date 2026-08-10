"""Open a camera preview without tracking or saving data."""

import argparse

import cv2

from beadtrack.camera import open_camera
from beadtrack.console import error, info, result, warn


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--width", type=int, default=None, help="Requested frame width.")
    parser.add_argument("--height", type=int, default=None, help="Requested frame height.")
    parser.add_argument("--fps", type=int, default=None, help="Requested frame rate.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    cap = None
    frames = 0

    try:
        cap = open_camera(
            camera_index=args.camera,
            width=args.width,
            height=args.height,
            fps=args.fps,
        )
        info("Camera preview started. Press q or ESC to stop.")

        while True:
            received, frame = cap.read()
            if not received or frame is None:
                error("Could not read frame from camera")
                return 1

            frames += 1
            cv2.imshow("camera", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in {ord("q"), 27}:
                result(f"camera={args.camera} frames={frames} stopped_by=user")
                return 0
    except KeyboardInterrupt:
        warn("Camera preview interrupted by user.")
        result(f"camera={args.camera} frames={frames} stopped_by=interrupt")
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
