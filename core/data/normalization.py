"""외부 데이터와 계산 결과를 JSON/DB에 안전한 값으로 정규화한다."""
from __future__ import annotations

import math
import numbers


def normalize_finite_numbers(value):
    if isinstance(value, dict):
        return {key: normalize_finite_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_finite_numbers(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_finite_numbers(item) for item in value)
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        return value if math.isfinite(float(value)) else None
    return value
