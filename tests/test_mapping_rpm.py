import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from beadtrack.models import TrackingData
from pipelines.Mapping_RPM_pipeline.automatic_produce import infer_speed_from_filename
from pipelines.Mapping_RPM_pipeline.graphs_RPM import get_file_from_speed


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "pipelines" / "Mapping_RPM_pipeline" / "mapping_RPM.py"
SPEC = importlib.util.spec_from_file_location("mapping_RPM", SCRIPT)
mapping = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mapping)


def sample_data():
    return TrackingData.from_sequences(
        time=[1.0, 2.0],
        x=[10.0, 11.0],
        y=[20.0, 21.0],
        radius=[3.0, 3.0],
        area=[30.0, 31.0],
    )


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.writes = []

    def write(self, payload):
        self.writes.append(payload)

    def flush(self):
        pass

    def close(self):
        self.is_open = False


class MappingHelpersTests(unittest.TestCase):
    def test_default_speed_sweep_and_filenames(self):
        args = mapping.build_parser().parse_args([])
        speeds = mapping.parse_speeds(args)
        self.assertEqual(len(speeds), 158)
        self.assertEqual(speeds[0], 1.0)
        self.assertEqual(speeds[-1], 79.5)
        self.assertEqual(
            mapping.output_path_for_speed(Path("out"), 1.5),
            Path("out/1.5_RPM.csv"),
        )

    def test_rejects_inconsistent_sweep_direction(self):
        args = mapping.build_parser().parse_args(
            ["--speed-start", "3", "--speed-stop", "1", "--speed-step", "1"]
        )
        with self.assertRaises(ValueError):
            mapping.parse_speeds(args)

    def test_analysis_contract_accepts_decimal_speed(self):
        self.assertEqual(infer_speed_from_filename("1.5_RPM.csv"), 1.5)
        self.assertEqual(
            get_file_from_speed(Path("out"), 1.5),
            Path("out/1.5_RPM.csv"),
        )


class MappingLifecycleTests(unittest.TestCase):
    def test_resources_persist_and_motor_is_stopped(self):
        fake_serial = FakeSerial()
        fake_capture = MagicMock()
        fake_thread = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(mapping.serial, "Serial", return_value=fake_serial),
                patch.object(mapping.threading, "Thread", return_value=fake_thread),
                patch.object(mapping, "open_camera", return_value=fake_capture) as open_camera,
                patch.object(mapping, "settle_camera"),
                patch.object(
                    mapping,
                    "record_segment",
                    side_effect=[sample_data(), sample_data()],
                ) as record,
            ):
                result = mapping.main(
                    [
                        "--speeds",
                        "1",
                        "2",
                        "--duration",
                        "1",
                        "--settle",
                        "0",
                        "--arduino-ready-wait",
                        "0",
                        "--min-detections",
                        "1",
                        "--output-dir",
                        directory,
                    ]
                )

            self.assertEqual(result, 0)
            open_camera.assert_called_once_with(camera_index=0)
            self.assertEqual(record.call_count, 2)
            fake_capture.release.assert_called_once()
            self.assertEqual(
                fake_serial.writes,
                [b"SPEED\n", b"1\n", b"2\n", b"STOP\n"],
            )
            self.assertTrue((Path(directory) / "1_RPM.csv").exists())
            self.assertTrue((Path(directory) / "2_RPM.csv").exists())
            self.assertTrue((Path(directory) / "mapping_status.csv").exists())

    def test_empty_run_fails_and_still_stops_motor(self):
        fake_serial = FakeSerial()
        fake_capture = MagicMock()
        empty = TrackingData.from_sequences(
            time=[], x=[], y=[], radius=[], area=[]
        )
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(mapping.serial, "Serial", return_value=fake_serial),
                patch.object(mapping.threading, "Thread", return_value=MagicMock()),
                patch.object(mapping, "open_camera", return_value=fake_capture),
                patch.object(mapping, "settle_camera"),
                patch.object(mapping, "record_segment", return_value=empty),
            ):
                result = mapping.main(
                    [
                        "--speeds",
                        "1",
                        "--duration",
                        "1",
                        "--settle",
                        "0",
                        "--arduino-ready-wait",
                        "0",
                        "--output-dir",
                        directory,
                    ]
                )

            self.assertEqual(result, 1)
            self.assertFalse((Path(directory) / "1_RPM.csv").exists())
            self.assertEqual(fake_serial.writes[-1], b"STOP\n")


if __name__ == "__main__":
    unittest.main()
