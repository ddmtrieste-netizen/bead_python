import unittest
from unittest.mock import patch

import numpy as np

from beadtrack.camera import CapturedFrame
from beadtrack.models import Detection
from beadtrack.tracking import SegmentTracker, TrackingParameters


class TrackingParametersTests(unittest.TestCase):
    def test_rejects_invalid_morphology_kernel(self):
        with self.assertRaises(ValueError):
            TrackingParameters(kernel=4)


class SegmentTrackerTests(unittest.TestCase):
    @patch("beadtrack.tracking.draw_sample_track")
    @patch("beadtrack.tracking.draw_detection")
    @patch("beadtrack.tracking.detect_largest_contour_circle")
    @patch("beadtrack.tracking.compute_foreground_masks")
    @patch("beadtrack.tracking.create_background_subtractor")
    def test_tracks_elapsed_time_and_resets_per_instance(
        self,
        create_background,
        compute_masks,
        detect,
        _draw_detection,
        _draw_track,
    ):
        create_background.return_value = object()
        mask = np.zeros((4, 6), dtype=np.uint8)
        compute_masks.return_value = (mask, mask, mask)
        detect.side_effect = [Detection(1, 2, 3, 4), None]
        frame = np.zeros((4, 6, 3), dtype=np.uint8)

        tracker = SegmentTracker(TrackingParameters())
        first = tracker.process(CapturedFrame(time=10.0, image=frame))
        second = tracker.process(CapturedFrame(time=11.5, image=frame))

        self.assertEqual(first.elapsed, 0.0)
        self.assertEqual(second.elapsed, 1.5)
        self.assertEqual(second.sample_count, 1)
        self.assertEqual(len(tracker.data()), 1)

        another_tracker = SegmentTracker(TrackingParameters())
        self.assertEqual(another_tracker.sample_count, 0)


if __name__ == "__main__":
    unittest.main()
