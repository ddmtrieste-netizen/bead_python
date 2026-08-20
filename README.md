# beadtrack

Python tools for bead detection, tracking, and trajectory analysis in magnetic
actuation experiments based on a stepper motor stator.

## Current goal

Track a bead moving above a stepper motor stator and reconstruct its trajectory
under different actuation, confinement, fluid, and inclination conditions.

## Installation

beadtrack requires Python 3.11 or newer and uses
[uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
```

## Repository structure

- `src/beadtrack/`: reusable tracking code
- `scripts/`: runnable acquisition and analysis scripts
- `pipelines/`: automated acquisition and analysis workflows
- `firmware/`: Arduino firmware and magnetic-sensor utilities

## Single-bead workflow

Check that the camera is available:

```bash
uv run python scripts/00_check_camera.py
```

Optionally tune the detector, then record a trajectory:

```bash
uv run python scripts/04_tune_bead_tracking.py
uv run python scripts/02_track_moving_bead.py --output data/processed/track.csv
```

Press `q` to save and quit, or `Esc` to quit without saving. Plot the recorded
trajectory with:

```bash
uv run python scripts/03_plot_tracking_csv.py --input data/processed/track.csv
```

Run `uv run python scripts/02_track_moving_bead.py --help` to inspect all
tracking options.

## Tracking CSV

Single-bead recordings contain the columns `t`, `x`, `y`, `radius`, and `area`.
Time is expressed in seconds from the first saved detection; positions and
radius are measured in pixels, and area in square pixels.

## License

beadtrack is distributed under the [MIT License](LICENSE).

## Hardware setup

- Camera: Dell Pro Webcam WB5023
- Actuation: stepper motor stator
- Tracking: background subtraction or Hough circle detection
- Test conditions: free, constrained, or concentric Petri dish; air, water, or
  water-glycerol mixtures
- Optional magnetic sensing: Arduino, MCP2221, and MLX90393 tools are available
  under `firmware/` and `pipelines/Mapping_Hall_RPM_pipeline/`
