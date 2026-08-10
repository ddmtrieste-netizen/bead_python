import importlib.util
from pathlib import Path

import numpy as np
import serial


ROOT = Path(__file__).resolve().parents[1]


def load_script(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCamera:
    def __init__(self, frame=None):
        self.frame = np.zeros((20, 20, 3), dtype=np.uint8) if frame is None else frame
        self.released = False

    def read(self):
        return True, self.frame.copy()

    def release(self):
        self.released = True

    def get(self, _key):
        return 20


def silence_opencv(monkeypatch, module, key):
    monkeypatch.setattr(module.cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(module.cv2, "waitKey", lambda delay: key)
    monkeypatch.setattr(module.cv2, "destroyAllWindows", lambda: None)


def test_camera_check_reports_success_and_releases(monkeypatch):
    module = load_script("check_camera", "scripts/00_check_camera.py")
    camera = FakeCamera()
    monkeypatch.setattr(module, "open_camera", lambda **kwargs: camera)
    monkeypatch.setattr(module, "read_frame_or_raise", lambda cap: cap.frame)

    exit_code = module.main(["--camera", "0"])

    assert exit_code == 0
    assert camera.released is True


def test_camera_preview_releases_after_user_exit(monkeypatch):
    module = load_script("view_camera", "scripts/01_view_camera.py")
    camera = FakeCamera()
    monkeypatch.setattr(module, "open_camera", lambda **kwargs: camera)
    silence_opencv(monkeypatch, module, ord("q"))

    exit_code = module.main([])

    assert exit_code == 0
    assert camera.released is True


def configure_tracker(monkeypatch, module, detection, key):
    camera = FakeCamera()
    monkeypatch.setattr(module, "open_camera", lambda **kwargs: camera)
    monkeypatch.setattr(module, "create_background_subtractor", lambda **kwargs: object())
    monkeypatch.setattr(
        module,
        "compute_foreground_masks",
        lambda *args, **kwargs: (
            np.zeros((20, 20), dtype=np.uint8),
            np.zeros((20, 20), dtype=np.uint8),
            np.zeros((20, 20), dtype=np.uint8),
        ),
    )
    monkeypatch.setattr(
        module,
        "detect_largest_contour_circle",
        lambda *args, **kwargs: detection,
    )
    monkeypatch.setattr(module, "draw_detection", lambda frame, value: frame)
    monkeypatch.setattr(module, "draw_track", lambda frame, xs, ys: frame)
    silence_opencv(monkeypatch, module, key)
    return camera


def test_tracker_saves_stable_csv(monkeypatch, tmp_path):
    module = load_script("track_bead_save", "scripts/02_track_moving_bead.py")
    detection = {"x": 1.0, "y": 2.0, "radius": 3.0, "area": 4.0}
    camera = configure_tracker(monkeypatch, module, detection, ord("q"))
    output = tmp_path / "track.csv"

    exit_code = module.main(["--save", "--output", str(output)])

    assert exit_code == 0
    assert output.read_text(encoding="utf-8").splitlines()[0] == "t,x,y,radius,area"
    assert camera.released is True


def test_tracker_fails_cleanly_when_save_has_no_detections(monkeypatch, tmp_path):
    module = load_script("track_bead_empty", "scripts/02_track_moving_bead.py")
    camera = configure_tracker(monkeypatch, module, None, ord("q"))
    output = tmp_path / "empty.csv"

    exit_code = module.main(["--save", "--output", str(output)])

    assert exit_code == 1
    assert not output.exists()
    assert camera.released is True


def test_plot_command_rejects_invalid_csv(tmp_path):
    module = load_script("plot_invalid", "scripts/03_plot_tracking_csv.py")
    source = tmp_path / "invalid.csv"
    source.write_text("t,x\n0,1\n", encoding="utf-8")

    assert module.main(["--input", str(source)]) == 1


def test_diagnostic_tracker_learning_modes_and_dashboard():
    module = load_script("tune_bead_tracking", "scripts/04_tune_bead_tracking.py")

    assert module.resolve_learning_rate(0, frozen=False) == (None, "AUTO")
    assert module.resolve_learning_rate(10, frozen=False) == (0.001, "MANUAL 0.0010")
    assert module.resolve_learning_rate(10, frozen=True) == (
        0.0,
        "FROZEN (learning rate 0)",
    )

    live = np.zeros((20, 30, 3), dtype=np.uint8)
    mask = np.zeros((20, 30), dtype=np.uint8)
    dashboard = module.compose_dashboard(live, None, mask, mask, panel_width=60)

    assert dashboard.shape == (80, 120, 3)


def test_serial_console_sends_command_and_closes(monkeypatch):
    module = load_script("serial_console", "scripts/05_serial_with_ino.py")

    class FakeSerial:
        is_open = True
        in_waiting = 0

        def __init__(self):
            self.writes = []
            self.closed = False

        def write(self, payload):
            self.writes.append(payload)

        def flush(self):
            pass

        def close(self):
            self.is_open = False
            self.closed = True

    serial_port = FakeSerial()
    commands = iter(["5", "exit"])
    monkeypatch.setattr(module, "open_serial", lambda *args: serial_port)
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))

    exit_code = module.main(["--port", "COM3"])

    assert exit_code == 0
    assert serial_port.writes == [b"5\n"]
    assert serial_port.closed is True


def test_serial_console_reports_open_failure(monkeypatch):
    module = load_script("serial_console_error", "scripts/05_serial_with_ino.py")

    def fail(*args):
        raise serial.SerialException("not available")

    monkeypatch.setattr(module, "open_serial", fail)

    assert module.main(["--port", "COM3"]) == 1
