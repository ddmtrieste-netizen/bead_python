import argparse

import cv2

from _common import open_camera


def main():
    parser = argparse.ArgumentParser(description="View camera stream only.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index.")
    parser.add_argument("--width", type=int, default=None, help="Optional frame width.")
    parser.add_argument("--height", type=int, default=None, help="Optional frame height.")
    parser.add_argument("--fps", type=int, default=None, help="Optional FPS request.")

    args = parser.parse_args()

    cap = open_camera(
        camera_index=args.camera,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )

    print("Camera view started.")
    print("Press q or ESC to quit.")

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Could not read frame.")
            break

        cv2.imshow("camera", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
