from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

COMPARE_DIR = Path("debug/compare")

COVERAGE_KEYS = [
    "Εμβ. κάλυψης κτιρίου",
    "Εμβ. δόμησης κτιρίου",
    "Εμβ. ακάλυπτου χώρου οικοπέδου",
    "Όγκος κτιρίου (άνω εδάφους)",
    "Μέγιστο ύψος κτιρίου",
    "Αριθμός Ορόφων",
    "Αριθμός Θέσεων Στάθμευσης",
]

EU_NUM_RE = re.compile(r"^-?[0-9][0-9\.]*,[0-9]+$|^-?[0-9][0-9\.]*$")

def parse_eu_number(s: str) -> Optional[float]:
    raw = s
    s = s.strip().replace(" ", "")
    if not s or s in {"-", "--"}:
        return None
    sign = -1 if s.startswith('-') else 1
    s_body = s[1:] if s[0] in '+-' else s
    if not s_body:
        return None
    if ',' in s_body:
        int_part, dec = s_body.split(',', 1)
        int_part = int_part.replace('.', '')
        num_str = int_part + '.' + dec
    else:
        if s_body.count('.') == 0:
            num_str = s_body
        else:
            parts = s_body.split('.')
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                num_str = ''.join(parts)
            elif len(parts) == 2 and len(parts[1]) == 3:
                num_str = parts[0] + parts[1]
            elif len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                num_str = parts[0] + '.' + parts[1]
            else:
                num_str = ''.join(parts)
    try:
        return sign * float(num_str)
    except ValueError:
        return None

def load_raw(stem: str) -> Dict[str, str]:
    docling = (COMPARE_DIR / f"{stem}_docling.txt").read_text(encoding="utf-8")
    return {"docling": docling}

# pdfplumber removed; docling is the only supported engine.

def _extract_text_docling(pdf_path: Path) -> Optional[str]:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:
        return None
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    text = result.document.export_to_text() if hasattr(result.document, "export_to_text") else str(result.document)
    return (text or "").strip()

def extract_pdf_to_structured(pdf_path: Path, extractor: str) -> Dict[str, object]:
    extractor = extractor.lower().strip()
    if extractor == "docling":
        raw_text = _extract_text_docling(pdf_path)
        if raw_text is None:
            raise RuntimeError("docling not installed or failed to import")
    else:
        raise ValueError("extractor must be 'docling'")
    return build_structured(pdf_path.stem, raw_text, extractor)

def extract_kaek(text: str) -> Optional[str]:
    m = re.search(r"ΚΑΕΚ\s*[:\-]?\s*([0-9/]{6,})", text)
    if m:
        return m.group(1)
    for line in text.splitlines():
        if "ΚΑΕΚ" in line:
            m2 = re.search(r"ΚΑΕΚ[^0-9/]*([0-9/]{6,})", line)
            if m2:
                return m2.group(1)
    return None

def _post_process_kaek(raw_text: str, value: str) -> str:
    def tidy(v: str) -> str:
        v = v.replace(' /', '/').replace('/ ', '/').replace(' ', '')
        v = re.sub(r'/+', '/', v)
        return v
    original = value or ""
    if not original:
        for line in raw_text.splitlines():
            if 'ΚΑΕΚ' in line or re.search(r'[0-9]{6,}\s*/\s*0\s*/\s*0', line):
                m = re.search(r'([0-9]{6,})\s*/\s*0\s*/\s*0', line)
                if m:
                    original = m.group(1) + '/0/0'
                    break
                if 'ΚΑΕΚ' in line:
                    nums = re.findall(r'[0-9]{6,}', line)
                    if nums:
                        original = max(nums, key=len)
                        if (
                            (re.search(r'/\s*0\s*/\s*$', line) and re.search(r'ΚΑΕΚ\s*0', line))
                            or (re.search(r'/\s*0\s*/\s*\|', line) and re.search(r'ΚΑΕΚ\s*0', line))
                        ):
                            original = original + '/0/0'
                        if re.search(r'/\s*0\s*/\s*0', line) and not original.endswith('/0/0'):
                            original = original + '/0/0'
                        break
    v = original
    if not v:
        return ""
    if '/0/0' not in v:
        for line in raw_text.splitlines():
            if v[:10] in line and re.search(r'/\s*0\s*/\s*0', line):
                if re.search(re.escape(v) + r'\s*/\s*0\s*/\s*0', line) or ('ΚΑΕΚ' in line):
                    v = v + '/0/0'
                    break
    v = tidy(v)
    if '/0/0' not in v:
        base = v
        if base and '/' not in base:
            pattern = re.compile(re.escape(base) + r'.{0,40}/\s*0\s*/\s*0')
            pattern_rev = re.compile(r'/\s*0\s*/\s*0.{0,40}' + re.escape(base))
            for line in raw_text.splitlines():
                if pattern.search(line) or pattern_rev.search(line):
                    v = base + '/0/0'
                    break
    return v

