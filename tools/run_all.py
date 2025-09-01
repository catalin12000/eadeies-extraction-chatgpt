#!/usr/bin/env python3
"""End-to-end runner: raw text -> structured JSON -> benchmark -> eye dashboard.

Usage (full pipeline):
    python tools/run_all.py \
        --pdf-root data \
    --gt data/01_benchmark/eadeies_final.csv \
    --engines docling \
        --out-dir debug

Usage (single PDF "tool" mode):
    python tools/run_all.py \
        --single-pdf data/test/FILE.pdf \
        --engines docling \
        --out-dir debug

Notes:
    - When --single-pdf is provided, only that PDF is processed into structured JSON
        using build_structured_json.py and the selected engines. Other steps are skipped.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Optional


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, text=True)
    if r.returncode != 0:
        sys.exit(r.returncode)

def process_single_pdf(pdf: Path, out_struct: Path, engines: list[str] | None = None) -> None:
    """Process a single PDF into structured JSON using selected engines.

    Writes files like: <stem>_<engine>_structured.json under out_struct.
    """
    out_struct.mkdir(parents=True, exist_ok=True)
    step = [sys.executable, "build_structured_json.py", "--pdf", str(pdf), "--out-dir", str(out_struct)]
    if engines:
        step += ["--extractors", *engines]
    run(step)

def quick_structured(pdf: Path | str, *, engine: str = "docling", save: bool = False, out_dir: Path | None = None) -> Dict[str, Any]:
        """Simple function: load one PDF -> return structured JSON dict.

        Example:
                from tools.run_all import quick_structured
                a = quick_structured("data/test/ΕΠΗ446Ψ842-ΩΔΦ.pdf")
                print(a)

        Params:
            - pdf: path to a PDF file
            - engine: 'docling' (default)
            - save: when True, also writes <stem>_<engine>_structured.json
            - out_dir: target folder for saving (default: debug/structured_json)

        Returns:
            - The structured JSON dict.
        """
        from build_structured_json import extract_pdf_to_structured  # lazy import

        pdf_path = Path(pdf)
        data = extract_pdf_to_structured(pdf_path, engine)

        if save:
                target = (out_dir or Path("debug/structured_json"))
                target.mkdir(parents=True, exist_ok=True)
                out_path = target / f"{pdf_path.stem}_{engine}_structured.json"
                import json
                out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Saved {out_path}")

        return data


def main():
    ap = argparse.ArgumentParser(description="Run full pipeline and render dashboard")
    ap.add_argument("--pdf-root", type=Path, default=Path("data"))
    ap.add_argument("--gt", type=Path, default=Path("data/01_benchmark/eadeies_final.csv"))
    ap.add_argument("--out-dir", type=Path, default=Path("debug"))
    ap.add_argument("--engines", nargs="*", default=["docling"], help="docling")
    ap.add_argument("--single-pdf", type=Path, help="Process only this PDF to structured JSON; skip compare/benchmark/dashboard")
    args = ap.parse_args()

    out_compare = args.out_dir / "compare"
    out_struct = args.out_dir / "structured_json"
    out_compare.mkdir(parents=True, exist_ok=True)
    out_struct.mkdir(parents=True, exist_ok=True)

    # Single-PDF tool mode: just structure one file and exit.
    if args.single_pdf:
        process_single_pdf(args.single_pdf, out_struct, args.engines)
        return

    # 1) Raw text (optional)
    # run([sys.executable, "compare_pdf_extractors.py", "--root", str(args.pdf_root), "--output-dir", str(out_compare), "--save-text", "--sample-lines", "0"]) 

    # 2) Structured JSON directly from PDFs (docling-only engines)
    pdfs = sorted([p for p in args.pdf_root.rglob("*.pdf") if p.is_file()])
    if not pdfs:
        print(f"No PDFs found under {args.pdf_root}")
    else:
        for pdf in pdfs:
            process_single_pdf(pdf, out_struct, args.engines)

    # 3) Benchmark
    run([sys.executable, "benchmark_evaluation.py", "--benchmark-csv", str(args.gt), "--structured-dir", str(out_struct), "--out", str(args.out_dir / "benchmark_report.json")])

    # 4) Eye dashboard
    run([sys.executable, "build_eye_dashboard.py", "--benchmark-csv", str(args.gt), "--structured-dir", str(out_struct), "--out", str(args.out_dir / "eye_dashboard.html"), "--extractors", *args.engines])


if __name__ == "__main__":
    main()
