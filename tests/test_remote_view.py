import argparse
import contextlib
import io
import json
import time
import unittest
import urllib.error
import urllib.request

import numpy as np

from beadtrack.remote_view import (
    Action,
    RangeControl,
    RemoteEvent,
    RemoteView,
    add_display_arguments,
    compose_grid,
)


class RemoteViewTests(unittest.TestCase):
    def setUp(self):
        self.view = RemoteView(
            "Test view",
            port=0,
            controls=(RangeControl("gain", "Gain", 0, 10, 1, 3),),
            actions=(Action("stop", "Stop", ("q",), danger=True),),
        )
        self.view.start()

    def tearDown(self):
        self.view.close()

    def get(self, path):
        with urllib.request.urlopen(self.view.url + path, timeout=2) as response:
            return response.status, response.headers, response.read()

    def post(self, path, payload):
        request = urllib.request.Request(
            self.view.url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, response.read()

    def test_page_state_and_events(self):
        status, _headers, page = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Test view", page)
        self.assertIn(b"Stop", page)

        status, body = self.post("/api/control", {"name": "gain", "value": 7})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.post("/api/action", {"name": "stop"})
        self.assertEqual(
            self.view.drain_events(),
            [RemoteEvent("gain", 7), RemoteEvent("stop")],
        )

        _status, _headers, state = self.get("/api/state")
        self.assertEqual(json.loads(state)["gain"], 7)

    def test_invalid_control_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/control", {"name": "missing", "value": 1})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()

    def test_stream_emits_latest_jpeg(self):
        self.view.publish_frame(np.zeros((24, 32, 3), dtype=np.uint8))
        request = urllib.request.Request(self.view.url + "/stream.mjpg")
        with urllib.request.urlopen(request, timeout=2) as response:
            deadline = time.monotonic() + 2
            payload = b""
            while b"\xff\xd8" not in payload and time.monotonic() < deadline:
                payload += response.read(256)
            self.assertIn(b"--frame", payload)
            self.assertIn(b"\xff\xd8", payload)

    def test_state_updates_do_not_create_events(self):
        self.view.update_state(fps=29.5)
        self.assertEqual(self.view.drain_events(), [])
        _status, _headers, state = self.get("/api/state")
        self.assertEqual(json.loads(state)["fps"], 29.5)


class RemoteViewHelpersTests(unittest.TestCase):
    def test_display_arguments(self):
        parser = argparse.ArgumentParser()
        add_display_arguments(parser)
        args = parser.parse_args(["--display", "remote", "--remote-port", "9000"])
        self.assertEqual(args.display, "remote")
        self.assertEqual(args.remote_port, 9000)

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["--remote-port", "70000"])

    def test_compose_grid_converts_grayscale_and_pads(self):
        color = np.zeros((20, 30, 3), dtype=np.uint8)
        gray = np.zeros((20, 30), dtype=np.uint8)
        result = compose_grid(
            [("color", color), ("gray", gray), ("last", color)],
            panel_width=60,
            columns=2,
        )
        self.assertEqual(result.shape, (80, 120, 3))


if __name__ == "__main__":
    unittest.main()
