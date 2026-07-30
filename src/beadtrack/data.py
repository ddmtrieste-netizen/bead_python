"""Tracking CSV input and output helpers."""

import csv
import time
from pathlib import Path


TRACKING_FIELDS = ("t", "x", "y", "radius", "area")


def ensure_parent_dir(filename):
    """Create the parent directory of a future output file."""
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    return filename


def save_tracking_csv(filename, ts, xs, ys, radii, areas):
    """Save tracking arrays using the stable v1 CSV schema."""
    filename = ensure_parent_dir(filename)
    rows = list(zip(ts, xs, ys, radii, areas))
    if not rows:
        raise RuntimeError("No tracking data to save")

    t0 = rows[0][0]
    with filename.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(TRACKING_FIELDS)
        for t, x, y, radius, area in rows:
            writer.writerow(
                [
                    float(t - t0),
                    float(x),
                    float(y),
                    float(radius),
                    float(area),
                ]
            )

    return filename


def load_tracking_csv(filename):
    """Load and validate one tracking CSV file."""
    filename = Path(filename)
    if not filename.is_file():
        raise FileNotFoundError(f"Tracking CSV not found: {filename}")

    columns = {name: [] for name in TRACKING_FIELDS}
    with filename.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [name for name in TRACKING_FIELDS if name not in fieldnames]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Tracking CSV is missing columns: {missing_text}")

        for line_number, row in enumerate(reader, start=2):
            try:
                for name in TRACKING_FIELDS:
                    columns[name].append(float(row[name]))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid numeric value in {filename} at line {line_number}"
                ) from exc

    if not columns["t"]:
        raise ValueError(f"Tracking CSV contains no data rows: {filename}")

    return tuple(columns[name] for name in TRACKING_FIELDS)


def timestamp_string():
    """Return a compact timestamp suitable for filenames."""
    return time.strftime("%Y%m%d_%H%M%S")
