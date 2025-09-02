#!/usr/bin/env python3
from __future__ import annotations

"""Parallel, resumable month runner for docling extraction with Excel summary.

Features:
- Recursively discover PDFs in an input directory (month folder)
- Interactive confirmation (Y/N) showing how many files will be processed
- Parallel processing using multiprocessing (workers configurable)
- Resumable: skips PDFs that already have JSON outputs
- Robust: catches exceptions per-file and continues; logs status to manifest.csv
- Outputs per-run folder with structured_json/, manifest.csv, and a timestamped Excel

Usage (example):
  python tools/run_month.py \
    --input-dir data/2025/01 \
    --out-root debug/runs \
    --workers 6 \
    --resume

The Excel file will be named run_<run_name>_<timestamp>.xlsx under the run folder.
Run name defaults to the input folder name (e.g., '01').
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Ensure repository root is importable
THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Imports from project
from build_structured_json import extract_pdf_to_structured, COVERAGE_KEYS  # type: ignore
from benchmark_evaluation import _norm_header  # header canonicalizer compatible with GT
from tqdm import tqdm  # type: ignore

try:
    from openpyxl import Workbook  # noqa: F401
except Exception:  # pragma: no cover
    Workbook = None  # type: ignore


def discover_pdfs(input_dir: Path) -> List[Path]:
    """Recursively find all .pdf/.PDF files under input_dir."""
    files: List[Path] = []
    for ext in ("*.pdf", "*.PDF"):
        files.extend(sorted(input_dir.rglob(ext)))
    # De-duplicate while preserving order
    seen = set()
    uniq: List[Path] = []
    for p in files:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        uniq.append(p)
    return uniq


def ensure_dirs(out_root: Path, run_name: str) -> Tuple[Path, Path]:
    run_dir = out_root / run_name
    struct_dir = run_dir / "structured_json"
    log_dir = run_dir / "logs"
    struct_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    return struct_dir, log_dir


def json_path_for(struct_dir: Path, stem: str) -> Path:
    return struct_dir / f"{stem}_docling_structured.json"


def _extract_one(pdf_path: Path, struct_dir: Path, resume: bool) -> Dict[str, Any]:
    stem = pdf_path.stem
    out_json = json_path_for(struct_dir, stem)
    if resume and out_json.exists():
        # Populate fields from existing JSON to keep manifest informative
        try:
            data = json.loads(out_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        owners = data.get("Στοιχεία κυρίου του έργου", []) or []
        cov = data.get("Στοιχεία Διαγράμματος Κάλυψης", {}) or {}
        floors = (cov.get("ΣΥΝΟΛΟ", {}) or {}).get("Αριθμός Ορόφων")
        parking = (cov.get("ΣΥΝΟΛΟ", {}) or {}).get("Αριθμός Θέσεων Στάθμευσης")
        meta = data.get("_meta", {}) or {}
        return {
            "stem": stem,
            "pdf": str(pdf_path),
            "json": str(out_json),
            "status": "skipped",
            "elapsed_sec": 0.0,
            "err": "",
            "kaek_present": 1 if (data.get("ΚΑΕΚ") or "").strip() else 0,
            "owners_count": int(len(owners)) if owners is not None else None,
            "floors_total": floors if isinstance(floors, (int, float)) else None,
            "parking_total": parking if isinstance(parking, (int, float)) else None,
            "has_tables": 1 if meta.get("has_tables") else 0,
            "tables_count": int(meta.get("tables_count") or 0),
            "owners_present": 1 if meta.get("owners_present") else 0,
            "coverage_present": 1 if meta.get("coverage_present") else 0,
        }
    t0 = time.time()
    try:
        data = extract_pdf_to_structured(pdf_path, extractor="docling")
        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        elapsed = round(time.time() - t0, 3)
        owners = data.get("Στοιχεία κυρίου του έργου", []) or []
        cov = data.get("Στοιχεία Διαγράμματος Κάλυψης", {}) or {}
        floors = (cov.get("ΣΥΝΟΛΟ", {}) or {}).get("Αριθμός Ορόφων")
        parking = (cov.get("ΣΥΝΟΛΟ", {}) or {}).get("Αριθμός Θέσεων Στάθμευσης")
        meta = data.get("_meta", {}) or {}
        no_tables_warn = "no_tables" if not meta.get("has_tables") else ""
        return {
            "stem": stem,
            "pdf": str(pdf_path),
            "json": str(out_json),
            "status": "ok",
            "elapsed_sec": elapsed,
            "err": no_tables_warn,
            "kaek_present": 1 if (data.get("ΚΑΕΚ") or "").strip() else 0,
            "owners_count": int(len(owners)),
            "floors_total": floors if isinstance(floors, (int, float)) else None,
            "parking_total": parking if isinstance(parking, (int, float)) else None,
            "has_tables": 1 if meta.get("has_tables") else 0,
            "tables_count": int(meta.get("tables_count") or 0),
            "owners_present": 1 if meta.get("owners_present") else 0,
            "coverage_present": 1 if meta.get("coverage_present") else 0,
        }
    except Exception as e:  # pragma: no cover
        elapsed = round(time.time() - t0, 3)
        return {
            "stem": stem,
            "pdf": str(pdf_path),
            "json": "",
            "status": "error",
            "elapsed_sec": elapsed,
            "err": f"{type(e).__name__}: {e}",
            "kaek_present": 0,
            "owners_count": 0,
            "floors_total": None,
            "parking_total": None,
        }


def _extract_one_star(args: Tuple[Path, Path, bool]) -> Dict[str, Any]:
    """Helper for Pool.imap_unordered to unpack tuple args."""
    return _extract_one(*args)


def write_manifest(manifest_csv: Path, rows: List[Dict[str, Any]]) -> None:
    headers = [
        "stem",
        "pdf",
        "json",
        "status",
        "elapsed_sec",
        "err",
        "kaek_present",
        "owners_count",
        "floors_total",
        "parking_total",
        "has_tables",
        "tables_count",
        "owners_present",
        "coverage_present",
    ]
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_gt_like_csv(run_dir: Path, structured_dir: Path, run_name: str) -> Path:
    """Write a CSV with the same schema as the benchmark GT file.

    Columns:
      - ΑΔΑ, ΚΑΕΚ
      - Επώνυμο/ία, Όνομα (slash-joined when multiple owners)
      - For each coverage cell: "<GROUP> - <KEY>"
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv = run_dir / f"run_{run_name}_{ts}.csv"
    groups = ["ΥΦΙΣΤΑΜΕΝΑ", "ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ", "ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ", "ΣΥΝΟΛΟ"]
    # Build headers
    headers: List[str] = ["ΑΔΑ", "ΚΑΕΚ", "Επώνυμο/ία", "Όνομα"]
    cov_headers: List[str] = [f"{g} - {k}" for g in groups for k in COVERAGE_KEYS]
    headers.extend(cov_headers)

    json_files = sorted(structured_dir.glob("*_docling_structured.json"))
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            stem = data.get("ΑΔΑ", jf.stem.split("_", 1)[0])
            kaek = data.get("ΚΑΕΚ") or ""
            owners = data.get("Στοιχεία κυρίου του έργου", []) or []
            # Slash-join owners into two columns
            surnames = [str(o.get("Επώνυμο/ία") or "").strip() for o in owners if (o.get("Επώνυμο/ία") or "").strip()]
            names = [str(o.get("Όνομα") or "").strip() for o in owners if (o.get("Όνομα") or "").strip()]
            owners_surname = " / ".join(surnames)
            owners_name = " / ".join(names)
            cov = data.get("Στοιχεία Διαγράμματος Κάλυψης", {}) or {}
            row: Dict[str, Any] = {"ΑΔΑ": stem, "ΚΑΕΚ": kaek, "Επώνυμο/ία": owners_surname, "Όνομα": owners_name}
            for g in groups:
                crow = cov.get(g, {}) or {}
                for k in COVERAGE_KEYS:
                    hdr = f"{g} - {k}"
                    val = crow.get(k)
                    row[hdr] = val if val is not None else ""
            w.writerow(row)
    return out_csv


