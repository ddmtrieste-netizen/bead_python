"""Open the RPM exploration plot for each configured motor speed."""

import subprocess
import sys
from pathlib import Path

GRAPH_SCRIPT = Path(__file__).with_name("graphs_RPM.py")


def main() -> int:
    print("Avvio pipeline...\n")
    for speed in range(1, 57):
        print(f"\nSPEED = {speed}")
        subprocess.run(
            [
                sys.executable,
                str(GRAPH_SCRIPT),
                "--mode",
                "explore",
                "--speed",
                str(speed),
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
