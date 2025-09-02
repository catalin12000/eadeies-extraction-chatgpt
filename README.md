# EADEIES Extraction & Benchmarking Toolkit

Pipeline for extracting PDF permits with `docling`, normalizing structured data (KAEK, Owners, Coverage metrics), and benchmarking against a curated ground-truth CSV with JSON + Excel reporting.

See also: documentation of field-by-field parsing in `EXTRACTION_LOGIC.md`.

## 1. Features Overview
* Raw text comparison script retained (timings, similarity, basic text stats)
* Robust KAEK extraction with tolerance for fragmented `/0/0` suffix & leading-zero equivalence
* Owner table parsing (heuristics for raw text + markdown tables) with aggressive normalization (accents, punctuation, corporate tokens)
* Coverage diagram parsing (4 groups × 7 metrics = 28 cells) with EU number parsing (commas, thousands dots, negatives)
* Evaluation metrics: KAEK exact ratio, Owners precision/recall/F1, Coverage exact cell ratio + MAE/RMSE
* Excel workbook (multi-sheet) with boolean match flags and mismatch-only sheet

## 2. Repository Structure (Key Files)
| Path | Purpose |
|------|---------|
| `compare_pdf_extractors.py` | Raw text extraction + per-file / aggregate text metrics (docling primary; pdfplumber optional). |
| `build_structured_json.py` | Parse raw text to canonical JSON (docling-only). |
| `benchmark_evaluation.py` | Compute accuracy metrics vs ground-truth CSV. |
| `build_excel_comparison.py` | Generate multi-sheet Excel for manual QA. |
| `tools/debug_side_by_side.py` | Generate per-stem PDF vs extracted-text debug pages with diffs. |
| `data/01_benchmark/eadeies_final.csv` | Ground truth (KAEK, owners, coverage). |
| `debug/compare/` | Generated raw text & pairwise comparison JSON. (Git-ignored) |
| `debug/structured_json/` | Structured JSON outputs. (Git-ignored) |
| `debug/benchmark_side_by_side.xlsx` | Excel comparison report. |
| `documentation/Extraction_Workflow.md` | Mermaid diagram of full extraction + evaluation workflow. |
| `documentation/workflow.html` | Browser-rendered interactive workflow diagram (Mermaid). |

## 3. Installation
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install --upgrade pip
pip install -r requirements.txt
# (Optional) Alternatively, run the helper initializer:
# python tools/init_project.py
```

## 4. End-to-End Workflow
1. (Optional) Gather PDFs under `data/` (subdirectories allowed). Ground-truth CSV already present.
2. (Optional) Extract raw text & comparison metrics:
	 ```bash
	 python compare_pdf_extractors.py --root data --output-dir debug/compare --save-text --sample-lines 0
	 ```
	 Outputs: `*_pdfplumber.txt`, `*_docling.txt`, and `<stem>_compare.json` plus `_aggregate_summary.json`.
3. Build structured JSON for all stems (docling-only):
	 ```bash
	 python build_structured_json.py --all --compare-dir debug/compare --out-dir debug/structured_json
	 ```
4. Run quantitative benchmark:
	 ```bash
	 python benchmark_evaluation.py \
		 --benchmark-csv data/01_benchmark/eadeies_final.csv \
		 --structured-dir debug/structured_json \
		 --out debug/benchmark_report.json
	 ```
5. Create Excel comparison workbook:
	 ```bash
	 python build_excel_comparison.py \
		 --benchmark-csv data/01_benchmark/eadeies_final.csv \
		 --structured-dir debug/structured_json \
		 --out debug/benchmark_side_by_side.xlsx
	 ```
6. Inspect:
	 * `benchmark_report.json` for aggregate/per-stem metrics.
	 * Excel sheets (see section 6) for visual QA.

### 4.1 Parser-only quick paths
- Build structured for a single PDF:
	```bash
	python build_structured_json.py --pdf data/Mike/<stem>.pdf --extractors docling --out-dir debug/structured_json
	```
- Build from pre-extracted texts but only one engine:
	```bash
	python build_structured_json.py --stem <stem> --extractors docling --compare-dir debug/compare --out-dir debug/structured_json
	```
- Visual one-pager for selected stems and engines:
	```bash
	python build_eye_dashboard.py \
		--benchmark-csv data/01_benchmark/eadeies_final.csv \
		--structured-dir debug/structured_json \
		--extractors docling \
		--stems <stem1> <stem2> \
		--out debug/eye_dashboard_selected.html
	```

### 4.2 Programmatic API
You can call the parser as a function to get structured data from a single PDF without touching disk:
```python
from pathlib import Path
from build_structured_json import extract_pdf_to_structured

data = extract_pdf_to_structured(Path("data/Mike/<stem>.pdf"), extractor="docling")
print(data["ΚΑΕΚ"], len(data["Στοιχεία κυρίου του έργου"]))
```

### 4.3 Monthly batch runner (recommended)
Run the parallel, resumable month runner that writes per-file JSON, a manifest, and a GT-like CSV:
```bash
python tools/run_month.py \
	--input-dir data/2025/02 \
	--out-root debug/runs \
	--workers 8 \
	--resume \
	--yes
