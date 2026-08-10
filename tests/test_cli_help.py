import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    "scripts/00_check_camera.py",
    "scripts/01_view_camera.py",
    "scripts/02_track_moving_bead.py",
    "scripts/03_plot_tracking_csv.py",
    "scripts/04_tune_bead_tracking.py",
    "scripts/05_serial_with_ino.py",
    "pipelines/Mapping_RPM_pipeline/mapping_RPM.py",
    "pipelines/Mapping_RPM_pipeline/graphs_RPM.py",
    "pipelines/Mapping_RPM_pipeline/automatic_produce.py",
]


@pytest.mark.parametrize("relative_path", COMMANDS)
def test_supported_command_help(relative_path, tmp_path):
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment["MPLCONFIGDIR"] = str(tmp_path / "matplotlib")

    completed = subprocess.run(
        [sys.executable, str(ROOT / relative_path), "--help"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout
