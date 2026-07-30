# Changelog

## 1.0.2 - 2026-07-30

Maintenance release focused on operational clarity and software-only
reliability.

### Changed

- Turn `src/beadtrack` into the shared package for camera, tracking, CSV,
  serial, and terminal utilities.
- Keep supported operational commands small and directly executable.
- Require an explicit serial port on serial and RPM mapping commands for
  Windows/Linux parity.
- Standardize terminal tags and exit codes across supported commands.
- Expand the README and add an English operations guide for PowerShell and
  Linux/Jetson.
- Document the complete motor-to-bead RPM acquisition and analysis workflow.

### Reliability

- Treat an RPM condition without bead detections as a controlled failure.
- Validate tracking CSV schemas and numeric values before plotting.
- Release camera, OpenCV windows, serial ports, and the motor on all exit paths.
- Add hardware-independent tests for supported commands and data contracts.
- Add GitHub Actions checks on Windows and Linux with Python 3.10 and 3.14.

### Organization

- Move Hough tracking and Hall-field mapping to `experiments/`.
- Move one-off plotting and fixed-range exploration scripts to `archive/`.
- Remove duplicated `_common.py` modules and the empty class-demo placeholder.

## 1.0.1 - 2026-07-29

Maintenance release based on the frozen `v1.0.0` baseline.

### Fixed

- Preserve the sign of Hall-field rotation in the complex FFT estimator.
- Avoid a tracking crash when no bead is detected in the first frame.
- Make `q` save the current condition and ESC abort the complete RPM sweep.
- Warm up background subtraction before collecting trajectory points.
- Send an explicit zero-RPM command on normal completion and error paths.
- Generate low-speed step pulses without long blocking `delayMicroseconds()`
  calls.
- Use RPM consistently across firmware commands, CSV summaries and plots.
- Use `data/processed/mapping_RPM/` consistently for acquisition and analysis.
- Make `--save` a proper command-line flag.
- Use the active Python interpreter in automated exploration.

### Validation

- Four hardware-independent regression tests.
- Python byte-code compilation and Ruff static checks.
- Stepper firmware compiled for Arduino Uno with Arduino AVR core 1.8.8.

### Hardware note

The firmware defaults to full-step operation (`microsteps = 1`). This constant
must be changed only when the physical driver microstepping pins or DIP switches
are configured accordingly.
