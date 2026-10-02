"""One state per feature family, independent of how many indicators it emits."""

from __future__ import annotations

from services.x3.contracts_v1 import FAMILIES, X3FamilyResultV1, X3FeatureV1


def reduce_family_v1(family: str, features: tuple[X3FeatureV1, ...]) -> X3FamilyResultV1:
    if family not in FAMILIES or any(f.family != family for f in features):
        raise ValueError("family and feature mismatch")
    present = tuple(sorted(f.feature_id for f in features if f.status == "VALID"))
    missing = tuple(sorted(f.feature_id for f in features if f.status != "VALID"))
    dirs = {f.direction for f in features if f.status == "VALID"}
    if not present:
        state = "MISSING"
    elif "CONFLICT" in dirs or {"BULLISH", "BEARISH"} <= dirs:
        state = "CONFLICT"
    elif "BULLISH" in dirs:
        state = "BULLISH"
    elif "BEARISH" in dirs:
        state = "BEARISH"
    elif "UNKNOWN" in dirs:
        state = "UNKNOWN"
    else:
        state = "NON_DIRECTIONAL"
    return X3FamilyResultV1(
        family=family,
        state=state,
        member_ids=present,
        missing_ids=missing,
        shared_dependencies=tuple(sorted({dep for f in features for dep in f.dependency_ids})),
    )


def reduce_all_families_v1(features: tuple[X3FeatureV1, ...]) -> tuple[X3FamilyResultV1, ...]:
    return tuple(reduce_family_v1(f, tuple(x for x in features if x.family == f)) for f in FAMILIES)
