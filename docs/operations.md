# Operations guide

Run every command from the repository root after `uv sync --locked`.

## Terminal contract

- `[INFO]`: progress or an operational instruction.
- `[OK]`: a resource was opened, closed, or saved correctly.
- `[RESULT]`: the final, stable summary of a successful operation.
- `[WARN]`: a recoverable condition or deliberate interruption.
- `[ERROR]`: the command could not produce a valid result.

Exit code `0` indicates success or a deliberate interactive exit. Exit code `1`
indicates a hardware, runtime, or data failure. Invalid CLI arguments return
exit code `2`.

## 00 — Check the camera

Purpose: open one camera, read one frame, report its effective properties, and
close it immediately.

```text
uv run python scripts/00_check_camera.py --camera 0
```

Optional parameters: `--width`, `--height`, and `--fps`.

Expected final output:

```text
[RESULT] camera=0 opened=true frame_shape=(...) reported_width=...
```

The same result line also contains `reported_height` and `reported_fps`.

An `[ERROR]` and exit code `1` mean that OpenCV could not open or read the
camera. Close other programs using the camera and retry.

## 01 — Preview the camera

Purpose: show the camera feed without tracking or saving data.

```text
uv run python scripts/01_view_camera.py --camera 0
```

Press `q` or `ESC` to close the preview. Both are successful exits. Camera
resources and OpenCV windows are closed even after an interruption.

## 02 — Track the moving bead

Purpose: detect the largest moving object with background subtraction, display
its trajectory, and optionally save the detections.

Preview without writing data:

```text
uv run python scripts/02_track_moving_bead.py
```

Track and save to an automatically timestamped file:

```text
uv run python scripts/02_track_moving_bead.py --save
```

Track and select the output path:

```text
uv run python scripts/02_track_moving_bead.py --save --output data/processed/example.csv
```

Controls:

- `q`: finish; save only when `--save` is present.
- `ESC`: discard the current run and exit.
- `Ctrl+C`: interrupt and discard the current run.

The CSV schema is:

| Column | Meaning | Unit |
| --- | --- | --- |
| `t` | Time since the first saved detection | s |
| `x` | Horizontal bead center | px |
| `y` | Vertical bead center | px |
| `radius` | Enclosing-circle radius | px |
| `area` | Detected contour area | px² |

When saving is requested, zero detections are treated as an error rather than
creating an empty file.

## 03 — Plot a tracking CSV

Purpose: validate a tracking CSV and display trajectory and position plots.

```text
uv run python scripts/03_plot_tracking_csv.py --input data/processed/example.csv
```

Optionally save the trajectory figure:

```text
uv run python scripts/03_plot_tracking_csv.py --input <CSV> --save <PNG>
```

The command rejects missing columns, empty files, and non-numeric values with
exit code `1`.

## 05 — Arduino serial console

Purpose: send newline-terminated commands to Arduino and display its replies.
The serial port is mandatory because no portable default exists.

PowerShell:

```powershell
uv run python scripts/05_serial_with_ino.py --port COM3 --baud 9600
```

Linux or Jetson:

```bash
uv run python scripts/05_serial_with_ino.py --port /dev/ttyACM0 --baud 9600
```

Enter `exit` to close the console. `Ctrl+C` is also a clean exit. The port is
closed on every exit path.

## RPM mapping pipeline

Purpose: command successive motor speeds, record the bead trajectory at each
speed, and derive bead RPM with FFT analysis.

Compile the Arduino Uno firmware:

```text
arduino-cli compile --fqbn arduino:avr:uno firmware/ino_scripts/bead_stepper_motor
```

Acquire on Windows:

```powershell
uv run python pipelines/Mapping_RPM_pipeline/mapping_RPM.py --serial-port COM3
```

Acquire on Linux or Jetson:

```bash
uv run python pipelines/Mapping_RPM_pipeline/mapping_RPM.py --serial-port /dev/ttyACM0
```

Analyze one speed without opening plots:

```text
uv run python pipelines/Mapping_RPM_pipeline/graphs_RPM.py --mode produce --speed 5 --no-show
```

Produce the complete RPM curve:

```text
uv run python pipelines/Mapping_RPM_pipeline/automatic_produce.py --no-show
```

Press `q` during acquisition to save the current condition and continue. Press
`ESC` to abort the sweep. The pipeline sends `0` RPM before closing the serial
port on all normal and error paths.

See the [pipeline guide](../pipelines/Mapping_RPM_pipeline/README.md) for data
contracts and analysis parameters.
