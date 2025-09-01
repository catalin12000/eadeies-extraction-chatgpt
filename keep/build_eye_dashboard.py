#!/usr/bin/env python3
from __future__ import annotations

"""Wrapper entry-point under keep/: builds the eye dashboard using the core script.

This keeps a curated "important files" view without breaking original paths.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_eye_dashboard import main  # type: ignore

if __name__ == "__main__":
    main()
