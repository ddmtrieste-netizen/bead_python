"""Reusable state for one segment of MOG2 bead tracking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .camera import CapturedFrame
from .detection import (
    compute_foreground_masks,
    create_background_subtractor,
    detect_largest_contour_circle,
)
from .drawing import draw_detection, draw_sample_track
from .models import Detection, TrackingData, TrackingSample

__all__ = [
    "ProcessedTrackingFrame",
    "SegmentTracker",
    "TrackingParameters",
]


@dataclass(frozen=True, slots=True)
class TrackingParameters:
    """Detection parameters that stay fixed during one recording segment."""

    history: int = 500
    var_threshold: float = 100
    threshold: int = 120
    kernel: int = 3
    dilate: int = 2
    min_area: float = 50
    max_area: float | None = None

    def __post_init__(self) -> None:
        if self.history <= 0:
            raise ValueError("history must be positive")
        if self.var_threshold <= 0:
            raise ValueError("var_threshold must be positive")
        if not 0 <= self.threshold <= 255:
            raise ValueError("threshold must be between 0 and 255")
        if self.kernel <= 0 or self.kernel % 2 == 0:
            raise ValueError("kernel must be a positive odd number")
        if self.dilate < 0:
            raise ValueError("dilate cannot be negative")
        if self.min_area < 0:
            raise ValueError("min_area cannot be negative")
        if self.max_area is not None and self.max_area <= self.min_area:
            raise ValueError("max_area must be greater than min_area")


@dataclass(slots=True)
class ProcessedTrackingFrame:
    """Images and detection state produced from one captured frame."""

    time: float
    elapsed: float
    display: NDArray[np.uint8]
    foreground: NDArray[np.uint8]
    threshold: NDArray[np.uint8]
    clean: NDArray[np.uint8]
    detection: Detection | None
    sample_count: int


class SegmentTracker:
    """Track one speed condition while allowing the camera to remain open."""

    def __init__(self, parameters: TrackingParameters) -> None:
        self.parameters = parameters
        self.samples: list[TrackingSample] = []
        self._started_at: float | None = None
        self._background = create_background_subtractor(
            history=parameters.history,
            var_threshold=parameters.var_threshold,
            detect_shadows=True,
        )

    @property
    def sample_count(self) -> int:
        return len(self.samples)

    def process(self, captured: CapturedFrame) -> ProcessedTrackingFrame:
        """Process one frame and append a sample when a bead is detected."""
        if self._started_at is None:
            self._started_at = captured.time

        foreground, threshold, clean = compute_foreground_masks(
            captured.image,
            self._background,
            threshold_value=self.parameters.threshold,
            kernel_size=self.parameters.kernel,
            dilation_iterations=self.parameters.dilate,
        )
        detection = detect_largest_contour_circle(
            clean,
            min_area=self.parameters.min_area,
            max_area=self.parameters.max_area,
        )
        if detection is not None:
            self.samples.append(TrackingSample(captured.time, detection))

        display = captured.image.copy()
        draw_detection(display, detection)
        draw_sample_track(display, self.samples)
        return ProcessedTrackingFrame(
            time=captured.time,
            elapsed=captured.time - self._started_at,
            display=display,
            foreground=foreground,
            threshold=threshold,
            clean=clean,
            detection=detection,
            sample_count=len(self.samples),
        )

    def data(self) -> TrackingData:
        """Return all detections collected in this segment."""
        return TrackingData.from_samples(self.samples)
