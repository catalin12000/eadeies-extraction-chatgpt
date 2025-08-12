"""Benchmark evaluation against manually curated CSV ground truth.

Inputs:
  - Ground truth CSV (hand written) with columns:
      ΑΔΑ, ΚΑΕΚ, owner related fields, and coverage columns named like:
        ΥΦΙΣΤΑΜΕΝΑ - Εμβ. κάλυψης κτιρίου
        ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ - Εμβ. δόμησης κτιρίου
        ... etc.
  - Structured JSON per extractor already produced by build_structured_json.py located in a directory.

Outputs:
  - JSON report summarizing per-extractor accuracy metrics:
        * KAEK exact match ratio
        * Owner set precision/recall/F1 (on (surname,name) pairs)
        * Coverage cell exact match ratio
        * Coverage MAE / RMSE across numeric cells
    Plus optional per-stem breakdown.

Usage:
  ./.venv/bin/python benchmark_evaluation.py \
       --benchmark-csv data/01_benchmark/eadeies_final.csv \
       --structured-dir debug/structured_json \
       --out debug/benchmark_report.json

Assumptions / Heuristics:
  - Owner fields in CSV are slash (/) separated lists aligning across columns.
  - Ignore extra spaces, newlines, quotes, non-breaking spaces.
  - Coverage values in CSV are decimal with dot OR comma, negative values allowed.
  - Structured JSON coverage groups already normalized to 4 groups with 7 keys.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

GROUPS = ["ΥΦΙΣΤΑΜΕΝΑ","ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ","ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ","ΣΥΝΟΛΟ"]
COVERAGE_KEYS = [
    "Εμβ. κάλυψης κτιρίου",
    "Εμβ. δόμησης κτιρίου",
    "Εμβ. ακάλυπτου χώρου οικοπέδου",
    "Όγκος κτιρίου (άνω εδάφους)",
    "Μέγιστο ύψος κτιρίου",
    "Αριθμός Ορόφων",
    "Αριθμός Θέσεων Στάθμευσης",
]

CORPORATE_TOKENS = {
    "AE","ΑΕ","Α.Ε.","ΕΕ","Ε.Ε.","ΟΕ","Ο.Ε.","ΙΚΕ","Ι.Κ.Ε.","ΜΟΝΟΠΡΟΣΩΠΗ","ΑΝΩΝΥΜΗ","ΕΤΑΙΡΕΙΑ","ΜΟΝΟΠΡΟΣΩΠΗΑΕ","ΜΟΝΟΠΡΟΣΩΠΗΑ.Ε.","LLC","P.C.","PC","IKE"
}

def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")

def normalize_owner_component(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\xa0"," ").replace(" "," ")
    s = strip_accents(s)
    # Remove parentheses content that is often transliterations or registry codes
    s = re.sub(r"\([^)]*\)", " ", s)
    # Replace punctuation with space
    s = re.sub(r"[.,;&:'`\-]+", " ", s)
    # Collapse slashes used as separators into space
    s = s.replace("/"," ")
    # Uppercase
    s = s.upper()
    # Tokenize and drop corporate tokens
    tokens = [t for t in s.split() if t and t not in CORPORATE_TOKENS]
    return " ".join(tokens)

@dataclass
class Owner:
    surname: str
    name: str
    def key(self) -> Tuple[str,str]:
        return (normalize_owner_component(self.surname), normalize_owner_component(self.name))

def parse_float(val: str) -> Optional[float]:
    if val is None:
        return None
    v = val.strip().replace("\xa0"," ").replace(" "," ")
    if not v:
        return None
    v = v.strip('"')
    if v.count(",") == 1 and v.count(".") >= 1:
        int_part, dec = v.split(",",1)
        int_part = int_part.replace(".","")
        v = int_part + "." + dec
    v = v.replace(",",".")
    try:
        return float(v)
    except ValueError:
        return None

def load_ground_truth(csv_path: Path):
    rows: Dict[str, dict] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            stem = (r.get("ΑΔΑ") or "").strip()
            if not stem:
                continue
            rows[stem] = r
    return rows

def split_multi(value: str) -> List[str]:
    if value is None:
        return []
    cleaned = value.replace("\n"," ")
    parts = [p.strip() for p in cleaned.split("/")]
    return [p for p in parts if p]

def extract_ground_truth_owners(row: dict) -> List[Owner]:
    surnames = split_multi(row.get("Επώνυμο/ία ")) or split_multi(row.get("Επώνυμο/ία"))
    names = split_multi(row.get("Όνομα ")) or split_multi(row.get("Όνομα"))
    count = min(len(surnames), len(names))
    owners: List[Owner] = []
    for i in range(count):
        owners.append(Owner(surnames[i], names[i]))
    return owners

def load_structured(structured_dir: Path, stem: str, extractor: str) -> Optional[dict]:
    path = structured_dir / f"{stem}_{extractor}_structured.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

def extract_json_owners(data: dict) -> List[Owner]:
    result: List[Owner] = []
    for rec in data.get("Στοιχεία κυρίου του έργου", []):
        surname = str(rec.get("Επώνυμο/ία",""))
        name = str(rec.get("Όνομα",""))
        result.append(Owner(surname, name))
    return result

def normalize_kaek(v: str) -> str:
    if v is None:
        return ""
    v = v.strip().strip('"')
    v = v.replace(" ", "")
    # Remove any duplicate slashes spacing patterns
    v = re.sub(r"/+","/", v)
    return v

def _norm_header(s: str) -> str:
    """Canonicalize a ground-truth coverage header for robust matching.

    Replaces NBSP, collapses whitespace runs, trims, and normalizes spacing around hyphen.
    """
    if s is None:
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.replace("-  ", "- ")
    return s.strip()
def equivalent_kaek(a: str, b: str) -> bool:
    """Return True if KAEK codes are equivalent under optional leading zero loss in Excel.

    Rules:
      - Exact string match -> True
      - If both plain numeric (no '/') allow removal of exactly one leading '0' on either side
        when remaining digits match.
      - Do NOT strip zeros in the middle; only a single leading zero tolerance.
    """
    if a == b:
        return True
    # Only consider tolerance for plain numeric forms
    if '/' in a or '/' in b:
        return False
    if a.startswith('0') and a[1:] == b:
        return True
    if b.startswith('0') and b[1:] == a:
        return True
    return False

def evaluate(stems: List[str], gt_rows: Dict[str, dict], structured_dir: Path):
    extractors = ["pdfplumber","docling"]
    report = {e: {"per_stem": {}, "aggregate": {}} for e in extractors}
    for extractor in extractors:
        kaek_correct = 0
        owners_tp = owners_fp = owners_fn = 0
        cov_exact = 0
        cov_total = 0
        cov_diffs: List[float] = []
        for stem in stems:
            gt = gt_rows.get(stem)
            data = load_structured(structured_dir, stem, extractor)
            if not gt or not data:
                continue
            stem_metrics = {}
            gt_kaek = normalize_kaek(gt.get("ΚΑΕΚ") or "")
            pred_kaek = normalize_kaek(data.get("ΚΑΕΚ",""))
            kaek_ok = equivalent_kaek(pred_kaek, gt_kaek)
            if kaek_ok:
                kaek_correct += 1
            stem_metrics["kaek_match"] = kaek_ok
            gt_owner_set = {o.key() for o in extract_ground_truth_owners(gt)}
            pred_owner_set = {o.key() for o in extract_json_owners(data)}
            tp = len(gt_owner_set & pred_owner_set)
            fp = len(pred_owner_set - gt_owner_set)
            fn = len(gt_owner_set - pred_owner_set)
            owners_tp += tp
            owners_fp += fp
            owners_fn += fn
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2*prec*rec/(prec+rec) if prec+rec else 0.0
            stem_metrics.update({"owners_tp": tp, "owners_fp": fp, "owners_fn": fn, "owners_precision": prec, "owners_recall": rec, "owners_f1": f1})
            pred_cov = data.get("Στοιχεία Διαγράμματος Κάλυψης", {})
            stem_cov_exact = 0
            stem_cov_total = 0
            stem_cov_mae_vals: List[float] = []
            for g in GROUPS:
                for key in COVERAGE_KEYS:
                    col_header = _norm_header(f"{g} - {key}")
                    gt_val_raw = None
                    for h, v in gt.items():
                        if _norm_header(h) == col_header:
                            gt_val_raw = v
                            break
                    gt_val = parse_float(gt_val_raw) if gt_val_raw is not None else None
                    pred_val = pred_cov.get(g, {}).get(key)
                    if gt_val is None:
                        continue
                    if isinstance(pred_val,(int,float)):
                        diff = pred_val - gt_val
                        if abs(diff) < 1e-6:
                            cov_exact += 1
                            stem_cov_exact += 1
                        cov_total += 1
                        stem_cov_total += 1
                        cov_diffs.append(abs(diff))
                        stem_cov_mae_vals.append(abs(diff))
            stem_metrics.update({
                "coverage_exact_cells": stem_cov_exact,
                "coverage_total_cells": stem_cov_total,
                "coverage_exact_ratio": (stem_cov_exact / stem_cov_total) if stem_cov_total else 0.0,
                "coverage_mae": (sum(stem_cov_mae_vals)/len(stem_cov_mae_vals)) if stem_cov_mae_vals else 0.0,
            })
            report[extractor]["per_stem"][stem] = stem_metrics
        prec_overall = owners_tp / (owners_tp + owners_fp) if owners_tp + owners_fp else 0.0
        rec_overall = owners_tp / (owners_tp + owners_fn) if owners_tp + owners_fn else 0.0
        f1_overall = 2*prec_overall*rec_overall/(prec_overall+rec_overall) if prec_overall+rec_overall else 0.0
        cov_mae = sum(cov_diffs)/len(cov_diffs) if cov_diffs else 0.0
        cov_rmse = math.sqrt(sum(d*d for d in cov_diffs)/len(cov_diffs)) if cov_diffs else 0.0
        report[extractor]["aggregate"] = {
            "stems_evaluated": len(report[extractor]["per_stem"]),
            "kaek_exact": kaek_correct,
            "kaek_exact_ratio": kaek_correct / len(report[extractor]["per_stem"]) if report[extractor]["per_stem"] else 0.0,
            "owners_tp": owners_tp,
            "owners_fp": owners_fp,
            "owners_fn": owners_fn,
            "owners_precision": prec_overall,
            "owners_recall": rec_overall,
            "owners_f1": f1_overall,
            "coverage_exact_cells": cov_exact,
            "coverage_total_cells": cov_total,
            "coverage_exact_ratio": cov_exact / cov_total if cov_total else 0.0,
            "coverage_mae": cov_mae,
            "coverage_rmse": cov_rmse,
        }
    return report

def main():
    ap = argparse.ArgumentParser(description="Evaluate structured JSONs against manual benchmark CSV")
    ap.add_argument("--benchmark-csv", type=Path, required=True)
    ap.add_argument("--structured-dir", type=Path, default=Path("debug/structured_json"))
    ap.add_argument("--out", type=Path, default=Path("debug/benchmark_report.json"))
    ap.add_argument("--stems", nargs="*", help="Optional subset of stems to evaluate")
    args = ap.parse_args()

    gt_rows = load_ground_truth(args.benchmark_csv)
    stems = args.stems if args.stems else sorted(gt_rows.keys())
    report = evaluate(stems, gt_rows, args.structured_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote benchmark report to {args.out}")

if __name__ == "__main__":  # pragma: no cover
    main()
