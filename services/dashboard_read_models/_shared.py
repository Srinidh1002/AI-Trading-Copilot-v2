from __future__ import annotations

import math
from datetime import datetime
from typing import Any


def text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def number(value: object, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def optional_number(value: object, name: str) -> float | None:
    if value is None:
        return None
    return number(value, name)


def exact_tuple(value: object, name: str) -> tuple:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")
    return value


def diagnostics(value: object, name: str) -> tuple[str, ...]:
    items = exact_tuple(value, name)
    result: list[str] = []
    for item in items:
        item = text(item, name)
        if item not in result:
            result.append(item)
    return tuple(result)


def paper_only(execution_mode: object, live_execution_eligible: object) -> None:
    if execution_mode != "PAPER":
        raise ValueError("execution_mode must be PAPER")
    if live_execution_eligible is not False:
        raise ValueError("live_execution_eligible must be false")


def plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, tuple):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(value[key]) for key in sorted(value)}
    return value
