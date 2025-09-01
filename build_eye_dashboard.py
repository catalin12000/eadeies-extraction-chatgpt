"""Build a single HTML dashboard for eyeballing extractions vs ground truth.

This script renders, per stem (ΑΔΑ):
  - KAEK: GT vs per-extractor values (match highlighting)
  - Owners: GT list and per-extractor list with differences highlighted
  - Coverage table: GT numeric cells vs per-extractor values, with exact match/diff
  - Embedded PDF (if found under known data folders)

Inputs (defaults chosen for this repo layout):
  --benchmark-csv data/01_benchmark/eadeies_final.csv
  --structured-dir debug/structured_json
  --pdf-dirs data/Athens data/Thessaloniki data/Pireaues data/Mike
    --extractors docling
  --out debug/eye_dashboard.html

Usage:
  python build_eye_dashboard.py [--args]

Notes:
  - Reuses normalization/loading helpers from benchmark_evaluation.py
  - Gracefully handles missing JSONs or PDFs
  - Designed for quick manual inspection, not for metrics
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Reuse helpers from the evaluation script to ensure consistent parsing/normalization
from benchmark_evaluation import (
    GROUPS,
    COVERAGE_KEYS,
    load_ground_truth,
    extract_ground_truth_owners,
    load_structured,
    extract_json_owners,
    normalize_kaek,
    equivalent_kaek,
    parse_float,
    _norm_header,
)


def find_pdf_for_stem(stem: str, pdf_dirs: List[Path]) -> Optional[Path]:
    """Return the first matching PDF path for the given stem searching in given dirs.

    Checks for exact '{stem}.pdf' or '{stem}.PDF' files inside each dir (non-recursive).
    """
    candidates = [f"{stem}.pdf", f"{stem}.PDF"]
    for d in pdf_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for name in candidates:
            p = d / name
            if p.exists():
                return p
    return None


def owner_pairs_display(owners) -> List[str]:
    items = []
    for o in owners:
        # o may be Owner dataclass or dict with 'surname'/'name'
        surname = getattr(o, "surname", None) or o.get("surname") if isinstance(o, dict) else None
        name = getattr(o, "name", None) or o.get("name") if isinstance(o, dict) else None
        if surname is None and name is None:
            # Fallback: try dict-like
            try:
                surname = o[0]
                name = o[1]
            except Exception:
                surname = str(o)
                name = ""
        items.append(f"{html.escape(str(surname))} — {html.escape(str(name))}")
    return items


def render_html(
    stems: List[str],
    gt_rows: Dict[str, dict],
    structured_dir: Path,
    pdf_dirs: List[Path],
    extractors: List[str],
    out_dir: Path,
) -> str:
    # Pre-scan PDFs for performance
    pdf_map: Dict[str, Optional[Path]] = {}
    for stem in stems:
        pdf_map[stem] = find_pdf_for_stem(stem, pdf_dirs)

    # Basic styles for quick contrast
    styles = """
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 16px; }
    .grid { display: grid; grid-template-columns: 280px 1fr; gap: 12px; align-items: start; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.04);} 
    .stem { font-weight: 700; font-size: 18px; }
    .ok { background: #e8f7ee; }
    .bad { background: #fdecea; }
    .warn { background: #fff7e6; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #eee; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { background: #fafafa; position: sticky; top: 0; z-index: 1; }
    details { margin-top: 8px; }
    .muted { color: #666; }
    .section-title { margin: 8px 0 6px; font-weight: 600; }
    .pill { display: inline-block; padding: 2px 6px; border-radius: 999px; font-size: 12px; border: 1px solid #ddd; background: #f8f8f8; }
    .owners { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }
    .owner-list { border: 1px solid #eee; border-radius: 6px; padding: 8px; background: #fcfcfc; }
    .toc { position: sticky; top: 8px; max-height: 90vh; overflow: auto; }
    .kaek { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    .diff { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    summary { cursor: pointer; }
    .pdf-frame { width: 100%; height: 800px; border: 1px solid #eee; border-radius: 8px; }
    .not-found { color: #a00; }
    .extractor { font-weight: 600; }
    """

    # Build content
    parts: List[str] = []
    parts.append("<!doctype html><html lang=\"el\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    parts.append(f"<title>Eye Dashboard</title><style>{styles}</style></head><body>")
    parts.append("<h1>Eye Evaluation Dashboard</h1>")
    parts.append("<p class=\"muted\">Ground truth from CSV vs structured JSONs. Click a stem to jump; expand PDF to view.</p>")

    # TOC
    parts.append("<div class=\"grid\">")
    # Left column: TOC
    parts.append("<div class=\"card toc\"><div class=\"section-title\">Stems</div><ol>")
    for stem in stems:
        parts.append(f"<li><a href=\"#{html.escape(stem)}\">{html.escape(stem)}</a></li>")
    parts.append("</ol></div>")

    # Right column: content
    parts.append("<div class=\"content-col\">")

    for stem in stems:
        gt = gt_rows.get(stem)
        if not gt:
            continue
        parts.append(f"<div class=\"card\" id=\"{html.escape(stem)}\">")
        parts.append(f"<div class=\"stem\">{html.escape(stem)}</div>")

        # KAEK row
        gt_kaek = normalize_kaek(gt.get("ΚΑΕΚ") or "")
        parts.append("<div class=\"section-title\">KAEK</div>")
        parts.append("<table><thead><tr><th>Source</th><th>Value</th><th>Match GT</th></tr></thead><tbody>")
        parts.append(f"<tr><td>GT</td><td class=\"kaek\">{html.escape(gt_kaek)}</td><td class=\"muted\">—</td></tr>")

        # Load per-extractor JSONs
        per_extractor_data: Dict[str, Optional[dict]] = {}
        for ex in extractors:
            per_extractor_data[ex] = load_structured(structured_dir, stem, ex)
            pred = (per_extractor_data[ex] or {}).get("ΚΑΕΚ", "")
            pred_norm = normalize_kaek(pred)
            match = equivalent_kaek(pred_norm, gt_kaek)
            cls = "ok" if match else "bad"
            parts.append(
                f"<tr class=\"{cls}\"><td class=\"extractor\">{html.escape(ex)}</td><td class=\"kaek\">{html.escape(pred_norm)}</td><td>{'✓' if match else '✗'}</td></tr>"
            )
        parts.append("</tbody></table>")

        # Owners section
        parts.append("<div class=\"section-title\">Owners</div>")
        gt_owners = extract_ground_truth_owners(gt)
        gt_set = {o.key() for o in gt_owners}
        parts.append("<div class=\"owners\">")
        # GT list
        parts.append("<div class=\"owner-list\"><div class=\"pill\">GT</div><ul>")
        for o in gt_owners:
            parts.append(f"<li>{html.escape(o.surname)} — {html.escape(o.name)}</li>")
        if not gt_owners:
            parts.append("<li class=\"muted\">(no owners)</li>")
        parts.append("</ul></div>")

        # Extractor lists with differences
        for ex in extractors:
            data = per_extractor_data.get(ex)
            pred_owners = extract_json_owners(data) if data else []
            pred_set = {o.key() for o in pred_owners}
            missing = gt_set - pred_set
            extra = pred_set - gt_set
            cls = "ok" if not missing and not extra else ("warn" if not missing and extra or missing and not extra else "bad")
            parts.append(f"<div class=\"owner-list {cls}\"><div class=\"pill\">{html.escape(ex)}</div><ul>")
            # Show predicted owners
            for o in pred_owners:
                nk = o.key()
                flag = ""
                if nk in extra:
                    flag = " <span class=\"muted\">(extra)</span>"
                parts.append(f"<li>{html.escape(o.surname)} — {html.escape(o.name)}{flag}</li>")
            if not pred_owners:
                parts.append("<li class=\"muted\">(no owners)</li>")
            # Show missing
            if missing:
                parts.append("</ul><div class=\"muted\" style=\"margin-top:6px\"><b>Missing vs GT:</b><ul>")
                for sur, nam in sorted(missing):
                    parts.append(f"<li class=\"diff\">{html.escape(sur)} — {html.escape(nam)}</li>")
                parts.append("</ul></div>")
            parts.append("</div>")
        parts.append("</div>")  # owners grid

        # Coverage section
        parts.append("<div class=\"section-title\">Coverage</div>")
        parts.append("<table><thead><tr><th>Group</th><th>Key</th><th>GT</th>")
        for ex in extractors:
            parts.append(f"<th>{html.escape(ex)}</th><th>Δ</th>")
        parts.append("</tr></thead><tbody>")

        # Precompute GT values in a dict keyed by (group,key)
        gt_cov: Dict[Tuple[str, str], Optional[float]] = {}
        for g in GROUPS:
            for k in COVERAGE_KEYS:
                header = _norm_header(f"{g} - {k}")
                raw = None
                for h, v in gt.items():
                    if _norm_header(h) == header:
                        raw = v
                        break
                gt_cov[(g, k)] = parse_float(raw) if raw is not None else None

        # For each cell, render predictions and diffs
        for g in GROUPS:
            for k in COVERAGE_KEYS:
                gt_val = gt_cov[(g, k)]
                parts.append(f"<tr><td>{html.escape(g)}</td><td>{html.escape(k)}</td><td>{'' if gt_val is None else gt_val}</td>")
                for ex in extractors:
                    data = per_extractor_data.get(ex) or {}
                    pred_val = (data.get("Στοιχεία Διαγράμματος Κάλυψης", {}).get(g, {}) or {}).get(k)
                    if isinstance(pred_val, (int, float)) and gt_val is not None:
                        diff = pred_val - gt_val
                        cls = "ok" if abs(diff) < 1e-6 else "bad"
                        parts.append(f"<td class=\"{cls}\">{pred_val}</td><td class=\"{cls}\">{diff:+.6g}</td>")
                    else:
                        # No value or non-numeric -> warn
                        parts.append("<td class=\"warn\">—</td><td class=\"warn\">—</td>")
                parts.append("</tr>")
        parts.append("</tbody></table>")

        # PDF section
        pdf_path = pdf_map.get(stem)
        parts.append("<details><summary>PDF</summary>")
        if pdf_path and pdf_path.exists():
            # Use path relative to the HTML file location
            rel = os.path.relpath(pdf_path, start=out_dir)
            parts.append(
                f"<object class=\"pdf-frame\" data=\"{html.escape(rel)}\" type=\"application/pdf\">"
                f"<a href=\"{html.escape(rel)}\">Open PDF</a></object>"
            )
        else:
            parts.append("<div class=\"not-found\">PDF not found</div>")
        parts.append("</details>")

        parts.append("</div>")  # card

    parts.append("</div>")  # content-col
    parts.append("</div>")  # grid
    parts.append("</body></html>")

    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Build a single HTML dashboard for eyeballing GT vs extracted data with PDFs")
    ap.add_argument("--benchmark-csv", type=Path, default=Path("data/01_benchmark/eadeies_final.csv"))
    ap.add_argument("--structured-dir", type=Path, default=Path("debug/structured_json"))
    ap.add_argument("--pdf-dirs", type=Path, nargs="*", default=[Path("data/Athens"), Path("data/Thessaloniki"), Path("data/Pireaues"), Path("data/Mike")])
    ap.add_argument("--extractors", nargs="*", default=["docling"], help="Which extractors to include (must match structured JSON filenames)")
    ap.add_argument("--out", type=Path, default=Path("debug/eye_dashboard.html"))
    ap.add_argument("--stems", nargs="*", help="Optional subset of stems to include; defaults to all from CSV")
    args = ap.parse_args()

    gt_rows = load_ground_truth(args.benchmark_csv)
    stems = args.stems if args.stems else sorted(gt_rows.keys())

    html_text = render_html(stems, gt_rows, args.structured_dir, list(args.pdf_dirs), list(args.extractors), args.out.parent)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_text, encoding="utf-8")
    print(f"Wrote eye dashboard to {args.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
