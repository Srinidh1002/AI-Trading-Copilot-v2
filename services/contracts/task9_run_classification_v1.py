"""Immutable Task 9 root purpose; diagnostic roots never become official."""
from __future__ import annotations
OFFICIAL_CERTIFICATION = "OFFICIAL_CERTIFICATION"
DIAGNOSTIC_NON_COUNTING = "DIAGNOSTIC_NON_COUNTING"
RUN_CLASSIFICATIONS = frozenset({OFFICIAL_CERTIFICATION, DIAGNOSTIC_NON_COUNTING})
def validate_task9_run_classification(value: object) -> str:
    if type(value) is not str or value.strip().upper() not in RUN_CLASSIFICATIONS: raise ValueError("run_classification")
    return value.strip().upper()
