"""File and CSV input/output helpers for tracking data."""

import csv
import time
from pathlib import Path

from .models import TrackingData

__all__ = [
    "ensure_parent_directory",
    "load_tracking_csv",
    "save_tracking_csv",
    "timestamp_for_filename",
]


def ensure_parent_directory(filename: str | Path) -> Path:
    """Create the parent directory of ``filename`` and return its path."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_tracking_csv(
    filename: str | Path,
    data: TrackingData,
) -> Path:
    """Save tracking samples to CSV with time relative to the first sample."""
    if len(data) == 0:
        raise ValueError("Cannot save tracking data without timestamps")

    path = ensure_parent_directory(filename)
    initial_timestamp = data.time[0]

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["t", "x", "y", "radius", "area"])

        for timestamp, x, y, radius, area in zip(
            data.time,
            data.x,
            data.y,
            data.radius,
            data.area,
            strict=True,
        ):
            writer.writerow(
                [
                    float(timestamp - initial_timestamp),
                    float(x),
                    float(y),
                    float(radius),
                    float(area),
                ]
            )

    return path


def load_tracking_csv(
    filename: str | Path,
) -> TrackingData:
    """Load tracking columns ``t``, ``x``, ``y``, ``radius`` and ``area``."""
    columns: dict[str, list[float]] = {
        name: [] for name in ("t", "x", "y", "radius", "area")
    }

    with Path(filename).open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            for name, values in columns.items():
                values.append(float(row[name]))

    return TrackingData.from_sequences(
        time=columns["t"],
        x=columns["x"],
        y=columns["y"],
        radius=columns["radius"],
        area=columns["area"],
    )


def timestamp_for_filename() -> str:
    """Return the current local time in a compact filename-safe format."""
    return time.strftime("%Y%m%d_%H%M%S")
