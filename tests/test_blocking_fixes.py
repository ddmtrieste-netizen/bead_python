import csv
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "bead_python_matplotlib"),
)


def load_module(name, relative_path, import_dir=None):
    if import_dir is not None:
        sys.path.insert(0, str(ROOT / import_dir))

    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if import_dir is not None:
            sys.path.pop(0)


def test_hall_fft_preserves_rotation_direction():
    hall = load_module(
        "mapping_hall_rpm",
        "pipelines/Mapping_Hall_RPM_pipeline/mapping_hall_RPM.py",
    )
    time_s = np.linspace(0.0, 4.0, 400, endpoint=False)

    positive = hall.estimate_rotation_from_fft(
        time_s,
        np.cos(2.0 * np.pi * time_s),
        np.sin(2.0 * np.pi * time_s),
    )
    negative = hall.estimate_rotation_from_fft(
        time_s,
        np.cos(-2.0 * np.pi * time_s),
        np.sin(-2.0 * np.pi * time_s),
    )

    assert positive["fft_rpm"] == pytest.approx(60.0)
    assert negative["fft_rpm"] == pytest.approx(-60.0)


def test_tracker_handles_a_run_without_detections(monkeypatch, tmp_path):
    mapping = load_module(
        "mapping_rpm",
        "pipelines/Mapping_RPM_pipeline/mapping_RPM.py",
        import_dir="pipelines/Mapping_RPM_pipeline",
    )

    class FakeCamera:
        def read(self):
            return True, np.zeros((10, 10, 3), dtype=np.uint8)

    monkeypatch.setattr(mapping, "create_background_subtractor", lambda **kwargs: object())
    monkeypatch.setattr(
        mapping,
        "compute_foreground_masks",
        lambda *args, **kwargs: (
            np.zeros((10, 10), dtype=np.uint8),
            np.zeros((10, 10), dtype=np.uint8),
            np.zeros((10, 10), dtype=np.uint8),
        ),
    )
    monkeypatch.setattr(mapping, "detect_largest_contour_circle", lambda *args, **kwargs: None)
    monkeypatch.setattr(mapping, "draw_detection", lambda frame, detection: frame)
    monkeypatch.setattr(mapping, "draw_track", lambda frame, xs, ys: frame)
    monkeypatch.setattr(mapping.cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(mapping.cv2, "waitKey", lambda delay: ord("q"))
    monkeypatch.setattr(mapping.cv2, "destroyAllWindows", lambda: None)

    continue_sweep = mapping.tracker(
        cap=FakeCamera(),
        rpm=5,
        recording_time_sec=1.0,
        output_dir=tmp_path,
        warmup_time_sec=0.0,
    )

    assert continue_sweep is True
    assert not list(tmp_path.glob("*.csv"))


def test_motor_stop_command_is_always_zero_rpm():
    mapping = load_module(
        "mapping_rpm_stop",
        "pipelines/Mapping_RPM_pipeline/mapping_RPM.py",
        import_dir="pipelines/Mapping_RPM_pipeline",
    )

    class FakeSerial:
        is_open = True

        def __init__(self):
            self.writes = []

        def write(self, value):
            self.writes.append(value)

        def flush(self):
            pass

    serial_port = FakeSerial()
    mapping.stop_motor(serial_port)

    assert serial_port.writes == [b"0\n"]


def test_rpm_analysis_reports_motor_command_in_rpm(tmp_path):
    graphs = load_module(
        "graphs_rpm",
        "pipelines/Mapping_RPM_pipeline/graphs_RPM.py",
    )
    csv_path = tmp_path / "5_RPM.csv"
    time_s = np.linspace(0.0, 5.0, 500, endpoint=False)

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["t", "x", "y", "radius", "area"])
        for t in time_s:
            writer.writerow([t, np.cos(2.0 * np.pi * t), 0.0, 1.0, 1.0])

    result = graphs.analyze_single_file(
        speed=5,
        data_dir=tmp_path,
        method="raw",
        signal_name="x",
    )

    assert result["motor_rpm_command"] == 5
    assert result["bead_rpm_fft"] == pytest.approx(60.0, rel=1e-4)
