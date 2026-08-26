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
- [`experiments/`](experiments/): dated exploratory analyses and research
  scratchpads
- `pipelines/`: automated acquisition and analysis workflows
- `firmware/`: Arduino firmware and magnetic-sensor utilities

Code under `experiments/` preserves the reasoning behind provisional analyses;
it is not part of the stable `beadtrack` API.

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

## Remote view over SSH

The live camera scripts can serve their video and controls to a browser without
requiring a graphical display on the acquisition computer. The HTTP server is
bound to `127.0.0.1` only, so reach it through an SSH tunnel rather than exposing
it on the local network.

Open the tunnel from the MASTER computer:

```bash
ssh -L 8765:127.0.0.1:8765 <user>@orin11
```

Then, inside that SSH session, start one of the live scripts on Orin:

```bash
uv run python scripts/01_view_camera.py --display remote
uv run python scripts/02_track_moving_bead.py --display remote
uv run python scripts/04_tune_bead_tracking.py --display remote
```

Open `http://127.0.0.1:8765` in a browser on MASTER. The camera view offers a
remote stop button, tracking offers save/stop and discard/stop, and the tuning
page mirrors the OpenCV sliders and keyboard commands. Use `--remote-port` on
Orin, and the same destination port in the SSH tunnel, when port 8765 is busy.
Closing the browser or tunnel does not stop acquisition; reconnecting shows the
latest frame. The original OpenCV windows remain the default (`--display local`).

The RPM mapping pipeline can also keep one remote view open across its complete
speed sweep:

```bash
uv run python pipelines/Mapping_RPM_pipeline/mapping_RPM.py \
  --speeds 5 10 \
  --duration 10 \
  --display remote
```

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
