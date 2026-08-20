import argparse

import cv2

from beadtrack import messages
from beadtrack.camera import open_camera, read_frame_or_raise


def main():
    parser = argparse.ArgumentParser(description="View camera stream only.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--width", type=int, default=None, help="Optional frame width.")
    parser.add_argument(
        "--height", type=int, default=None, help="Optional frame height."
    )
    parser.add_argument("--fps", type=int, default=None, help="Optional FPS request.")

    args = parser.parse_args()

    cap = open_camera(
        camera_index=args.camera,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )

    messages.info("Camera view started. Press q or ESC to quit.")

    while True:
        try:
            frame = read_frame_or_raise(cap)
        except RuntimeError:
            messages.error("Could not read frame.")
            break

        cv2.imshow("camera", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
