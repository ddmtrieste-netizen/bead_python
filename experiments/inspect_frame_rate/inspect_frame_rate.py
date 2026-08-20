"""Scratchpad for inspecting frame intervals in one tracking CSV."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from beadtrack.io import load_tracking_csv

INPUT_CSV = Path("data/processed/track.csv")  # Edit before running.


def main() -> None:
    data = load_tracking_csv(INPUT_CSV)
    if len(data) < 2:
        raise ValueError("At least two tracking samples are required")

    intervals = np.diff(data.time)
    if np.any(intervals <= 0):
        raise ValueError("Timestamps must be strictly increasing")

    instantaneous_fps = 1.0 / intervals
    print(f"File:          {INPUT_CSV}")
    print(f"Samples:       {len(data)}")
    print(f"Duration:      {data.time[-1] - data.time[0]:.6f} s")
    print(f"Mean interval: {np.mean(intervals):.9f} s")
    print(f"Median FPS:    {np.median(instantaneous_fps):.6f}")
    print(f"Interval STD:  {np.std(intervals):.9f} s")

    figure, (interval_axis, fps_axis) = plt.subplots(1, 2, figsize=(14, 6))
    interval_axis.hist(intervals, bins="auto")
    interval_axis.set(xlabel="frame interval [s]", ylabel="count")
    interval_axis.grid(True)

    fps_axis.plot(data.time[1:], instantaneous_fps)
    fps_axis.set(xlabel="time [s]", ylabel="instantaneous FPS")
    fps_axis.grid(True)

    figure.suptitle(INPUT_CSV.name)
    figure.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
