#!/usr/bin/env python3
"""Compare PDF text extraction between pdfplumber and docling (single file or batch).

Note: Project is now docling-only for downstream parsing. This script remains for 
raw text comparison and can run with only docling available; pdfplumber is optional.

Usage (single file):
    python compare_pdf_extractors.py --pdf path/to/file.pdf [--output-dir ./debug]

Usage (batch over directory tree):
    python compare_pdf_extractors.py --root ./data [--output-dir ./debug] [--save-text]

Produces per-file JSON comparison plus an aggregated summary when --root is used.

Per-file metrics:
    - extraction_time_sec
    - chars, lines, avg_line_len
    - whitespace_ratio, ascii_ratio
    - md5 hash
    - approx_tokens (chars/4 heuristic)
    - similarity_ratio (difflib on full text if both succeed)

Aggregate summary (batch mode):
    - counts of successes per engine
    - average chars / lines / extraction time
    - average similarity (over successful pairs)

If docling isn't installed, its section will show an error field and batch will continue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
import re
import sys
import difflib
from dataclasses import dataclass
from typing import Optional, Dict, Any, Iterable, List

# pdfplumber import (optional)
try:
    import pdfplumber  # type: ignore
    _PDFPLUMBER_AVAILABLE = True
except Exception:
    _PDFPLUMBER_AVAILABLE = False

# Optional docling import
try:
    from docling.document_converter import DocumentConverter  # type: ignore
    _DOCLING_AVAILABLE = True
except Exception:  # pragma: no cover
    _DOCLING_AVAILABLE = False


@dataclass
class ExtractionResult:
    ok: bool
    engine: str
    text: str = ""
    extraction_time_sec: float = 0.0
    error: Optional[str] = None

    def metrics(self) -> Dict[str, Any]:
        if not self.ok:
            return {"engine": self.engine, "ok": False, "error": self.error}
        text = self.text
        chars = len(text)
        lines = text.count("\n") + (1 if text else 0)
        avg_line_len = chars / lines if lines else 0
        whitespace = sum(c.isspace() for c in text)
        ascii_printable = sum(32 <= ord(c) <= 126 for c in text)
        whitespace_ratio = whitespace / chars if chars else 0
        ascii_ratio = ascii_printable / chars if chars else 0
        md5 = hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()
        approx_tokens = round(chars / 4)
        return {
            "engine": self.engine,
            "ok": True,
            "extraction_time_sec": round(self.extraction_time_sec, 4),
            "chars": chars,
            "lines": lines,
            "avg_line_len": round(avg_line_len, 2),
            "whitespace_ratio": round(whitespace_ratio, 4),
            "ascii_ratio": round(ascii_ratio, 4),
            "md5": md5,
            "approx_tokens": approx_tokens,
        }


def extract_pdfplumber(pdf_path: Path) -> ExtractionResult:
    if not _PDFPLUMBER_AVAILABLE:
        return ExtractionResult(False, "pdfplumber", error="pdfplumber not installed")
    start = time.perf_counter()
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        text = "\n\n".join(pages)
        # Basic cleaning similar to existing loader
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n\n", text)
        elapsed = time.perf_counter() - start
        return ExtractionResult(True, "pdfplumber", text=text.strip(), extraction_time_sec=elapsed)
    except Exception as e:  # pragma: no cover
        return ExtractionResult(False, "pdfplumber", error=str(e), extraction_time_sec=time.perf_counter() - start)


def extract_docling(pdf_path: Path) -> ExtractionResult:
    if not _DOCLING_AVAILABLE:
        return ExtractionResult(False, "docling", error="docling not installed")
    start = time.perf_counter()
    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        # result.document.export_to_text()
        text = result.document.export_to_text() if hasattr(result.document, "export_to_text") else str(result.document)
        elapsed = time.perf_counter() - start
        return ExtractionResult(True, "docling", text=text.strip(), extraction_time_sec=elapsed)
    except Exception as e:  # pragma: no cover
        return ExtractionResult(False, "docling", error=str(e), extraction_time_sec=time.perf_counter() - start)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 4)


def discover_pdfs(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.pdf") if p.is_file()]


def process_single(pdf_path: Path, output_dir: Path, save_text: bool, sample_lines: int) -> Dict[str, Any]:
    r_pdfplumber = extract_pdfplumber(pdf_path)
    r_docling = extract_docling(pdf_path)
    metrics_pdfplumber = r_pdfplumber.metrics()
    metrics_docling = r_docling.metrics()
    sim_ratio = similarity(r_pdfplumber.text, r_docling.text) if (r_pdfplumber.ok and r_docling.ok) else None
    summary = {
        "file": str(pdf_path),
        "pdfplumber": metrics_pdfplumber,
        "docling": metrics_docling,
        "similarity_ratio": sim_ratio,
    }
    json_path = output_dir / f"{pdf_path.stem}_compare.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if save_text:
        if r_pdfplumber.ok:
            (output_dir / f"{pdf_path.stem}_pdfplumber.txt").write_text(r_pdfplumber.text, encoding="utf-8")
        if r_docling.ok:
            (output_dir / f"{pdf_path.stem}_docling.txt").write_text(r_docling.text, encoding="utf-8")
    if sample_lines > 0:
        def head_lines(t: str) -> str:
            return "\n".join(t.splitlines()[: sample_lines])
        print(f"\n=== {pdf_path.name} ===")
        print("--- pdfplumber sample ---")
        print(head_lines(r_pdfplumber.text) if r_pdfplumber.ok else f"ERROR: {r_pdfplumber.error}")
        print("--- docling sample ---")
        print(head_lines(r_docling.text) if r_docling.ok else f"ERROR: {r_docling.error}")
    return summary


def aggregate(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not summaries:
        return {}
    def collect(engine: str, key: str) -> List[float]:
        vals = []
        for s in summaries:
            eng = s.get(engine, {})
            if eng.get("ok") and isinstance(eng.get(key), (int, float)):
                vals.append(eng[key])
        return vals
    pdf_ok = sum(1 for s in summaries if s.get("pdfplumber", {}).get("ok"))
    doc_ok = sum(1 for s in summaries if s.get("docling", {}).get("ok"))
    sims = [s["similarity_ratio"] for s in summaries if isinstance(s.get("similarity_ratio"), (int, float))]
    avg = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0
    return {
        "files": len(summaries),
        "pdfplumber_success": pdf_ok,
        "docling_success": doc_ok,
        "avg_pdfplumber_chars": avg(collect("pdfplumber", "chars")),
        "avg_docling_chars": avg(collect("docling", "chars")),
        "avg_pdfplumber_time": avg(collect("pdfplumber", "extraction_time_sec")),
        "avg_docling_time": avg(collect("docling", "extraction_time_sec")),
        "avg_similarity": avg(sims),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare pdfplumber and docling text extraction")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pdf", type=Path, help="Path to a single PDF file")
    group.add_argument("--root", type=Path, help="Root directory to recursively search for PDFs")
    parser.add_argument("--output-dir", type=Path, default=Path("./debug/compare"), help="Directory to save outputs")
    parser.add_argument("--save-text", action="store_true", help="Save raw extracted text files")
    parser.add_argument("--sample-lines", type=int, default=5, help="Show first N lines sample for each engine (per file)")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.pdf:
        if not args.pdf.exists():
            raise SystemExit(f"PDF not found: {args.pdf}")
        summary = process_single(args.pdf, args.output_dir, args.save_text, args.sample_lines)
        print("\nSingle file summary:")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        if not args.root.exists():
            raise SystemExit(f"Root not found: {args.root}")
        pdfs = discover_pdfs(args.root)
        if not pdfs:
            raise SystemExit("No PDFs discovered under root.")
        summaries: List[Dict[str, Any]] = []
        for pdf in sorted(pdfs):
            summaries.append(process_single(pdf, args.output_dir, args.save_text, args.sample_lines))
        agg = aggregate(summaries)
        (args.output_dir / "_aggregate_summary.json").write_text(
            json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("\nAggregate summary:")
        print(json.dumps(agg, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