```
Outputs under `debug/runs/<MM>/`:
- `structured_json/*.json` (one per PDF)
- `manifest.csv` (file list with status)
- `run_<MM>_<timestamp>.csv` (wide, GT-like CSV)

Resume behavior: if `--resume` is set, existing JSONs in the same run folder are skipped.

## 5. Structured JSON Schema
Each `<stem>_<extractor>_structured.json`:
```json
{
	"ΑΔΑ": "<stem>",
	"ΚΑΕΚ": "<kaek>",
	"Στοιχεία κυρίου του έργου": [
		{"Επώνυμο/ία": "...", "Όνομα": "...", "Ιδιότητα": "...", "Ποσοστό": 50.0, "Τύπος δικαιώματος": "Πλήρης κυριότητα" }
	],
	"Στοιχεία Διαγράμματος Κάλυψης": {
		"ΥΦΙΣΤΑΜΕΝΑ": { "Εμβ. κάλυψης κτιρίου": 123.45, ... },
		"ΝΟΜΙΜΟΠΟΙΟΥΜΕΝΑ": { ... },
		"ΠΡΑΓΜΑΤΟΠΟΙΟΥΜΕΝΑ": { ... },
		"ΣΥΝΟΛΟ": { ... }
	}
}
```

## 6. Excel Workbook Sheets
| Sheet | Content |
|-------|---------|
| `KAEK` | Ground truth & prediction + match flags (1/0). |
| `Owners` | Row-aligned GT vs predicted surnames/names with per-slot normalized match flags. |
| `Coverage` | One row per (ΑΔΑ, Group, Metric) with GT, prediction, boolean matches, and diffs. |
| `CoverageWide` | Wide format: one row per ΑΔΑ, columns for all coverage metrics (prefers docling). |
| `CoverageMismatches` | Only rows where prediction differs (any extractor). |

## 7. Evaluation Logic Highlights
* KAEK equivalence allows a single dropped leading zero (Excel formatting issue) but otherwise exact.
* Owner comparison uses normalized `(surname, name)` sets (accent & punctuation stripped, corporate tokens removed) – order ignored in metrics, order shown in Excel.
* Coverage: 28 numeric cells. Exact match threshold `abs(pred-gt) < 1e-6`. MAE / RMSE computed over absolute differences for matched numeric cells.
* Number parsing handles EU formatting, thousands separators, and negatives.

## 8. Typical Questions / Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| Missing docling results | Package not installed / pydantic v1 conflict | `pip install docling` and ensure pydantic v2 (see requirements.txt). |
| IDE crash on run (macOS) | Multiprocessing with default 'fork' and ML libs (PyTorch) can crash IDEs | We force `spawn` in `tools/run_month.py`. Ensure you run with `python3 tools/run_month.py ...`. If crash persists, run in terminal, not the IDE debug console. |
| KAEK mismatch w/ leading zero | Excel stripped leading zero | Handled automatically in equivalence; check raw JSON if persistent. |
| Coverage mismatch large factor (e.g., 1834 vs 1.834) | Thousands vs decimal ambiguity | Refine `parse_eu_number` heuristic (see code comments). |
| Negative values lost | Regex missed '-' | Ensure patterns include `-?` (already handled in docling parser). |
| Owners mis-splitting due to layout | Text layout/line wrapping heuristic limits | Adjust owners table heuristics (header detection, row stitching). |

## 9. Extending / Improving
* Add heuristic: treat pattern `^\d\.\d{3}$` as decimal if expected metric logically < 100.
* Persist intermediate diagnostics (e.g. coverage parse candidates) for debugging.
* Add CLI flag to `build_structured_json.py` to only rebuild missing outputs.
* Add unit tests for number parsing and KAEK post-processing.

## 10. Quick Metrics Recap (Current)
See `debug/benchmark_report.json` for exact values.

## 11. Re-running From Scratch
```bash
rm -rf debug/compare debug/structured_json
python compare_pdf_extractors.py --root data --output-dir debug/compare --save-text --sample-lines 0
python build_structured_json.py --all --compare-dir debug/compare --out-dir debug/structured_json
python benchmark_evaluation.py --benchmark-csv data/01_benchmark/eadeies_final.csv --structured-dir debug/structured_json --out debug/benchmark_report.json
python build_excel_comparison.py --benchmark-csv data/01_benchmark/eadeies_final.csv --structured-dir debug/structured_json --out debug/benchmark_side_by_side.xlsx
```

## 12. License
Add a LICENSE file if this will be shared externally.

## 13. Contribution Notes
* Keep parsing changes minimal & tested (add a few stems to a local test harness).
* Avoid destructive KAEK normalization; use tolerant comparison only.
* When adding coverage metrics, update: `COVERAGE_KEYS`, all parsers, evaluation, and Excel builder.

---
Feel free to adapt/extend. Open an issue or PR for enhancements.

See also: `CHAT_HISTORY.md` for a concise log of design decisions and operational tips.

For day-to-day collaboration across devices, use `WORKLOG.md` as a simple, commit-backed chat/notes thread.
