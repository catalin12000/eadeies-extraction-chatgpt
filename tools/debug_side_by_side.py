#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import html
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure repository root is importable
THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse helpers from evaluation where possible
from benchmark_evaluation import (
    load_ground_truth,
    extract_ground_truth_owners,
    load_structured,
    extract_json_owners,
    normalize_kaek,
    equivalent_kaek,
    parse_float,
    GROUPS,
    COVERAGE_KEYS,
    _norm_header,
)


def find_pdf_for_stem(stem: str, pdf_dirs: List[Path]) -> Optional[Path]:
    candidates = [f"{stem}.pdf", f"{stem}.PDF"]
    for d in pdf_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for name in candidates:
            p = d / name
            if p.exists():
                return p
    return None


def extract_docling_text(pdf: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:
        return ""
    conv = DocumentConverter()
    res = conv.convert(str(pdf))
    # Note: export_to_text triggers a deprecation warning internally; harmless.
    txt = res.document.export_to_text() if hasattr(res.document, "export_to_text") else str(res.document)
    return (txt or "").strip()


def collect_mismatch_stems(report_path: Path, extractor: str = "docling", limit: int = 0) -> List[str]:
    if not report_path.exists():
        return []
    data = json.loads(report_path.read_text(encoding="utf-8"))
    per = (data.get(extractor) or {}).get("per_stem") or {}
    stems: List[str] = []
    for stem, m in per.items():
        kaek_ok = bool(m.get("kaek_match"))
        owners_f1 = float(m.get("owners_f1", 1.0) or 0.0)
        cov_ratio = float(m.get("coverage_exact_ratio", 1.0) or 0.0)
        if (not kaek_ok) or owners_f1 < 0.999999 or cov_ratio < 0.999999:
            stems.append(stem)
    stems.sort()
    if limit and len(stems) > limit:
        stems = stems[:limit]
    return stems


def render_case_html(stem: str, pdf_rel: str, text: str, gt_row: dict, parsed: Optional[dict]) -> str:
    # Precompute GT coverage map
    gt_cov: Dict[Tuple[str, str], Optional[float]] = {}
    for g in GROUPS:
        for k in COVERAGE_KEYS:
            header = _norm_header(f"{g} - {k}")
            raw = None
            for h, v in gt_row.items():
                if _norm_header(h) == header:
                    raw = v
                    break
            gt_cov[(g, k)] = parse_float(raw) if raw is not None else None

    parsed_cov = (parsed or {}).get("Στοιχεία Διαγράμματος Κάλυψης", {}) if parsed else {}
    parsed_owners = extract_json_owners(parsed) if parsed else []
    gt_owners = extract_ground_truth_owners(gt_row)

    # Build minimal HTML
    parts: List[str] = []
    parts.append("<!doctype html><meta charset='utf-8'><title>Case Debug</title>")
    parts.append("<style>body{font-family:system-ui,Arial,sans-serif;margin:12px} .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px} pre{white-space:pre-wrap;border:1px solid #ddd;padding:8px;border-radius:8px;background:#fafafa;max-height:80vh;overflow:auto} .pdf{width:100%;height:85vh;border:1px solid #ddd;border-radius:8px} table{border-collapse:collapse;width:100%} td,th{border:1px solid #eee;padding:6px 8px;text-align:left} th{background:#f8f8f8} .ok{background:#e8f7ee} .bad{background:#fdecea} .pill{display:inline-block;padding:2px 6px;border:1px solid #ccc;border-radius:999px;font-size:12px;margin-right:6px} .muted{color:#666} .section{margin-top:18px}</style>")
    parts.append(f"<h2>{html.escape(stem)}</h2>")
    parts.append("<div class='grid'>")
    parts.append(f"<div><object class='pdf' data='{html.escape(pdf_rel)}' type='application/pdf'><a href='{html.escape(pdf_rel)}'>Open PDF</a></object></div>")
    parts.append(f"<div><div class='pill'>Extracted text (docling)</div><pre>{html.escape(text)}</pre></div>")
    parts.append("</div>")

    # Summary block
    gt_kaek = normalize_kaek(gt_row.get("ΚΑΕΚ") or "")
    pred_kaek = normalize_kaek((parsed or {}).get("ΚΑΕΚ", ""))
    k_ok = equivalent_kaek(pred_kaek, gt_kaek)
    parts.append("<h3 class='section'>Summary</h3>")
    parts.append("<table><thead><tr><th>Field</th><th>GT</th><th>Pred</th><th>Status</th></tr></thead><tbody>")
    parts.append(f"<tr class='{ 'ok' if k_ok else 'bad'}'><td>KAEK</td><td>{html.escape(gt_kaek)}</td><td>{html.escape(pred_kaek)}</td><td>{'✓' if k_ok else '✗'}</td></tr>")

    # Owners
    gt_set = {o.key() for o in gt_owners}
    pred_set = {o.key() for o in parsed_owners}
    miss = gt_set - pred_set
    extra = pred_set - gt_set
    o_ok = not miss and not extra
    parts.append(f"<tr class='{ 'ok' if o_ok else 'bad'}'><td>Owners</td><td>{len(gt_owners)}</td><td>{len(parsed_owners)}</td><td>{'✓' if o_ok else '✗'}</td></tr>")
    parts.append("</tbody></table>")

    # Not recognized items (present in GT but missing in prediction)
    missing_items: List[str] = []
    if (gt_kaek or "") and not (pred_kaek or ""):
        missing_items.append("KAEK (not found)")
    for sur, nam in sorted(miss):
        missing_items.append(f"Owner missing: {html.escape(sur)} — {html.escape(nam)}")
    for g in GROUPS:
        for k in COVERAGE_KEYS:
            gt_v = gt_cov[(g, k)]
            pred_v = (parsed_cov.get(g, {}) or {}).get(k)
            if gt_v is not None and not isinstance(pred_v, (int, float)):
                missing_items.append(f"Coverage missing: {html.escape(g)} — {html.escape(k)}")

    if missing_items:
        parts.append("<h3 class='section'>Not recognized items</h3><ul>")
        for item in missing_items:
            parts.append(f"<li>{item}</li>")
        parts.append("</ul>")

    # Coverage details where mismatch
    parts.append("<h3 class='section'>Coverage mismatches</h3>")
    parts.append("<table><thead><tr><th>Group</th><th>Key</th><th>GT</th><th>Pred</th><th>Δ</th></tr></thead><tbody>")
    compact_diffs: List[str] = []
    for g in GROUPS:
        for k in COVERAGE_KEYS:
            gt_v = gt_cov[(g, k)]
            pred_v = (parsed_cov.get(g, {}) or {}).get(k)
            if isinstance(pred_v, (int, float)) and gt_v is not None:
                diff = pred_v - gt_v
                if abs(diff) > 1e-6:
                    parts.append(f"<tr class='bad'><td>{html.escape(g)}</td><td>{html.escape(k)}</td><td>{gt_v}</td><td>{pred_v}</td><td>{diff:+.6g}</td></tr>")
                    compact_diffs.append(f"{html.escape(g)} — {html.escape(k)}: GT {gt_v} vs Pred {pred_v} (Δ {diff:+.6g})")
            else:
                # Missing value but GT present
                if gt_v is not None:
                    parts.append(f"<tr class='bad'><td>{html.escape(g)}</td><td>{html.escape(k)}</td><td>{gt_v}</td><td>—</td><td>—</td></tr>")
    parts.append("</tbody></table>")

    if (not k_ok) or compact_diffs:
        parts.append("<div class='muted'>")
        if not k_ok:
            parts.append(f"<div><strong>KAEK differs</strong>: GT {html.escape(gt_kaek)} vs Pred {html.escape(pred_kaek)}</div>")
        if compact_diffs:
            parts.append("<div><strong>Coverage diffs (compact)</strong>:</div><ul>")
            for d in compact_diffs[:30]:
                parts.append(f"<li>{d}</li>")
            if len(compact_diffs) > 30:
                parts.append(f"<li>… and {len(compact_diffs) - 30} more</li>")
            parts.append("</ul>")
        parts.append("</div>")

    # Owners details when not exact
    if miss or extra:
        parts.append("<h3 class='section'>Owners diff</h3><div class='pill'>Missing vs GT</div><ul>")
        for sur, nam in sorted(miss):
            parts.append(f"<li>{html.escape(sur)} — {html.escape(nam)}</li>")
        parts.append("</ul><div class='pill'>Extra vs GT</div><ul>")
        for sur, nam in sorted(extra):
            parts.append(f"<li>{html.escape(sur)} — {html.escape(nam)}</li>")
        parts.append("</ul>")

    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Generate side-by-side PDF vs text pages for mismatch stems")
    ap.add_argument("--benchmark-csv", type=Path, default=Path("data/01_benchmark/eadeies_final.csv"))
    ap.add_argument("--report", type=Path, default=Path("debug/benchmark_report.json"))
    ap.add_argument("--structured-dir", type=Path, default=Path("debug/structured_json"))
    ap.add_argument("--pdf-dirs", type=Path, nargs="*", default=[Path("data/Athens"), Path("data/Thessaloniki"), Path("data/Pireaues"), Path("data/Mike"), Path("data/test")])
    ap.add_argument("--out-dir", type=Path, default=Path("debug/case_debug"))
    ap.add_argument("--stems", nargs="*", help="Optional stems to include explicitly")
    ap.add_argument("--limit", type=int, default=12, help="Max number of cases (0 = no limit)")
    args = ap.parse_args()

    gt_rows = load_ground_truth(args.benchmark_csv)
    if args.stems:
        stems = list(args.stems)
    else:
        stems = collect_mismatch_stems(args.report, extractor="docling", limit=args.limit)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    index_parts = ["<!doctype html><meta charset='utf-8'><title>Case Debug Index</title>", "<h2>Mismatch Cases</h2>", "<ul>"]

    for stem in stems:
        gt = gt_rows.get(stem)
        if not gt:
            continue
        pdf = find_pdf_for_stem(stem, list(args.pdf_dirs))
        if not pdf:
            continue
        # Copy PDF
        case_dir = out / stem
        case_dir.mkdir(parents=True, exist_ok=True)
        pdf_copy = case_dir / pdf.name
        if not pdf_copy.exists():
            try:
                shutil.copy2(pdf, pdf_copy)
            except Exception:
                shutil.copy(pdf, pdf_copy)

        # Extract text
        text = extract_docling_text(pdf)
        (case_dir / f"{stem}_docling.txt").write_text(text, encoding="utf-8")

        # Load parsed structured
        parsed = load_structured(args.structured_dir, stem, "docling")

        # Render page
        rel_pdf = os.path.relpath(pdf_copy, start=case_dir)
        html_text = render_case_html(stem, rel_pdf, text, gt, parsed)
        (case_dir / "index.html").write_text(html_text, encoding="utf-8")

        index_parts.append(f"<li><a href='{stem}/index.html'>{html.escape(stem)}</a></li>")

    index_parts.append("</ul>")
    (out / "index.html").write_text("".join(index_parts), encoding="utf-8")
    print(f"Wrote cases to {out} (index.html)")


if __name__ == "__main__":
    main()
