import argparse
import cv2
from _common import open_camera, read_frame_or_raise


def main():
    parser = argparse.ArgumentParser(description="Check if a camera can be opened.")
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

    frame = read_frame_or_raise(cap)

    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_fps = cap.get(cv2.CAP_PROP_FPS)

    print("Camera opened successfully.")
    print(f"Camera index: {args.camera}")
    print(f"Frame shape: {frame.shape}")
    print(f"Reported width: {actual_width}")
    print(f"Reported height: {actual_height}")
    print(f"Reported FPS: {actual_fps}")

    cap.release()


if __name__ == "__main__":
    main()
