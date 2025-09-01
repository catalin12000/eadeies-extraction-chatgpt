#!/usr/bin/env python3
"""
Minimal example: process a single PDF, return/print the structured JSON,
optionally save it. Meant as a tiny, easy-to-read entry point.

Usage:
  # Print JSON (docling engine by default)
  python tools/example.py --pdf data/test/ΕΠΗ446Ψ842-ΩΔΦ.pdf

    # Choose engine (docling only)
    python tools/example.py --pdf data/test/ΕΠΗ446Ψ842-ΩΔΦ.pdf --engine docling

  # Save JSON to disk as well
  python tools/example.py --pdf data/test/ΕΠΗ446Ψ842-ΩΔΦ.pdf --save --out-dir debug/structured_json

Programmatic use:
  from tools.example import process_pdf
  data = process_pdf("data/test/ΕΠΗ446Ψ842-ΩΔΦ.pdf", engine="docling", save=True)
  print(data)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is importable when running this file directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse the tested helper so logic stays centralized (optional)
try:
    from tools.run_all import quick_structured  # type: ignore
except Exception:
    quick_structured = None  # type: ignore


def process_pdf(pdf: str | Path, *, engine: str = "docling", save: bool = False, out_dir: str | Path | None = None) -> Dict[str, Any]:
    """Return the structured JSON for one PDF; optionally save to disk.

    - engine: 'docling' (only supported)
    - save: when True, writes <stem>_<engine>_structured.json
    - out_dir: directory to save into (default: debug/structured_json)
    """
    from build_structured_json import extract_pdf_to_structured  # fallback path

    pdf_path = Path(pdf)

    if quick_structured is not None:
        # Prefer the shared helper if available
        return quick_structured(pdf_path, engine=engine, save=save, out_dir=Path(out_dir) if out_dir else None)

    # Fallback: call the core extractor directly (keeps this file self-sufficient)
    data = extract_pdf_to_structured(pdf_path, engine)
    if save:
        target = Path(out_dir) if out_dir else Path("debug/structured_json")
        target.mkdir(parents=True, exist_ok=True)
        out_path = target / f"{pdf_path.stem}_{engine}_structured.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {out_path}")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description="Process a single PDF and print/save structured JSON")
    ap.add_argument("--pdf", type=Path, required=True, help="Path to a PDF file")
    ap.add_argument("--engine", choices=["docling"], default="docling")
    ap.add_argument("--save", action="store_true", help="Also save to <stem>_<engine>_structured.json")
    ap.add_argument("--out-dir", type=Path, default=Path("debug/structured_json"))
    ap.add_argument("--no-pretty", action="store_true", help="Print compact JSON (no indentation)")
    args = ap.parse_args()

    data = process_pdf(args.pdf, engine=args.engine, save=args.save, out_dir=args.out_dir)
    if args.no_pretty:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
