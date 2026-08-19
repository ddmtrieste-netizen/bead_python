"""OpenCV camera acquisition helpers."""

import cv2
import numpy as np
from numpy.typing import NDArray

__all__ = ["open_camera", "read_frame_or_raise"]


def open_camera(
    camera_index: int = 0,
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
) -> cv2.VideoCapture:
    """Open and configure a camera, raising if it is unavailable."""
    capture = cv2.VideoCapture(camera_index)

    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")

    if width is not None:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)

    if height is not None:
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    if fps is not None:
        capture.set(cv2.CAP_PROP_FPS, fps)

    return capture


def read_frame_or_raise(capture: cv2.VideoCapture) -> NDArray[np.uint8]:
    """Read and return one frame, raising if acquisition fails."""
    success, frame = capture.read()

    if not success or frame is None:
        raise RuntimeError("Could not read frame from camera")

    return np.asarray(frame, dtype=np.uint8)
