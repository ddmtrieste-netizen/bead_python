# Phase alignment calibration - 2026-08

These files preserve the exploratory calculations used to determine the
correction factor applied to angular velocity. The goal was to reconstruct the
field phase from PC timestamps while maintaining phase coherence across
separate experimental runs.

The sequence records the evolution of the reasoning:

- `calculator.py`: initial comparison between step counts and measured phase;
- `calculator2.py`: narrow sweep of the steps-per-revolution value;
- `calculator3.py`: evaluation of a fixed calibrated value;
- `calculator4.py`: transition to timestamp-based phase reconstruction;
- `calculator45.py`: application to a later set of acquisitions;
- `calculator46.py`: sweep of the multiplicative angular-velocity correction.

These are research scratchpads, not stable commands or library modules. Their
measurements and parameters are intentionally embedded in the source so the
calculation history remains visible. Any result promoted into `beadtrack`
should first receive documented inputs, explicit units, and tests.
