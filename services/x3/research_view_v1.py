"""Read-only X2/X3 evidence envelope; *not* a combined trading score."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from services.x3.contracts_v1 import X3MultiTimeframeResultV1


@dataclass(frozen=True, slots=True)
class X23ResearchViewV1:
    market: str
    x2_evidence_hashes: tuple[tuple[str, str], ...]
    x3_result_sha256: str
    x2_available: bool
    x3_available: bool
    schema_version: str = "X23_RESEARCH_VIEW_V1"
    data_only: bool = True
    live_execution_eligible: bool = False

    @property
    def sha256(self):
        return hashlib.sha256(
            json.dumps(
                {
                    "market": self.market,
                    "x2_evidence_hashes": self.x2_evidence_hashes,
                    "x3_result_sha256": self.x3_result_sha256,
                    "x2_available": self.x2_available,
                    "x3_available": self.x3_available,
                    "schema_version": self.schema_version,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()


def build_x23_research_view_v1(
    x3: X3MultiTimeframeResultV1, x2_inputs: Mapping[str, object] | None = None
):
    if not isinstance(x3, X3MultiTimeframeResultV1):
        raise ValueError("X3 result required")
    if x2_inputs is not None and not isinstance(x2_inputs, Mapping):
        raise ValueError("X2 mapping expected")
    hashes = []
    for key, value in sorted((x2_inputs or {}).items()):
        if not isinstance(key, str) or not key or not hasattr(value, "to_dict"):
            raise ValueError("X2 result must have a stable to_dict contract")
        payload = value.to_dict()
        if not isinstance(payload, dict) or not payload.get("schema_version"):
            raise ValueError("unversioned X2 result")
        owner = payload.get("index_symbol", payload.get("market"))
        if owner is not None and owner != x3.market:
            raise ValueError("X2/X3 market mismatch")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        hashes.append((key, hashlib.sha256(encoded.encode()).hexdigest()))
    return X23ResearchViewV1(
        market=x3.market,
        x2_evidence_hashes=tuple(hashes),
        x3_result_sha256=x3.sha256,
        x2_available=bool(hashes),
        x3_available=any(not r.blockers for r in x3.timeframe_results),
    )
