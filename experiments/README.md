# Experiments

This directory contains promising tools that are not part of the supported
v1.0.2 workflow.

Experimental commands may change without compatibility guarantees and are not
included in the release test gate. Validate them on the intended hardware
before using their results in a demonstration or scientific analysis.

## Current experiments

- `tracking_hough/`: alternative bead detection based on the Hough transform.
- `hall_mapping/`: motor-command to magnetic-field rotation mapping using the
  MCP2221 and MLX90393.

The supported operational tools are documented in
[`docs/operations.md`](../docs/operations.md).
