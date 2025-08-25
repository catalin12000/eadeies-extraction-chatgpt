#!/usr/bin/env python3
"""End-to-end runner: raw text -> structured JSON -> benchmark -> eye dashboard.

Usage:
  python tools/run_all.py \
    --pdf-root data \
    --gt data/01_benchmark/eadeies_final.csv \
    --engines pdfplumber docling \
    --out-dir debug
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, text=True)
    if r.returncode != 0:
        sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser(description="Run full pipeline and render dashboard")
    ap.add_argument("--pdf-root", type=Path, default=Path("data"))
    ap.add_argument("--gt", type=Path, default=Path("data/01_benchmark/eadeies_final.csv"))
    ap.add_argument("--out-dir", type=Path, default=Path("debug"))
    ap.add_argument("--engines", nargs="*", default=["pdfplumber", "docling"], help="pdfplumber docling")
    args = ap.parse_args()

    out_compare = args.out_dir / "compare"
    out_struct = args.out_dir / "structured_json"
    out_compare.mkdir(parents=True, exist_ok=True)
    out_struct.mkdir(parents=True, exist_ok=True)

    # 1) Raw text
    run([sys.executable, "compare_pdf_extractors.py", "--root", str(args.pdf_root), "--output-dir", str(out_compare), "--save-text", "--sample-lines", "0"]) 

    # 2) Structured JSON (subset of engines if requested)
    step = [sys.executable, "build_structured_json.py", "--all", "--compare-dir", str(out_compare), "--out-dir", str(out_struct)]
    if args.engines:
        step += ["--extractors", *args.engines]
    run(step)

    # 3) Benchmark
    run([sys.executable, "benchmark_evaluation.py", "--benchmark-csv", str(args.gt), "--structured-dir", str(out_struct), "--out", str(args.out_dir / "benchmark_report.json")])

    # 4) Eye dashboard
    run([sys.executable, "build_eye_dashboard.py", "--benchmark-csv", str(args.gt), "--structured-dir", str(out_struct), "--out", str(args.out_dir / "eye_dashboard.html"), "--extractors", *args.engines])


if __name__ == "__main__":
    main()
