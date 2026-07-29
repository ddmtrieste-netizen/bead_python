# Pipeline per mappare gli RPM della bilia agli RPM comandati allo statore

**Date**: 27 Maggio 2026

### Setup
* Bead diameter: 4.5 mm
* Work bench: Petri dish libero (no barriers)
* Fluid: Acqua, sommergere la bilia completamente

### Scripts
Generate and record trajectories [here](mapping_RPM.py) and post processing/plotting [here](graphs_RPM.py) 

### Data

Acquisition and analysis use the same local folder:
`data/processed/mapping_RPM/`.

The numeric prefix in files such as `5_RPM.csv` is the commanded motor speed
in RPM, not steps per second. The firmware's `microsteps` constant must match
the physical driver setting before collecting calibrated data.

## Results
![RPM plot raw](rpm_curve_raw.png)


![RPM plot binned](rpm_curve_bins.png)
