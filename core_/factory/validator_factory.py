from typing import Any, Callable, Optional, List


def create_validator(
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    value_type: type = str,
    allowed_values: Optional[List[Any]] = None,
) -> Callable[[Any], Any]:
    def validator(value: Any) -> Any:
        if value is None:
            return None
        try:
            typed = value_type(value)
        except Exception:
            return None
        if allowed_values is not None and typed not in allowed_values:
            return None
        if min_value is not None and isinstance(typed, (int, float)) and typed < min_value:
            return None
        if max_value is not None and isinstance(typed, (int, float)) and typed > max_value:
            return None
        return typed
    return validator
