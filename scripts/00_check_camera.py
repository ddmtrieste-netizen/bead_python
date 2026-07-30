"""Check that an OpenCV camera can be opened and read."""

import argparse

import cv2

from beadtrack.camera import open_camera, read_frame_or_raise
from beadtrack.console import error, result


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

    try:
        cap = open_camera(
            camera_index=args.camera,
            width=args.width,
            height=args.height,
            fps=args.fps,
        )
        frame = read_frame_or_raise(cap)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        result(
            f"camera={args.camera} opened=true frame_shape={frame.shape} "
            f"reported_width={width} reported_height={height} reported_fps={fps:g}"
        )
        return 0
    except (RuntimeError, cv2.error) as exc:
        error(str(exc))
        return 1
    finally:
        if cap is not None:
            cap.release()


if __name__ == "__main__":
    raise SystemExit(main())
