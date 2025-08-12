import re
from typing import List, Callable, Dict, Optional, Any
from core_.base.datatypes import FeaturePrediction


def create_pattern_finder(
    patterns: List[str],
    feature_name: str,
    validator: Callable[[Any], Any],
    is_binary: bool = False,
    value_converter: Callable[[str], Any] = str,
    european_format: bool = False,
    fixed_matches: Optional[Dict[str, int]] = None,
) -> Callable[[str], FeaturePrediction]:
    def pattern_finder(text: str) -> FeaturePrediction:
        lowered = text.lower()

        if fixed_matches:
            for pattern, fixed_value in fixed_matches.items():
                if re.search(pattern, lowered):
                    val = validator(fixed_value)
                    if val is not None:
                        return FeaturePrediction(
                            feature_name=feature_name,
                            predicted_value=val,
                            method="strict_regex",
                            cost=0.0,
                        )

        if is_binary:
            for pattern in patterns:
                if re.search(pattern, lowered):
                    val = validator(1)
                    if val is not None:
                        return FeaturePrediction(
                            feature_name=feature_name,
                            predicted_value=val,
                            method="strict_regex",
                            cost=0.0,
                        )
            val = validator(0)
            return FeaturePrediction(
                feature_name=feature_name,
                predicted_value=val,
                method="strict_regex",
                cost=0.0,
            )

        for pattern in patterns:
            m = re.search(pattern, lowered, re.MULTILINE)
            if m:
                grp = m.group(1) if m.groups() else m.group(0)
                raw = grp.strip()
                if european_format:
                    raw = raw.replace(".", "").replace(",", ".")
                try:
                    converted = value_converter(raw)
                except Exception:
                    converted = raw
                val = validator(converted)
                if val is not None:
                    return FeaturePrediction(
                        feature_name=feature_name,
                        predicted_value=val,
                        method="strict_regex",
                        cost=0.0,
                    )

        return FeaturePrediction(
            feature_name=feature_name,
            predicted_value=None,
            method="strict_regex",
            cost=0.0,
        )

    return pattern_finder
