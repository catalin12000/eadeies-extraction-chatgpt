#!/usr/bin/env python3
import argparse
import glob
import json
import os
import statistics
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Time per-file extraction for the docling engine.")
    parser.add_argument("--engine", default="docling", choices=["docling"], help="Extractor engine (docling only)")
    parser.add_argument("--pattern", default="data/test/*.pdf", help="Glob pattern for PDFs")
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to repeat each file (>=1)")
    parser.add_argument("--save", action="store_true", help="Also save structured JSON (default: don't save)")
    parser.add_argument("--out-dir", default="debug/structured_json", help="Output dir when --save is used")
    parser.add_argument("--warmup", type=int, default=0, help="Warm-up runs before timing (per file)")
    args = parser.parse_args()

    # Ensure project root on sys.path for imports when running from anywhere
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from keep.build_structured_json import extract_pdf_to_structured
    except Exception:
        # Fallback to top-level if keep copy isn't present
        from build_structured_json import extract_pdf_to_structured

    pdfs = sorted(glob.glob(args.pattern))
    if not pdfs:
        print(json.dumps({"error": f"No PDFs matched pattern: {args.pattern}"}, ensure_ascii=False))
        sys.exit(1)

    results = []
    for pdf in pdfs:
        # Optional warm-up to account for cold starts
        for _ in range(max(0, args.warmup)):
            try:
                _ = extract_pdf_to_structured(Path(pdf), args.engine)
            except Exception:
                pass

        per_runs = []
        for _ in range(max(1, args.repeat)):
            t0 = time.perf_counter()
            data = extract_pdf_to_structured(Path(pdf), args.engine)
            dt = time.perf_counter() - t0
            per_runs.append(dt)
            if args.save:
                out_dir = Path(args.out_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                stem = Path(pdf).stem
                out_path = out_dir / f"{stem}_{args.engine}_structured.json"
                out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append({
            "file": pdf,
            "times_sec": per_runs,
            "avg_sec": statistics.mean(per_runs),
            "min_sec": min(per_runs),
            "max_sec": max(per_runs),
        })

    flat_times = [t for r in results for t in r["times_sec"]]
    summary = {
        "engine": args.engine,
        "pattern": args.pattern,
        "repeat": args.repeat,
        "files": len(pdfs),
        "total_runs": len(flat_times),
        "avg_sec": statistics.mean(flat_times),
        "min_sec": min(flat_times),
        "max_sec": max(flat_times),
        "p50_sec": statistics.median(flat_times),
        "p90_sec": percentile(flat_times, 90),
        "p95_sec": percentile(flat_times, 95),
    }

    print(json.dumps({"summary": summary, "details": results}, ensure_ascii=False, indent=2))


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values)-1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[int(k)]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return d0 + d1


if __name__ == "__main__":
    main()
