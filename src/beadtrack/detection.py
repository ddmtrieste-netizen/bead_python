"""Bead detection using background subtraction and circle detection."""

import cv2
import numpy as np
from numpy.typing import NDArray

from .models import Detection

__all__ = [
    "Detection",
    "compute_foreground_masks",
    "create_background_subtractor",
    "detect_hough_circles",
    "detect_largest_contour_circle",
]


# ---------------------------------------------------------------------
# Background subtraction
# ---------------------------------------------------------------------


def create_background_subtractor(
    history: int = 500,
    var_threshold: float = 100,
    detect_shadows: bool = True,
) -> cv2.BackgroundSubtractorMOG2:
    """Create a MOG2 background model for foreground segmentation."""
    return cv2.createBackgroundSubtractorMOG2(
        history=int(history),
        varThreshold=float(var_threshold),
        detectShadows=bool(detect_shadows),
    )


def compute_foreground_masks(
    frame: NDArray[np.uint8],
    background_subtractor: cv2.BackgroundSubtractorMOG2,
    threshold_value: int = 120,
    kernel_size: int = 3,
    dilation_iterations: int = 2,
    learning_rate: float | None = None,
) -> tuple[NDArray[np.uint8], NDArray[np.uint8], NDArray[np.uint8]]:
    """
    Compute foreground masks from one frame.

    Pipeline:
    frame
        -> background subtraction
        -> binary threshold
        -> dilation

    Returns
    -------
    foreground : ndarray
        Raw foreground mask from background subtractor.

    threshold : ndarray
        Binary thresholded mask.

    clean : ndarray
        Dilated mask used for contour detection.
    """

    if learning_rate is None:
        foreground = background_subtractor.apply(frame)
    else:
        foreground = background_subtractor.apply(
            frame,
            learningRate=float(learning_rate),
        )

    _, threshold = cv2.threshold(
        foreground.copy(),
        int(threshold_value),
        255,
        cv2.THRESH_BINARY,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (int(kernel_size), int(kernel_size)),
    )

    clean = cv2.dilate(
        threshold,
        kernel,
        iterations=int(dilation_iterations),
    )

    foreground = np.asarray(foreground, dtype=np.uint8)
    threshold = np.asarray(threshold, dtype=np.uint8)
    clean = np.asarray(clean, dtype=np.uint8)

    return foreground, threshold, clean


# ---------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------


def detect_largest_contour_circle(
    mask: NDArray[np.uint8],
    min_area: float = 50,
    max_area: float | None = None,
) -> Detection | None:
    """
    Detect the largest moving object in a binary mask.

    The selected contour is approximated with its minimum enclosing circle.

    Parameters
    ----------
    mask : ndarray
        Binary mask.

    min_area : float
        Minimum accepted contour area in pixels.

    max_area : float or None
        Optional maximum accepted contour area in pixels.

    Returns
    -------
    detection : Detection or None
        Geometry of the largest accepted contour, if one exists.
    """
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    best_detection: Detection | None = None
    best_area = -1.0

    for contour in contours:
        area = cv2.contourArea(contour)

        if area < float(min_area):
            continue

        if max_area is not None and area > float(max_area):
            continue

        if area > best_area:
            (x, y), radius = cv2.minEnclosingCircle(contour)

            best_detection = Detection(
                x=float(x),
                y=float(y),
                radius=float(radius),
                area=float(area),
            )

            best_area = area

    return best_detection


def detect_hough_circles(
    frame: NDArray[np.uint8],
    dp: float = 1.2,
    min_distance: float = 20,
    edge_threshold: float = 100,
    accumulator_threshold: float = 15,
    min_radius: int = 1,
    max_radius: int = 30,
) -> list[Detection]:
    """
    Detect circles using the Hough transform.

    This is useful when the bead is visually circular but background
    subtraction is not reliable.

    Returns
    -------
    detections : list[Detection]
        Circle geometry for each accepted candidate.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=float(dp),
        minDist=float(min_distance),
        param1=float(edge_threshold),
        param2=float(accumulator_threshold),
        minRadius=int(min_radius),
        maxRadius=int(max_radius),
    )

    if circles is None:
        return []

    circles = np.round(circles[0, :]).astype(int)

    detections: list[Detection] = []

    for x, y, radius in circles:
        detections.append(
            Detection(
                x=float(x),
                y=float(y),
                radius=float(radius),
                area=float("nan"),
            )
        )

    return detections
