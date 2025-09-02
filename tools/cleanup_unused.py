#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGETS = [
    ROOT/"legacy(USELESS_CODE)",
    ROOT/"core_",
]

def main():
    ap = argparse.ArgumentParser(description="Clean up unused directories (dry-run by default)")
    ap.add_argument("--dry-run", action="store_true", help="Only print what would be removed")
    ap.add_argument("--targets", nargs="*", type=Path, default=DEFAULT_TARGETS, help="Paths to remove")
    args = ap.parse_args()

    for t in args.targets:
        if not t.exists():
            continue
        if args.dry_run:
            print(f"Would remove: {t}")
        else:
            print(f"Removing: {t}")
            shutil.rmtree(t, ignore_errors=True)

    print("Done.")

if __name__ == "__main__":
    main()
