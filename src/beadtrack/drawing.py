"""Drawing helpers for bead detections and trajectories."""

from collections.abc import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from .models import Detection

__all__ = ["draw_detection", "draw_detections", "draw_track"]

Color = tuple[int, int, int]


def draw_detection(
    frame: NDArray[np.uint8],
    detection: Detection | None,
    circle_color: Color = (255, 255, 0),
) -> NDArray[np.uint8]:
    """Draw one circular bead detection in place and return the frame."""
    if detection is None:
        return frame

    center = (int(detection.x), int(detection.y))
    radius = int(detection.radius)

    cv2.circle(frame, center, radius, circle_color, 2)
    cv2.circle(frame, center, 2, (0, 0, 255), -1)
    return frame


def draw_detections(
    frame: NDArray[np.uint8],
    detections: Sequence[Detection],
) -> NDArray[np.uint8]:
    """Draw multiple bead detections in place and return the frame."""
    for detection in detections:
        draw_detection(frame, detection)
    return frame


def draw_track(
    frame: NDArray[np.uint8],
    x_positions: Sequence[float],
    y_positions: Sequence[float],
    max_points: int = 300,
) -> NDArray[np.uint8]:
    """Draw the most recent trajectory points in place and return the frame."""
    if len(x_positions) != len(y_positions):
        raise ValueError("x_positions and y_positions must have equal length")
    if len(x_positions) < 2:
        return frame

    start = max(1, len(x_positions) - max_points)
    for index in range(start, len(x_positions)):
        previous = (int(x_positions[index - 1]), int(y_positions[index - 1]))
        current = (int(x_positions[index]), int(y_positions[index]))
        cv2.line(frame, previous, current, (0, 255, 255), 1)

    return frame
