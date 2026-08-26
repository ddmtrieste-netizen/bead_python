import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(filename):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DisplayCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scripts = [
            load_script("01_view_camera.py"),
            load_script("02_track_moving_bead.py"),
            load_script("04_tune_bead_tracking.py"),
        ]

    def test_local_display_is_backwards_compatible_default(self):
        for script in self.scripts:
            with self.subTest(script=script.__name__):
                args = script.build_parser().parse_args([])
                self.assertEqual(args.display, "local")
                self.assertEqual(args.remote_port, 8765)

    def test_remote_display_options_are_available(self):
        for script in self.scripts:
            with self.subTest(script=script.__name__):
                args = script.build_parser().parse_args(
                    ["--display", "remote", "--remote-port", "9001"]
                )
                self.assertEqual(args.display, "remote")
                self.assertEqual(args.remote_port, 9001)


if __name__ == "__main__":
    unittest.main()
