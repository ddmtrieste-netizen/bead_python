"""Image processing and drawing helpers for bead tracking."""

import cv2
import numpy as np


def create_background_subtractor(
    history=500,
    var_threshold=100,
    detect_shadows=True,
):
    """Create a MOG2 background subtractor."""
    return cv2.createBackgroundSubtractorMOG2(
        history=int(history),
        varThreshold=float(var_threshold),
        detectShadows=bool(detect_shadows),
    )


def compute_foreground_masks(
    frame,
    bg_subtractor,
    threshold_value=120,
    kernel_size=3,
    dilation_iterations=2,
    learning_rate=None,
):
    """Return the exact MOG2 masks used by contour detection.

    ``learning_rate=None`` preserves OpenCV's automatic learning rate. Pass
    ``0.0`` to freeze an initialized model or a value in ``(0, 1]`` to
    control adaptation explicitly.

    With MOG2 shadow detection enabled, the raw mask normally encodes
    background as 0, shadows as 127, and foreground as 255. Consequently, a
    binary threshold below 127 includes shadows while a threshold of 127 or
    greater excludes them.
    """
    if learning_rate is None:
        foreground = bg_subtractor.apply(frame)
    else:
        foreground = bg_subtractor.apply(
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
    return foreground, threshold, clean


def detect_largest_contour_circle(mask, min_area=50, max_area=None):
    """Return the largest accepted contour as a circular detection."""
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    best_detection = None
    best_area = -1.0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < float(min_area):
            continue
        if max_area is not None and area > float(max_area):
            continue
        if area <= best_area:
            continue

        (x, y), radius = cv2.minEnclosingCircle(contour)
        best_detection = {
            "x": float(x),
            "y": float(y),
            "radius": float(radius),
            "area": float(area),
        }
        best_area = area

    return best_detection


def detect_hough_circles(
    frame,
    dp=1.2,
    min_dist=20,
    param1=100,
    param2=15,
    min_radius=1,
    max_radius=30,
):
    """Return all circles detected with the Hough transform."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=float(dp),
        minDist=float(min_dist),
        param1=float(param1),
        param2=float(param2),
        minRadius=int(min_radius),
        maxRadius=int(max_radius),
    )
    if circles is None:
        return []

    return [
        {
            "x": float(x),
            "y": float(y),
            "radius": float(radius),
            "area": float(np.pi * radius * radius),
        }
        for x, y, radius in np.round(circles[0, :]).astype(int)
    ]


def draw_detection(frame, detection, circle_color=(255, 255, 0)):
    """Draw one circular detection in place."""
    if detection is None:
        return frame
    x = int(detection["x"])
    y = int(detection["y"])
    radius = int(detection["radius"])
    cv2.circle(frame, (x, y), radius, circle_color, 2)
    cv2.circle(frame, (x, y), 2, (0, 0, 255), -1)
    return frame


def draw_detections(frame, detections):
    """Draw multiple circular detections in place."""
    for detection in detections:
        draw_detection(frame, detection)
    return frame


def draw_track(frame, xs, ys, max_points=300):
    """Draw recent trajectory points in place."""
    if len(xs) < 2:
        return frame

    start = max(0, len(xs) - int(max_points))
    for index in range(start + 1, len(xs)):
        previous = (int(xs[index - 1]), int(ys[index - 1]))
        current = (int(xs[index]), int(ys[index]))
        cv2.line(frame, previous, current, (0, 255, 255), 1)
    return frame
