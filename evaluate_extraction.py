"""Evaluate extraction correctness between pdfplumber and docling outputs.

Assumes you already ran compare_pdf_extractors.py with --save-text producing:
  debug/compare/<STEM>_pdfplumber.txt
  debug/compare/<STEM>_docling.txt

We parse owners table and coverage metrics from both, normalize numbers, and
produce a JSON report with cell-level comparisons plus aggregate metrics.

Usage:
  python evaluate_extraction.py --stem 63ΤΛ46Ψ842-Ξ2Μ 
  python evaluate_extraction.py --pdf data/Athens/63ΤΛ46Ψ842-Ξ2Μ.pdf
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import List, Dict, Any, Tuple, Optional

EU_NUM_RE = re.compile(r"^[0-9][0-9\.]*,[0-9]+$|^[0-9][0-9\.]*$")

def parse_eu_number(s: str) -> Optional[float]:
    s = s.strip()
    if not s or s.lower() in {"-", "--", "α", "a"}:
        return None
    s2 = s.replace(" ", "")
    if EU_NUM_RE.match(s2):
        if "," in s2:
            parts = s2.split(",")
            int_part = parts[0].replace(".", "")
            s2 = int_part + "." + parts[1]
        else:
            s2 = s2.replace(".", "")
    try:
        return float(s2)
    except ValueError:
        return None

def load_texts(stem: str, compare_dir: Path) -> Tuple[str, str]:
    pdfpl_text = (compare_dir / f"{stem}_pdfplumber.txt").read_text(encoding="utf-8")
    docling_text = (compare_dir / f"{stem}_docling.txt").read_text(encoding="utf-8")
    return pdfpl_text, docling_text

def parse_pdfplumber_owners(text: str) -> List[Dict[str, str]]:
    owners: List[Dict[str, str]] = []
    if "Στοιχεία κυρίου του έργου" not in text:
        return owners
    section = text.split("Στοιχεία κυρίου του έργου", 1)[1]
    for tok in ["Πρόσθετες", "Στοιχεία Διαγράμματος"]:
        if tok in section:
            section = section.split(tok, 1)[0]
    lines = [l.strip() for l in section.splitlines() if l.strip()]
    joined: List[str] = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and lines[i] == "Πλήρης" and lines[i + 1].startswith("κυρι"):
            joined.append(lines[i] + " " + lines[i + 1])
            i += 2
        else:
            joined.append(lines[i])
            i += 1
    for ln in joined:
        if "Επώνυμο" in ln or "Ιδιότητα" in ln:
            continue
        tokens = ln.split()
        if len(tokens) < 5:
            continue
        share_idx = None
        for idx, t in enumerate(tokens):
            if parse_eu_number(t) is not None and 0 <= parse_eu_number(t) <= 100:
                share_idx = idx
        if share_idx is None:
            continue
        if share_idx + 1 < len(tokens):
            owners.append({
                "surname": tokens[0],
                "given": tokens[1],
                "role": tokens[3] if share_idx >= 4 else "",
                "share": tokens[share_idx],
                "right": " ".join(tokens[share_idx + 1:])
            })
    return owners

def parse_docling_markdown_table(block: str) -> List[List[str]]:
    lines = [l for l in block.splitlines() if l.strip().startswith("|")]
    rows: List[List[str]] = []
    for l in lines:
        parts = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r"-+", p) for p in parts):
            continue
        rows.append(parts)
    return rows

def extract_docling_tables(text: str) -> List[List[List[str]]]:
    tables: List[List[List[str]]] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line)
        else:
            if current:
                tables.append(parse_docling_markdown_table("\n".join(current)))
                current = []
    if current:
        tables.append(parse_docling_markdown_table("\n".join(current)))
    return tables

def parse_docling_owners(text: str) -> List[Dict[str, str]]:
    owners: List[Dict[str, str]] = []
    tables = extract_docling_tables(text)
    for tbl in tables:
        if not tbl:
            continue
        header = [h.lower() for h in tbl[0]]
        if "επώνυμο/ία" in header and "ποσοστό" in header:
            for row in tbl[1:]:
                if len(row) < len(header):
                    continue
                mapping = dict(zip(header, row))
                owners.append({
                    "surname": mapping.get("επώνυμο/ία", ""),
                    "given": mapping.get("όνομα", ""),
                    "role": mapping.get("ιδιότητα", ""),
                    "share": mapping.get("ποσοστό", ""),
                    "right": mapping.get("τύπος δικαιώματος", ""),
                })
    return owners

COVERAGE_KEYS = [
    "Εμβ. κάλυψης κτιρίου",
    "Εμβ. δόμησης κτιρίου",
    "Εμβ. ακάλυπτου χώρου οικοπέδου",
    "Όγκος κτιρίου (άνω εδάφους)",
    "Μέγιστο ύψος κτιρίου",
    "Αριθμός Ορόφων",
    "Αριθμός Θέσεων Στάθμευσης",
]

def parse_pdfplumber_coverage(text: str) -> Dict[str, Dict[str, Optional[float]]]:
    if "Στοιχεία Διαγράμματος Κάλυψης" not in text:
        return {}
    section = text.split("Στοιχεία Διαγράμματος Κάλυψης", 1)[1]
    lines = [l.strip() for l in section.splitlines() if l.strip()]
    coverage: Dict[str, Dict[str, Optional[float]]] = {}
    for ln in lines:
        for key in COVERAGE_KEYS:
            if ln.startswith(key):
                nums = re.findall(r"[0-9][0-9\.,]*", ln[len(key):])
                values = [parse_eu_number(n) for n in nums[:4]]
                while len(values) < 4:
                    values.append(None)
                coverage[key] = {
                    "ΥΦΙΣΤΑΜΕΝΑ": values[0],
                    "ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ": values[1],
                    "ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ": values[2],
                    "ΣΥΝΟΛΟ": values[3],
                }
    return coverage

def parse_docling_coverage(text: str) -> Dict[str, Dict[str, Optional[float]]]:
    tables = extract_docling_tables(text)
    coverage: Dict[str, Dict[str, Optional[float]]] = {}
    for tbl in tables:
        if not tbl:
            continue
        if len(tbl) < 2:
            continue
        for row in tbl[1:]:
            if len(row) == 5 and row[0] in COVERAGE_KEYS:
                coverage[row[0]] = {
                    "ΥΦΙΣΤΑΜΕΝΑ": parse_eu_number(row[1]),
                    "ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ": parse_eu_number(row[2]),
                    "ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ": parse_eu_number(row[3]),
                    "ΣΥΝΟΛΟ": parse_eu_number(row[4]),
                }
    return coverage

def compare_owners(a: List[Dict[str, str]], b: List[Dict[str, str]]) -> Dict[str, Any]:
    def norm_name(o):
        return f"{o.get('surname','').strip()} {o.get('given','').strip()}".strip()
    set_a = {norm_name(o) for o in a if norm_name(o)}
    set_b = {norm_name(o) for o in b if norm_name(o)}
    return {
        "pdfplumber_count": len(a),
        "docling_count": len(b),
        "name_intersection": len(set_a & set_b),
        "names_only_pdfplumber": sorted(set_a - set_b),
        "names_only_docling": sorted(set_b - set_a),
        "exact_match": set_a == set_b,
    }

def compare_coverage(a: Dict[str, Dict[str, Optional[float]]], b: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Any]:
    diffs = []
    exact = 0
    total = 0
    cells = []
    for key in COVERAGE_KEYS:
        for col in ["ΥΦΙΣΤΑΜΕΝΑ", "ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ", "ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ", "ΣΥΝΟΛΟ"]:
            av = a.get(key, {}).get(col)
            bv = b.get(key, {}).get(col)
            total += 1
            if av is not None and bv is not None and abs(av - bv) < 1e-6:
                exact += 1
            if av is not None and bv is not None and abs(av - bv) >= 1e-6:
                diffs.append({"row": key, "col": col, "pdfplumber": av, "docling": bv, "delta": round((bv - av), 6)})
            cells.append({"row": key, "col": col, "pdfplumber": av, "docling": bv})
    return {
        "exact_cell_matches": exact,
        "total_cells": total,
        "accuracy": round(exact / total, 4) if total else 0.0,
        "differences": diffs,
        "cells": cells,
    }

def evaluate(stem: str, compare_dir: Path, output_dir: Path) -> Dict[str, Any]:
    pdfpl_text, docling_text = load_texts(stem, compare_dir)
    owners_pdf = parse_pdfplumber_owners(pdfpl_text)
    owners_doc = parse_docling_owners(docling_text)
    cov_pdf = parse_pdfplumber_coverage(pdfpl_text)
    cov_doc = parse_docling_coverage(docling_text)
    owners_cmp = compare_owners(owners_pdf, owners_doc)
    coverage_cmp = compare_coverage(cov_pdf, cov_doc)
    report = {
        "stem": stem,
        "owners_pdfplumber": owners_pdf,
        "owners_docling": owners_doc,
        "owners_comparison": owners_cmp,
        "coverage_pdfplumber": cov_pdf,
        "coverage_docling": cov_doc,
        "coverage_comparison": coverage_cmp,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stem}_accuracy.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

def main():
    parser = argparse.ArgumentParser(description="Evaluate correctness between extractors")
    parser.add_argument("--stem", help="PDF filename stem (without extension)")
    parser.add_argument("--pdf", type=Path, help="Path to PDF (derive stem)", required=False)
    parser.add_argument("--compare-dir", type=Path, default=Path("debug/compare"), help="Directory containing extracted txt files")
    parser.add_argument("--output-dir", type=Path, default=Path("debug/compare"), help="Directory to write accuracy report")
    args = parser.parse_args()
    if not args.stem and not args.pdf:
        parser.error("Provide either --stem or --pdf")
    stem = args.stem or args.pdf.stem  # type: ignore
    report = evaluate(stem, args.compare_dir, args.output_dir)
    print(json.dumps(report["owners_comparison"], ensure_ascii=False, indent=2))
    print(json.dumps(report["coverage_comparison"], ensure_ascii=False, indent=2))

if __name__ == "__main__":  # pragma: no cover
    main()
