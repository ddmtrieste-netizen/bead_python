import csv

import cv2
import numpy as np
import pytest

from beadtrack.camera import open_camera, read_frame_or_raise
from beadtrack.data import load_tracking_csv, save_tracking_csv
from beadtrack.serial_io import send_line
from beadtrack.tracking import compute_foreground_masks, detect_largest_contour_circle


def test_open_camera_applies_properties(monkeypatch):
    class FakeCapture:
        def __init__(self, index):
            self.index = index
            self.properties = []
            self.released = False

        def isOpened(self):
            return True

        def set(self, key, value):
            self.properties.append((key, value))

    capture = FakeCapture(2)
    monkeypatch.setattr(cv2, "VideoCapture", lambda index: capture)

    returned = open_camera(2, width=640, height=480, fps=30)

    assert returned is capture
    assert capture.properties == [
        (cv2.CAP_PROP_FRAME_WIDTH, 640),
        (cv2.CAP_PROP_FRAME_HEIGHT, 480),
        (cv2.CAP_PROP_FPS, 30),
    ]


def test_open_camera_failure_releases_capture(monkeypatch):
    class FakeCapture:
        released = False

        def isOpened(self):
            return False

        def release(self):
            self.released = True

    capture = FakeCapture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda index: capture)

    with pytest.raises(RuntimeError, match="Could not open camera"):
        open_camera()

    assert capture.released is True


def test_read_frame_rejects_missing_frame():
    class FakeCapture:
        def read(self):
            return False, None

    with pytest.raises(RuntimeError, match="Could not read frame"):
        read_frame_or_raise(FakeCapture())


def test_tracking_csv_round_trip(tmp_path):
    output = tmp_path / "nested" / "track.csv"
    save_tracking_csv(
        output,
        ts=[10.0, 10.5],
        xs=[1, 2],
        ys=[3, 4],
        radii=[5, 6],
        areas=[7, 8],
    )

    t, x, y, radius, area = load_tracking_csv(output)

    assert t == [0.0, 0.5]
    assert x == [1.0, 2.0]
    assert y == [3.0, 4.0]
    assert radius == [5.0, 6.0]
    assert area == [7.0, 8.0]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([["t", "x"], ["0", "1"]], "missing columns"),
        ([["t", "x", "y", "radius", "area"]], "contains no data"),
        (
            [["t", "x", "y", "radius", "area"], ["0", "invalid", "2", "3", "4"]],
            "Invalid numeric value",
        ),
    ],
)
def test_tracking_csv_validation(tmp_path, rows, message):
    source = tmp_path / "invalid.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows(rows)

    with pytest.raises(ValueError, match=message):
        load_tracking_csv(source)


def test_detect_largest_contour_circle():
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.circle(mask, (25, 25), 5, 255, -1)
    cv2.circle(mask, (70, 70), 10, 255, -1)

    detection = detect_largest_contour_circle(mask, min_area=20)

    assert detection["x"] == pytest.approx(70, abs=1)
    assert detection["y"] == pytest.approx(70, abs=1)
    assert detection["radius"] == pytest.approx(10, abs=1)


def test_foreground_masks_control_learning_rate_and_shadow_threshold():
    class FakeBackgroundSubtractor:
        learning_rate = None

        def apply(self, _frame, learningRate=None):
            self.learning_rate = learningRate
            return np.array([[0, 127, 255]], dtype=np.uint8)

    subtractor = FakeBackgroundSubtractor()
    frame = np.zeros((1, 3, 3), dtype=np.uint8)

    foreground, threshold, clean = compute_foreground_masks(
        frame,
        subtractor,
        threshold_value=127,
        kernel_size=1,
        dilation_iterations=0,
        learning_rate=0.0,
    )

    assert subtractor.learning_rate == 0.0
    assert foreground.tolist() == [[0, 127, 255]]
    assert threshold.tolist() == [[0, 0, 255]]
    assert clean.tolist() == [[0, 0, 255]]


def test_foreground_masks_preserve_automatic_learning_call():
    class FakeBackgroundSubtractor:
        called = False

        def apply(self, _frame):
            self.called = True
            return np.array([[0, 127, 255]], dtype=np.uint8)

    subtractor = FakeBackgroundSubtractor()

    _foreground, threshold, _clean = compute_foreground_masks(
        np.zeros((1, 3, 3), dtype=np.uint8),
        subtractor,
        threshold_value=120,
        kernel_size=1,
        dilation_iterations=0,
    )

    assert subtractor.called is True
    assert threshold.tolist() == [[0, 255, 255]]


def test_send_line_uses_newline_and_flushes():
    class FakeSerial:
        def __init__(self):
            self.writes = []
            self.flushed = False

        def write(self, payload):
            self.writes.append(payload)

        def flush(self):
            self.flushed = True

    serial_port = FakeSerial()
    payload = send_line(serial_port, "5\n")

    assert payload == b"5\n"
    assert serial_port.writes == [b"5\n"]
    assert serial_port.flushed is True
