# Motor-to-bead RPM mapping

This supported pipeline maps commanded stator RPM to measured bead RPM.

## Experimental setup

- Bead diameter used in the original baseline: 4.5 mm
- Work plane: unconstrained Petri dish
- Fluid: water, with the bead completely submerged
- Camera tracking: background subtraction and largest-contour detection
- Motor command unit: RPM

Before calibrated acquisition, verify that `microsteps` in
`firmware/ino_scripts/bead_stepper_motor/bead_stepper_motor.ino` matches the
physical driver.

## Data flow

```text
Arduino RPM command
        ↓
mapping_RPM.py
        ↓
data/processed/mapping_RPM/<rpm>_RPM.csv
        ↓
graphs_RPM.py or automatic_produce.py
        ↓
bead RPM estimate, summary CSV, and plots
```

The numeric prefix in `5_RPM.csv` is the commanded motor speed in RPM.

Each trajectory CSV contains:

```text
t,x,y,radius,area
```

Time is measured in seconds from the first recorded detection. Coordinates,
radius, and area are expressed in camera pixels.

## Acquisition

Windows:

```powershell
uv run python pipelines/Mapping_RPM_pipeline/mapping_RPM.py `
  --serial-port COM3 `
  --rpm-start 1 `
  --rpm-stop 20 `
  --rpm-step 1 `
  --duration 180
```

Linux or Jetson:

```bash
uv run python pipelines/Mapping_RPM_pipeline/mapping_RPM.py \
  --serial-port /dev/ttyACM0 \
  --rpm-start 1 \
  --rpm-stop 20 \
  --rpm-step 1 \
  --duration 180
```

For every speed, the pipeline:

1. sends `<rpm>\n` to Arduino;
2. waits for the configured settling time;
3. warms up the background model;
4. records detections for the configured duration;
5. saves `<rpm>_RPM.csv`.

`q` saves the current speed and continues. `ESC` aborts the sweep. A condition
with no bead detections fails instead of generating an empty CSV. A `0\n` stop
command is sent before closing the port on every exit path.

## Single-file analysis

```text
uv run python pipelines/Mapping_RPM_pipeline/graphs_RPM.py --mode produce --speed 5 --method raw
```

Available signals are `x`, `y`, `r`, and `radius`. Available FFT methods are
`raw` and `bins`. Use `--no-show` for non-interactive execution.

## Batch analysis

```text
uv run python pipelines/Mapping_RPM_pipeline/automatic_produce.py --method bins --signal x
```

Default outputs:

- `data/processed/mapping_RPM/rpm_summary.csv`
- `data/processed/mapping_RPM/rpm_curve_bins.png`

The summary reports commanded motor RPM and FFT-derived bead cycles per minute.
Generated data and plots are intentionally ignored by Git.
