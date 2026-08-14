# Multiple-bead tracking: lecture workflow

Run commands from `~/Documents/bead_python` with the project virtualenv.

## 07 — Acquire multiple moving beads

Script 07 now uses the same MOG2 pipeline as `02_track_moving_bead.py`, extended
to accept every valid moving contour and assign bead IDs.

The tested defaults are sufficient for the current Orin camera and the bead
rotating near 15 motor steps/s:

```bash
venv/bin/python scripts/07_track_multiple_beads.py
```

The important defaults are:

- MOG2 history: `500`;
- MOG2 variance threshold: `100`;
- binary threshold: `200` (rejects MOG2 shadow pixels near 127);
- dilation: `1`;
- area: `20–2000 px²`;
- radius: `2–30 px`;
- minimum circularity: `0.10`;
- association distance: `70 px`;
- circular work area: center `(320,240)`, radius `190 px`.

Controls:

- `q`: save the CSV and quit;
- `ESC`: discard the run.

The debug windows show the raw MOG2 foreground, thresholded mask, and final
mask. The tracking window shows accepted detections, IDs, recent trajectories,
and the circular work area.

To override the work area:

```bash
venv/bin/python scripts/07_track_multiple_beads.py --roi-circle 320,240,190
```

Use `--no-roi` only when objects outside the vessel must also be detected.

The output is written under `data/multiple_beads/` with one row per detection:

```text
bead_id,t,x,y,radius,area
```

### Known limitation

MOG2 detects motion rather than physical beads. A bead that stops can be
absorbed into the learned background. Reflections and the leading/trailing
edges of one moving bead can also create intermittent contours, so an ID may
restart during a full orbit. The current defaults detect the rotating bead in
roughly 92–96% of measured frames, but do not yet guarantee one ID for the
entire revolution.

## 08 — Plot one acquisition

```bash
venv/bin/python scripts/08_plot_multiple_beads.py \
  --input data/multiple_beads/track_<timestamp>.csv
```

This opens one dashboard with x-y trajectories, x(t), and y(t), using one color
per recorded bead ID.

Save without opening a window:

```bash
MPLBACKEND=Agg venv/bin/python scripts/08_plot_multiple_beads.py \
  --input data/multiple_beads/track_<timestamp>.csv \
  --save data/multiple_beads/dashboard.png \
  --no-show
```
