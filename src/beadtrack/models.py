"""Shared domain models for bead tracking."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

import numpy as np
from numpy.typing import NDArray

__all__ = ["Detection", "TrackingData"]


@dataclass(slots=True, eq=False)
class TrackingData:
    """Aligned one-dimensional arrays produced by a tracking run."""

    time: NDArray[np.float64]
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    radius: NDArray[np.float64]
    area: NDArray[np.float64]

    @classmethod
    def from_sequences(
        cls,
        *,
        time: Sequence[float],
        x: Sequence[float],
        y: Sequence[float],
        radius: Sequence[float],
        area: Sequence[float],
    ) -> Self:
        """Build tracking data from Python sequences."""
        return cls(
            time=np.asarray(time, dtype=np.float64),
            x=np.asarray(x, dtype=np.float64),
            y=np.asarray(y, dtype=np.float64),
            radius=np.asarray(radius, dtype=np.float64),
            area=np.asarray(area, dtype=np.float64),
        )

    def __post_init__(self) -> None:
        for field_name in ("time", "x", "y", "radius", "area"):
            values = np.asarray(getattr(self, field_name), dtype=np.float64)
            if values.ndim != 1:
                raise ValueError(f"{field_name} must be one-dimensional")
            setattr(self, field_name, values)

        sample_count = len(self.time)
        if any(
            len(getattr(self, field_name)) != sample_count
            for field_name in ("x", "y", "radius", "area")
        ):
            raise ValueError("All tracking arrays must have equal length")

    def __len__(self) -> int:
        return len(self.time)


@dataclass(slots=True)
class Detection:
    """Position and geometry of one detected bead."""

    x: float
    y: float
    radius: float
    area: float
