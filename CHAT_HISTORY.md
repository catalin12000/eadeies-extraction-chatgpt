# Project Chat Summary (portable)

Scope: Extract fields (ΚΑΕΚ, Owners, Coverage 4×7) from permit PDFs using docling; benchmark & QA; scale to large monthly runs.

Key decisions:
- Standardized on docling for structured parsing (pdfplumber only used in earlier comparisons).
- KAEK: post-process to reconstruct '/0/0' when fragmented; leading-zero tolerance only at evaluation.
- Owners: parse markdown-like tables; normalize for accents/transliteration; order-insensitive when comparing.
- Coverage: label-first parsing; recover parking when label split via orphan numeric row after "Αριθμός Ορόφων"; final text fallback for ΣΥΝΟΛΟ.
- EU numbers: tolerant parser (comma decimal; thousand dots heuristics).
- QA artifacts: structured JSONs, per-run manifest, CSV in GT-like schema, optional Excel/HTML for review.

Ops tooling:
- tools/run_month.py: parallel, resumable runner with tqdm progress; writes structured_json/, manifest.csv, GT-like CSV.
- tools/init_project.py: create baseline dirs and install dependencies.
- tools/cleanup_unused.py: optional removal of legacy folders (dry-run by default).

Recent (2025-09-02):
- Fixed `requirements.txt` to `openpyxl>=3.1.5,<4` to satisfy docling.
- Verified month runner with resume mode; CSV emitted to debug/runs/MM.

How to run (quick):
1) python3 tools/init_project.py
2) Put PDFs under data/2025/MM
3) python3 tools/run_month.py --input-dir data/2025/MM --out-root debug/runs --workers 8 --resume

Outputs:
- debug/runs/MM/structured_json/*.json
- debug/runs/MM/manifest.csv
- debug/runs/MM/run_MM_<timestamp>.csv (GT-like)

Benchmarks (historic):
- Coverage exact ≈ 99.5% vs original GT; 100% vs corrected GT; KAEK 1.0; Owners F1 ≈ 0.934 (docling).
