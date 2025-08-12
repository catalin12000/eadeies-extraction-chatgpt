from core_.base.datatypes import FeatureConfig, Feature
from core_.factory.validator_factory import create_validator
from core_.factory.pattern_factory import create_pattern_finder


def create_feature(config: FeatureConfig) -> Feature:
    validator = create_validator(
        min_value=config.min_value,
        max_value=config.max_value,
        value_type=config.value_type,
        allowed_values=config.allowed_values,
    )
    pattern_finder = create_pattern_finder(
        patterns=config.patterns,
        feature_name=config.name,
        validator=validator,
        is_binary=config.is_binary,
        value_converter=config.value_type,
        european_format=config.european_format,
        fixed_matches=config.fixed_matches,
    )
    return Feature(
        name=config.name,
        column_name=config.column_name,
        prompt=config.prompt,
        strict_prediction=pattern_finder,
        validate_func=validator,
    )
