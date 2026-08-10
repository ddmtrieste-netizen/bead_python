# Bead tracking and magnetic actuation

Reliable command-line tools for camera checks, bead tracking, trajectory
analysis, Arduino communication, and motor-to-bead RPM mapping.

Version `1.1.0` adds an interactive diagnostic dashboard for the existing
single-bead tracking pipeline while preserving the acquisition and FFT
algorithms.

## Supported workflow

1. Check and preview the camera.
2. Track the moving bead and save a stable CSV dataset.
3. Inspect the trajectory and position plots.
4. Communicate with the Arduino motor controller.
5. Acquire an RPM sweep and estimate bead RPM from the recorded trajectories.

The operational commands are documented in
[`docs/operations.md`](docs/operations.md). Experimental alternatives are kept
separately in [`experiments/`](experiments/README.md).

## Requirements

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/)
- OpenCV-compatible camera
- Arduino-compatible motor controller for serial and RPM mapping commands
- Arduino CLI only when compiling the firmware

The development computer may use Windows and PowerShell. Classroom acquisition
may use Linux on Jetson; both command variants are documented.

## Installation

From the repository root, keep the environment and cache outside the Git
repository.

PowerShell:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "..\.venv"
$env:UV_CACHE_DIR = "..\.uv-cache"
uv sync --locked
```

Linux:

```bash
export UV_PROJECT_ENVIRONMENT="../.venv"
export UV_CACHE_DIR="../.uv-cache"
uv sync --locked
```

Verify the software-only release gate:

```text
uv run ruff check src scripts pipelines tests
uv run python -m compileall -q src scripts pipelines
uv run pytest
```

## Quick start

Check the default camera:

```text
uv run python scripts/00_check_camera.py
```

Track and save a bead trajectory:

```text
uv run python scripts/02_track_moving_bead.py --save
```

Plot a saved trajectory:

```text
uv run python scripts/03_plot_tracking_csv.py --input <TRACKING_CSV>
```

Tune and validate the exact tracking masks in one interactive dashboard:

```text
uv run python scripts/04_tune_bead_tracking.py
```

Open the Arduino serial console:

```text
uv run python scripts/05_serial_with_ino.py --port <SERIAL_PORT>
```

Use `COM3`-style serial ports on Windows and `/dev/ttyACM0`-style ports on
Linux.

## Repository structure

- `scripts/`: supported, small operational commands.
- `src/beadtrack/`: shared and tested implementation used by the commands.
- `pipelines/`: supported multi-step acquisition and analysis workflows.
- `firmware/`: Arduino and sensor firmware sources.
- `experiments/`: useful but unsupported research prototypes.
- `archive/`: historical and one-off scripts retained for reference.
- `notes/`: internal chronological laboratory notes.
- `tests/`: hardware-independent regression and interface tests.

## Data and compatibility

Tracking CSV files use the stable columns `t,x,y,radius,area`. RPM acquisition
and analysis use `data/processed/mapping_RPM/`. Experimental data and generated
plots are ignored by Git and must be archived separately with their acquisition
metadata.

Supported commands use tagged terminal output:
`[INFO]`, `[OK]`, `[RESULT]`, `[WARN]`, and `[ERROR]`. Exit code `0` means a
successful or deliberate interactive exit, `1` means a runtime or data error,
and `2` means invalid command-line arguments.

Before collecting calibrated RPM data, ensure that `microsteps` in
`firmware/ino_scripts/bead_stepper_motor/bead_stepper_motor.ino` matches the
physical driver configuration.

See [`CHANGELOG.md`](CHANGELOG.md) for release history.
