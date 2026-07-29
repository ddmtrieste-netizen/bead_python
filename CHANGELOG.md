# Changelog

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
