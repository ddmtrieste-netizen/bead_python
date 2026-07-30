"""Camera access helpers shared by scripts and pipelines."""

import cv2


def open_camera(camera_index=0, width=None, height=None, fps=None):
    """Open an OpenCV camera and apply the requested capture properties."""
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open camera index {camera_index}")

    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    if fps is not None:
        cap.set(cv2.CAP_PROP_FPS, int(fps))

    return cap


def read_frame_or_raise(cap):
    """Read one frame or raise a runtime error."""
    received, frame = cap.read()
    if not received or frame is None:
        raise RuntimeError("Could not read frame from camera")
    return frame
