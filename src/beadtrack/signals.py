"""Signal smoothing helpers."""

import numpy as np
import scipy.ndimage
import scipy.signal
from numpy.typing import ArrayLike, NDArray

__all__ = ["median_smooth", "savitzky_golay_smooth"]


def savitzky_golay_smooth(
    values: ArrayLike,
    window_length: int = 301,
    polynomial_order: int = 3,
) -> NDArray[np.float64]:
    """Smooth one-dimensional values with a Savitzky-Golay filter."""
    if window_length <= 0 or window_length % 2 == 0:
        raise ValueError("window_length must be a positive odd integer")
    if polynomial_order < 0 or polynomial_order >= window_length:
        raise ValueError("polynomial_order must satisfy 0 <= order < window_length")

    return np.asarray(
        scipy.signal.savgol_filter(
            values,
            window_length=window_length,
            polyorder=polynomial_order,
        ),
        dtype=np.float64,
    )


def median_smooth(
    values: ArrayLike,
    window_size: int = 101,
) -> NDArray[np.float64]:
    """Smooth one-dimensional values with a wrapping median filter."""
    if window_size <= 0:
        raise ValueError("window_size must be positive")

    return np.asarray(
        scipy.ndimage.median_filter(values, size=window_size, mode="wrap"),
        dtype=np.float64,
    )
