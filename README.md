# bead_python

Python tools for bead detection, tracking, and trajectory analysis in magnetic
actuation experiments based on a stepper-motor stator.

`v1.0.0` is the frozen experimental baseline. The first consolidated
maintenance release is `v1.0.1`.

## Experimental setup

- Camera: DELL Pro Webcam WB5023
- Tracking: background subtraction and Hough circle detection
- Actuation: Arduino-controlled stepper-motor stator
- Magnetic sensing: MLX90393 through MCP2221
- Working planes: free, constrained and concentric Petri dishes
- Surrounding fluids: air and water

## Development environment

The project uses `uv`. To keep the environment and cache outside this Git
repository in PowerShell:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "..\.venv"
$env:UV_CACHE_DIR = "..\.uv-cache"
uv sync
uv run pytest
```

## Main commands

```powershell
uv run python scripts/00_check_camera.py
uv run python scripts/02_track_moving_bead.py --save
uv run python pipelines/Mapping_RPM_pipeline/mapping_RPM.py --serial-port COM3
uv run python pipelines/Mapping_Hall_RPM_pipeline/mapping_hall_RPM.py --arduino-port COM3
```

Compile the stepper firmware for an Arduino Uno with:

```powershell
arduino-cli compile --fqbn arduino:avr:uno firmware/ino_scripts/bead_stepper_motor
```

RPM mapping acquisition and analysis both use
`data/processed/mapping_RPM/`. Experimental data are intentionally ignored by
Git and must be archived separately with their acquisition metadata.

Before acquiring calibrated data, ensure that `microsteps` in
`firmware/ino_scripts/bead_stepper_motor/bead_stepper_motor.ino` matches the
physical driver configuration.

See [CHANGELOG.md](CHANGELOG.md) for release details.
