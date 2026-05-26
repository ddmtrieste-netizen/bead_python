# bead_python

Python tools for bead detection, tracking, and trajectory analysis in magnetic actuation experiments based on a stepper motor stator.

## Current goal

Track the position of a bead moving above a stepper motor stator and reconstruct its trajectory under different actuation, confinement, fluid, and inclination conditions.

## Setup

- Camera: DELL Pro Webcam WB5023
- Tracking method: background subtraction / Hough circle detection
- Actuation: stepper motor stator
- Object: magnetic or non-magnetic bead
- Working plane: free Petri, contrained, concentric
- Surrounding fluid: ari, water

## Repository structure

- `src/beadtrack/`: reusable tracking code
- `scripts/`: runnable scripts
- `experiments/`: experimental data and metadata
- `notes/`: project notes
- `archive/`: old exploratory scripts

## Basic usage

```bash
python scripts/track_live.py
python scripts/record_video.py
python scripts/plot_trajectory.py
