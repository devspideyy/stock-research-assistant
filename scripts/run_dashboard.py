"""Start the local dashboard from any working directory."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "app/dashboard.py"),
                *sys.argv[1:],
            ],
            cwd=ROOT,
        )
    )
