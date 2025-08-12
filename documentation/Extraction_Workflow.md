# Extraction & Evaluation Workflow Diagram

Below is a Mermaid diagram capturing the end-to-end pipeline from raw PDF to final artifacts (structured JSON, metrics JSON, Excel report).

```mermaid
graph TD
    A[PDF Files under data/] --> B{Extraction Engines}
    B --> B1[pdfplumber\n(raw text)]
    B --> B2[docling\n(raw text)]
    B1 --> C[compare_pdf_extractors.py\n(save *_pdfplumber.txt)]
    B2 --> C[compare_pdf_extractors.py\n(save *_docling.txt)]
    C --> D[debug/compare/\n_raw texts_]
    C --> E[_aggregate_summary.json]

    D --> F[build_structured_json.py\n(parse KAEK, Owners, Coverage)]
    F --> G1[<stem>_pdfplumber_structured.json]
    F --> G2[<stem>_docling_structured.json]
    G1 --> H[Structured JSON Dir]
    G2 --> H[Structured JSON Dir]

    H --> I[benchmark_evaluation.py\n(compare vs CSV ground truth)]
    dataCSV[data/01_benchmark/eadeies_final.csv] --> I
    I --> J[benchmark_report.json\n(per-stem + aggregate)]

    H --> K[build_excel_comparison.py]
    dataCSV --> K
    K --> L[benchmark_side_by_side.xlsx\n(KAEK, Owners, Coverage, Mismatches)]

    J --> M[Insights / Iteration]
    L --> M
    M --> F[Heuristic Refinement]
```

## Legend
- Rounded rectangles: artifacts/files.
- Diamonds: branching / parallel extraction.
- Arrows show primary data flow.
- Feedback loop from insights leads to parser refinement.

## High-Level Stages
1. Raw text extraction (dual engine)
2. Structured parsing (normalize domain entities)
3. Benchmark evaluation (quant metrics)
4. Reporting (Excel + JSON)
5. Iterative refinement (heuristics & tests)

---
For detailed parsing logic see `EXTRACTION_LOGIC.md`.
