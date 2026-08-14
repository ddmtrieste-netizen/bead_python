import csv
import time
import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt
import scipy


# ---------------------------------------------------------------------
# Camera utilities
# ---------------------------------------------------------------------

def open_camera(camera_index=0, width=None, height=None, fps=None):
    """
    Open a standard webcam using OpenCV.

    Parameters
    ----------
    camera_index : int
        Camera index. Usually 0 for the default webcam.
    width, height : int or None
        Optional requested frame size.
    fps : int or None
        Optional requested acquisition FPS.

    Returns
    -------
    cap : cv2.VideoCapture
        OpenCV camera object.
    """
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")

    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))

    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))

    if fps is not None:
        cap.set(cv2.CAP_PROP_FPS, int(fps))

    return cap


def read_frame_or_raise(cap):
    """
    Read one frame from an OpenCV camera.
    """
    ret, frame = cap.read()

    if not ret or frame is None:
        raise RuntimeError("Could not read frame from camera")

    return frame


# ---------------------------------------------------------------------
# Background subtraction
# ---------------------------------------------------------------------

def create_background_subtractor(
    history=500,
    var_threshold=100,
    detect_shadows=True,
):
    """
    Create a MOG2 background subtractor.

    history:
        Number of previous frames used to learn the background.

    var_threshold:
        Sensitivity threshold. Lower values are more sensitive.
        Higher values are less sensitive.
    """
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
    learning_rate=None
):
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


# ---------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------

def detect_largest_contour_circle(mask, min_area=50, max_area=None):
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
    detection : dict or None
        {
            "x": float,
            "y": float,
            "radius": float,
            "area": float
        }
    """
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

        if area > best_area:
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
    """
    Detect circles using the Hough transform.

    This is useful when the bead is visually circular but background
    subtraction is not reliable.

    Returns
    -------
    detections : list[dict]
        Each dict contains x, y, radius, area.
    """
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

    circles = np.round(circles[0, :]).astype(int)

    detections = []

    for x, y, radius in circles:
        detections.append({
            "x": float(x),
            "y": float(y),
            "radius": float(radius),
            "area": np.nan,
        })

    return detections


# ---------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------

def draw_detection(frame, detection, circle_color=(255, 255, 0)):
    """
    Draw one circular detection on a frame.
    """
    if detection is None:
        return frame

    x = int(detection["x"])
    y = int(detection["y"])
    r = int(detection["radius"])

    cv2.circle(frame, (x, y), r, circle_color, 2)
    cv2.circle(frame, (x, y), 2, (0, 0, 255), -1)

    return frame


def draw_detections(frame, detections):
    """
    Draw multiple circular detections.
    """
    for detection in detections:
        draw_detection(frame, detection)

    return frame


def draw_track(frame, xs, ys, max_points=300):
    """
    Draw recent trajectory on frame.
    """
    if len(xs) < 2:
        return frame

    start = max(0, len(xs) - int(max_points))

    for i in range(start + 1, len(xs)):
        p0 = (int(xs[i - 1]), int(ys[i - 1]))
        p1 = (int(xs[i]), int(ys[i]))
        cv2.line(frame, p0, p1, (0, 255, 255), 1)

    return frame


# ---------------------------------------------------------------------
# Signal Processing
# ---------------------------------------------------------------------

def smooth_sav(signal, window=301, ord=3):
    y = scipy.signal.savgol_filter(
            signal,
            window_length = window,
            polyorder = ord
        )

    return y

def smooth_median(signal, window=101):
    y = scipy.ndimage.median_filter(
            signal,
            size = window,
            mode="wrap"
        )

    return y
    




# ---------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------

def ensure_parent_dir(filename):
    """
    Ensure that the parent directory of filename exists.
    """
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    return filename


def save_tracking_csv(filename, ts, xs, ys, radii, areas):
    """
    Save tracking data to CSV.

    Columns:
    t, x, y, radius, area

    Time is shifted so that the first saved detection has t = 0.
    """
    filename = ensure_parent_dir(filename)

    if len(ts) == 0:
        raise RuntimeError("No tracking data to save")

    t0 = ts[0]

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "radius", "area"])

        for t, x, y, radius, area in zip(ts, xs, ys, radii, areas):
            writer.writerow([
                float(t - t0),
                float(x),
                float(y),
                float(radius),
                float(area),
            ])

    return filename


def load_csv(filename):
    t = []
    x = []
    y = []
    radius = []
    area = []

    with open(filename, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            t.append(float(row["t"]))
            x.append(float(row["x"]))
            y.append(float(row["y"]))
            radius.append(float(row["radius"]))
            area.append(float(row["area"]))

    return t, x, y, radius, area


def apply_screen_scale(scale):
    plt.rcParams.update({
        "font.size": 14 * scale,
        "axes.titlesize": 18 * scale,
        "axes.labelsize": 16 * scale,
        "xtick.labelsize": 13 * scale,
        "ytick.labelsize": 13 * scale,
        "legend.fontsize": 13 * scale,
        "lines.linewidth": 2.0 * scale,
        "grid.linewidth": 0.8 * scale,
    })


def maximize_window():
    manager = plt.get_current_fig_manager()

    try:
        manager.window.showMaximized()
    except Exception:
        try:
            manager.full_screen_toggle()
        except Exception:
            pass


def timestamp_string():
    """
    Return compact timestamp string for filenames.
    """
    return time.strftime("%Y%m%d_%H%M%S")

# Console styling


def message(level, text, *, stream=None):
    """Print one tagged message."""
    if stream is None:
        stream = sys.stderr if level in {"WARN", "ERROR"} else sys.stdout
    print(f"[{level}] {text}", file=stream, flush=True)


def info(text):
    message("INFO", text)


def ok(text):
    message("OK", text)


def result(text):
    message("RESULT", text)


def warn(text):
    message("WARN", text)


def error(text):
    message("ERROR", text)
