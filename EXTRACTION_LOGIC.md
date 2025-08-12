# Extraction & Parsing Logic Overview

This document explains how each component of the pipeline derives structured data from raw PDF permits for both `pdfplumber` and `docling` extractors.

## 1. Raw Text Acquisition
- `compare_pdf_extractors.py` loads each PDF with:
  - `pdfplumber`: concatenates page texts, normalizes hyphenated line breaks, collapses whitespace.
  - `docling` (optional): converts to an internal document model and exports plain text.
- Outputs (when `--save-text`): `debug/compare/<stem>_pdfplumber.txt` & `<stem>_docling.txt`.

## 2. KAEK Extraction
Goal: robustly identify the cadastral code `ΚΑΕΚ` which may appear in plain text or table form, sometimes fragmented.

Steps:
1. Regex scan: `ΚΑΕΚ\s*[:\-]?\s*([0-9/]{6,})` to capture adjacent numeric/slash sequence.
2. Line-wise fallback: if line contains `ΚΑΕΚ`, search for the first numeric block of length ≥6 after it.
3. Markdown table scan (docling output): iterate table rows; handle both orientations:
   - Normal: `| ΚΑΕΚ | 50097350003 |`
   - Reversed: `| 50097350003 | ... | ΚΑΕΚ |`
4. Post-processing `_post_process_kaek` heuristics:
   - Reconstruct missing `'/0/0'` suffix when fragmented tokens `/ 0 / 0` appear near the base number or across table cells.
   - Preserve leading zeros in stored value (no destructive trimming).
   - Global scan: append `/0/0` if the base number + fragmented pattern appears within a small textual window.
5. Equivalence (evaluation only) tolerates exactly one dropped leading zero (Excel formatting loss).

## 3. Owner Table Parsing
Owners appear as tabular data with columns like `Επώνυμο/ία`, `Όνομα`, `Ποσοστό`, etc.

### pdfplumber (`parse_pdfplumber_owners`):
- Identifies section starting at `Στοιχεία κυρίου του έργου` and ending before either `Πρόσθετες` or `Στοιχεία Διαγράμματος`.
- Collects non-empty lines, stitches wrapped lines (e.g., `Πλήρης` + `κυριότητα`).
- Token-based row parsing: finds a token that parses as a numeric percentage (0–100) to delimit share vs right.
- Emits list of dicts with keys: surname, name, percentage, inferred right (`Τύπος δικαιώματος`).

### docling (`parse_docling_owners`):
- Detects markdown tables (lines starting with `|`).
- Parses rows, skipping delimiter lines of dashes.
- Locates header row within first 3 rows that contains both `επώνυμο/ία` & `ποσοστό`.
- Normalizes and casts share value; returns owner records from subsequent rows.

### Normalization (for evaluation):
`normalize_owner_component`:
- Unicode accent stripping (NFD), punctuation removal, uppercase, corporate token filtering (ΑΕ, ΕΠΕ, ΙΚΕ, LLC, etc.), slash collapse.
- Produces comparable `(surname, name)` pairs used to compute precision/recall/F1 as *sets* (order-insensitive).

## 4. Coverage Diagram Parsing
Coverage metrics (7 per group) across 4 groups: `ΥΦΙΣΤΑΜΕΝΑ`, `ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ`, `ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ`, `ΣΥΝΟΛΟ`.

Metrics:
1. Εμβ. κάλυψης κτιρίου
2. Εμβ. δόμησης κτιρίου
3. Εμβ. ακάλυπτου χώρου οικοπέδου
4. Όγκος κτιρίου (άνω εδάφους)
5. Μέγιστο ύψος κτιρίου
6. Αριθμός Ορόφων
7. Αριθμός Θέσεων Στάθμευσης

### pdfplumber (`parse_pdfplumber_coverage`):
- After locating `Στοιχεία Διαγράμματος Κάλυψης`, scans each subsequent line.
- For each metric key prefix, captures up to 4 numeric patterns `-?[0-9][0-9\.,]*` (group values in canonical order).
- Passes each token through `parse_eu_number`.

### docling (`parse_docling_coverage`):
- Iterates markdown tables; any row with first cell matching a coverage key and exactly 5 columns (`[key, col1, col2, col3, col4]`) becomes a data row.
- Skips header-like rows if the second cell contains group labels instead of numbers.

### Orientation (`orient_coverage`):
- Builds nested dict: `{ group: { metric: value } }` mapping columns (ΥΦΙΣΤΑΜΕΝΑ, ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ, ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ, ΣΥΝΟΛΟ).
- Missing or `None` values filled with `0.0` for consistency.

### Number Parsing (`parse_eu_number`):
Heuristics to disambiguate European formatted numbers:
- Comma present: comma => decimal separator; dots stripped as thousands.
- No comma:
  * If all dot-separated groups after the first are length 3 -> treat dots as thousands (e.g. `1.234.567`).
  * Single dot + 3 trailing digits -> thousands (`1.234` => 1234).
  * Single dot + 1–2 trailing digits -> decimal (`7.5`, `12.34`).
  * Fallback: strip all dots.
- Supports leading minus for negative adjustments / demolition metrics.

## 5. Evaluation Metrics (`benchmark_evaluation.py`)
- KAEK: exact or one-leading-zero tolerance.
- Owners: set-based TP/FP/FN across normalized `(surname, name)` pairs.
- Coverage: 28 cells enumerated; exact cell if numeric difference < 1e-6. MAE/RMSE over absolute diffs (non-matching or matching cells alike once numeric parsed).

## 6. Excel Reporting (`build_excel_comparison.py`)
- Adds boolean match columns for KAEK, Owners (per index), and Coverage cells.
- `CoverageMismatches` sheet isolates only differing cells for rapid triage.
- `CoverageWide` gives a consolidated per-stem row (prefers docling values if present, else pdfplumber).

## 7. Error & Edge Case Handling
| Scenario | Handling |
|----------|----------|
| Missing docling install | Mark extraction result with error; continue benchmark. |
| Fragmented `/ 0 / 0` KAEK suffix | Reconstructed in `_post_process_kaek`. |
| Leading zero dropped in GT | Tolerated in `equivalent_kaek`. |
| Ambiguous thousands vs decimal | Heuristics; potential refinement to treat pattern `^\d\.\d{3}$` as decimal if domain constraints justify. |
| Negative coverage values lost | Regex includes optional `-`; extend similarly for docling if needed. |

## 8. Potential Refinements
- Context-aware magnitude checks (e.g., building volume rarely < 10, so `1.834` might be decimal while area metrics rarely use 4-digit decimals).
- Per-metric tolerance bands to flag "close" vs incorrect.
- Additional owner parsing smoothing (join lines split mid-name).
- Persist raw matched lines alongside structured values for audit traceability.

## 9. Data Flow Summary
```
PDF -> (pdfplumber/docling) raw text -> structured JSON (KAEK, Owners, Coverage) -> benchmark evaluation -> JSON metrics + Excel workbook
```

## 10. Glossary
- **ΚΑΕΚ**: Greek cadastral identifier.
- **ΥΦΙΣΤΑΜΕΝΑ**: Existing state.
- **ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ**: Legalizing components.
- **ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ**: Realized / resulting.
- **ΣΥΝΟΛΟ**: Total.

---
For implementation specifics, reference the functions cited above within `build_structured_json.py` and `benchmark_evaluation.py`.