# pdfplumber owners parsing removed

def extract_docling_tables(text: str):
    tables = []
    cur = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cur.append(line)
        else:
            if cur:
                tables.append(cur)
                cur = []
    if cur:
        tables.append(cur)
    return tables

def parse_markdown_table(lines: List[str]):
    rows = []
    for l in lines:
        l = l.rstrip()
        if not l.strip().startswith("|"):
            continue
        parts = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r"-+", p) for p in parts):
            continue
        rows.append(parts)
    return rows

def parse_docling_owners(text: str):
    owners: List[Dict[str, object]] = []
    for tbl_lines in extract_docling_tables(text):
        tbl = parse_markdown_table(tbl_lines)
        if not tbl or len(tbl) < 2:
            continue
        header_row_index = None
        for idx, row in enumerate(tbl[:3]):
            lowered = [c.lower() for c in row]
            if "επώνυμο/ία" in lowered and "ποσοστό" in lowered:
                header_row_index = idx
                header = lowered
                break
        if header_row_index is None:
            continue
        data_rows = tbl[header_row_index + 1 :]
        for row in data_rows:
            if len(row) < len(header):
                continue
            m = dict(zip(header, row))
            if not m.get("επώνυμο/ία", "").strip() and not m.get("ιδιότητα", "").strip():
                continue
            raw_share = str(m.get("ποσοστό", "")).strip()
            try:
                share_v = float(raw_share.replace(",", ".")) if raw_share else 0.0
            except ValueError:
                share_v = 0.0
            owners.append(
                {
                    "Επώνυμο/ία": m.get("επώνυμο/ία", "").strip(),
                    "Όνομα": m.get("όνομα", "").strip(),
                    "Ιδιότητα": m.get("ιδιότητα", "").strip(),
                    "Ποσοστό": share_v,
                    "Τύπος δικαιώματος": m.get("τύπος δικαιώματος", "").strip(),
                }
            )
    return owners

# pdfplumber coverage parsing removed

def parse_docling_coverage(text: str):
    cov = {}
    for tbl_lines in extract_docling_tables(text):
        tbl = parse_markdown_table(tbl_lines)
        if not tbl:
            continue
        for i,row in enumerate(tbl):
            if len(row) == 5 and row[0] in COVERAGE_KEYS:
                if i == 0 and any(label in row[1] for label in ["ΥΦΙΣΤΑ", "ΝΟΜΙΜ", "ΠΡΑΓΜ", "ΣΥΝΟΛ"]):
                    continue
                cov[row[0]] = [parse_eu_number(c) for c in row[1:5]]
    return cov

def orient_coverage(cov_map: Dict[str, List[Optional[float]]]):
    cols = ["ΥΦΙΣΤΑΜΕΝΑ","ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ","ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ","ΣΥΝΟΛΟ"]
    result = {c:{} for c in cols}
    for key in COVERAGE_KEYS:
        vals = cov_map.get(key, [None,None,None,None])
        for idx,c in enumerate(cols):
            v = vals[idx]
            result[c][key] = v if v is not None else 0.0
    return result