def main():
    ap = argparse.ArgumentParser(description="Run docling extraction for a month folder (parallel, resumable) and write an Excel summary")
    ap.add_argument("--input-dir", type=Path, required=True, help="Folder containing PDFs (e.g., data/2025/01)")
    ap.add_argument("--out-root", type=Path, default=Path("debug/runs"), help="Root output folder for runs")
    ap.add_argument("--run-name", type=str, default="", help="Name of this run (default: input dir name)")
    ap.add_argument("--workers", type=int, default=max(1, (cpu_count() or 4) - 1))
    ap.add_argument("--resume", action="store_true", help="Skip files that already have JSON outputs")
    ap.add_argument("--yes", action="store_true", help="Proceed without interactive confirmation")
    ap.add_argument("--progress-every", type=int, default=50, help="Print progress every N files")
    args = ap.parse_args()

    input_dir: Path = args.input_dir
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")
    run_name = args.run_name.strip() or input_dir.name
    struct_dir, log_dir = ensure_dirs(args.out_root, run_name)
    run_dir = args.out_root / run_name
    manifest_csv = run_dir / "manifest.csv"

    pdfs = discover_pdfs(input_dir)
    total = len(pdfs)
    print(f"Discovered {total} PDF(s) under {input_dir}")
    if total == 0:
        return

    # Interactive confirmation
    if not args.yes:
        reply = input(f"Process {total} files into {run_dir}? [Y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted by user.")
            return

    # Build job tuples
    jobs: List[Tuple[Path, Path, bool]] = [(p, struct_dir, args.resume) for p in pdfs]
    print(f"Starting with {args.workers} worker(s); resumable={bool(args.resume)}")

    results: List[Dict[str, Any]] = []
    ok = err = skipped = 0
    t_start = time.time()
    with Pool(processes=args.workers) as pool:
        with tqdm(total=total, unit="pdf", dynamic_ncols=True, desc=f"{run_name}") as pbar:
            for i, res in enumerate(pool.imap_unordered(_extract_one_star, jobs), 1):
                results.append(res)
                st = res.get("status")
                if st == "ok":
                    ok += 1
                elif st == "error":
                    err += 1
                elif st == "skipped":
                    skipped += 1
                pbar.update(1)
                if i % max(1, args.progress_every) == 0 or i == total:
                    pbar.set_postfix(ok=ok, skipped=skipped, err=err)

    # Write manifest and GT-like CSV
    write_manifest(manifest_csv, results)
    out_csv = write_gt_like_csv(run_dir, struct_dir, run_name)

    t_elapsed = round(time.time() - t_start, 2)
    # Summary diagnostics
    try:
        total_rows = len(results)
        tables_yes = sum(int(r.get("has_tables") or 0) for r in results)
        owners_yes = sum(int(r.get("owners_present") or 0) for r in results)
        coverage_yes = sum(int(r.get("coverage_present") or 0) for r in results)
        print(
            f"Done in {t_elapsed}s. ok={ok}, skipped={skipped}, err={err}. "
            f"Tables: {tables_yes}/{total_rows}, Owners: {owners_yes}/{total_rows}, Coverage: {coverage_yes}/{total_rows}. "
            f"CSV: {out_csv}"
        )
    except Exception:
        print(f"Done in {t_elapsed}s. ok={ok}, skipped={skipped}, err={err}. CSV: {out_csv}")


if __name__ == "__main__":  # pragma: no cover
    main()
