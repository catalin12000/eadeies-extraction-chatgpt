#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRS = [
    ROOT/"data"/"2025"/"01",
    ROOT/"data"/"2025"/"02",
    ROOT/"data"/"2025"/"03",
    ROOT/"debug"/"runs",
    ROOT/"debug"/"qa",
]

def main():
    # Create directories
    for d in DIRS:
        d.mkdir(parents=True, exist_ok=True)
    print("Created base directories.")

    # Show Python version
    print("Python:", sys.version)

    # Install requirements (optional prompt)
    req = ROOT/"requirements.txt"
    if req.exists():
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])
            print("Dependencies installed.")
        except subprocess.CalledProcessError:
            print("Warning: failed to install dependencies. Run manually: pip install -r requirements.txt")

    print("Initialization complete.")

if __name__ == "__main__":
    main()
