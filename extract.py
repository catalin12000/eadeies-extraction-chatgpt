from __future__ import annotations

import argparse
from pathlib import Path
import json
from text_loader import get_text
from core_.pipeline.enriching_pipeline import EnrichingPipeline


def main():
    parser = argparse.ArgumentParser(description="Extract permit features from one PDF")
    parser.add_argument("--pdf", required=True, type=Path, help="Path to PDF file")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    text = get_text(args.pdf)
    pipeline = EnrichingPipeline()
    preds = pipeline.extract_features(text)

    output = {
        f: {"value": p.predicted_value, "method": p.method, "cost": p.cost}
        for f, p in preds.items()
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