def build_structured(stem: str, raw_text: str, extractor: str):
    kaek = extract_kaek(raw_text) or ""
    if not kaek and '|' in raw_text:
        for l in raw_text.splitlines():
            if 'ΚΑΕΚ' not in l:
                continue
            if not l.strip().startswith('|'):
                continue
            cells = [c.strip() for c in l.strip().strip('|').split('|')]
            if not cells:
                continue
            for idx, c in enumerate(cells):
                if c == 'ΚΑΕΚ':
                    if idx + 1 < len(cells):
                        next_cell = cells[idx+1].strip()
                        cand = next_cell.split()[0] if next_cell else ''
                        cand_clean = cand.replace(' ', '')
                        if re.fullmatch(r'[0-9/]{6,}', cand_clean):
                            kaek = cand_clean
                            break
            if kaek:
                break
            for idx, c in enumerate(cells):
                if re.fullmatch(r'[0-9/]{6,}', c.replace(' ', '')) and any(cc == 'ΚΑΕΚ' for cc in cells[idx+1:]):
                    kaek = c.replace(' ', '')
                    break
            if kaek:
                break
    kaek = _post_process_kaek(raw_text, kaek)
    owners = parse_docling_owners(raw_text)
    cov = parse_docling_coverage(raw_text)
    structured = {
        "ΑΔΑ": stem,
        "ΚΑΕΚ": kaek,
        "Στοιχεία κυρίου του έργου": owners,
        "Στοιχεία Διαγράμματος Κάλυψης": orient_coverage(cov),
    }
    return structured

def main():
    ap = argparse.ArgumentParser(description="Build structured JSON for permit PDFs from extracted text")
    ap.add_argument("--stem", help="Filename stem (without .pdf)")
    ap.add_argument("--pdf", type=Path, help="Path to PDF to infer stem", required=False)
    ap.add_argument("--compare-dir", type=Path, default=COMPARE_DIR, help="Directory holding *_docling.txt")
    ap.add_argument("--out-dir", type=Path, default=Path("debug/structured_json"), help="Output directory for structured JSON")
    ap.add_argument("--extractors", nargs="*", default=["docling"], help="Engines to run: docling")
    ap.add_argument("--all", action="store_true", help="Process all stems present in compare-dir")
    ap.add_argument("--limit", type=int, default=0, help="Optional limit when using --all (0 = no limit)")
    args = ap.parse_args()
    selected_extractors = [e.lower() for e in args.extractors]
    valid = {"docling"}
    for e in selected_extractors:
        if e not in valid:
            ap.error("--extractors must be subset of: docling")

    if args.all:
        if args.stem or args.pdf:
            ap.error("Don't combine --all with --stem/--pdf")
        if not args.compare_dir.exists():
            raise SystemExit(f"Compare dir not found: {args.compare_dir}")
        stems = sorted({p.name.rsplit('_docling.txt',1)[0] for p in args.compare_dir.glob('*_docling.txt')})
        if args.limit > 0:
            stems = stems[: args.limit]
        args.out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for stem in stems:
            try:
                raws = load_raw(stem)
            except FileNotFoundError:
                print(f"Skipping {stem}: missing text files")
                continue
            for extractor, text in raws.items():
                if extractor not in selected_extractors:
                    continue
                data = build_structured(stem, text, extractor)
                path = args.out_dir / f"{stem}_{extractor}_structured.json"
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            count += 1
            if count % 10 == 0:
                print(f"Processed {count} stems...")
        print(f"Done. Structured JSON created for {count} stems in {args.out_dir}")
        return

    if not args.stem and not args.pdf:
        ap.error("Provide --stem/--pdf or use --all")

    stem = args.stem or args.pdf.stem  # type: ignore
    if args.pdf:
        raws: Dict[str, str] = {}
        if "docling" in selected_extractors:
            txt = _extract_text_docling(args.pdf)
            if txt is None:
                print("docling not available; skipping docling engine")
            else:
                raws["docling"] = txt
        if not raws:
            raise SystemExit("No text extracted; ensure selected engines are available")
    else:
        raws = load_raw(stem)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for extractor, text in raws.items():
        if extractor not in selected_extractors:
            continue
        data = build_structured(stem, text, extractor)
        path = out_dir / f"{stem}_{extractor}_structured.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {path}")

if __name__ == "__main__":
    main()
