"""Durable immutable PAPER portfolio-policy authority for Task 9."""

from __future__ import annotations

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file

import json
import os
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)


_STORE_SCHEMA = "task9-paper-portfolio-policy-store.v1"


def _decode_policy(
    payload: Mapping[str, Any],
) -> PaperPortfolioPolicyV1:
    if not isinstance(payload, Mapping):
        raise TypeError("persisted portfolio policy must be a mapping")

    values = dict(payload)

    policy_timestamp = values.get("policy_timestamp")

    if not isinstance(policy_timestamp, str):
        raise ValueError(
            "persisted portfolio policy timestamp is invalid"
        )

    try:
        values["policy_timestamp"] = datetime.fromisoformat(
            policy_timestamp
        )
    except ValueError as exc:
        raise ValueError(
            "persisted portfolio policy timestamp is invalid"
        ) from exc

    metadata = values.get("metadata", {})

    if not isinstance(metadata, Mapping):
        raise ValueError(
            "persisted portfolio policy metadata is invalid"
        )

    values["metadata"] = dict(metadata)

    return PaperPortfolioPolicyV1(**values)


class Task9PaperPortfolioPolicyStore:
    """Immutable policy storage keyed by portfolio_policy_id."""

    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def _load_payload(self) -> dict[str, object]:
        if not self.path.exists():
            return {
                "schema_version": _STORE_SCHEMA,
                "policies": {},
            }

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Task 9 portfolio policy store is unreadable"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "Task 9 portfolio policy store root is invalid"
            )

        if payload.get("schema_version") != _STORE_SCHEMA:
            raise ValueError(
                "Task 9 portfolio policy store schema is invalid"
            )

        policies = payload.get("policies")

        if not isinstance(policies, dict):
            raise ValueError(
                "Task 9 portfolio policy store policies are invalid"
            )

        return payload

    def _write_payload(
        self,
        payload: Mapping[str, object],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.path.with_name(
            f"{self.path.name}.tmp"
        )

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
        )

        replace_task9_atomic_file(
            temporary,
            self.path,
        )

    def save(
        self,
        policy: PaperPortfolioPolicyV1,
    ) -> PaperPortfolioPolicyV1:
        if type(policy) is not PaperPortfolioPolicyV1:
            raise TypeError(
                "policy must be exact PaperPortfolioPolicyV1"
            )

        policy_id = policy.portfolio_policy_id
        serialized = policy.to_dict()

        with self._lock:
            payload = self._load_payload()
            policies = dict(payload["policies"])

            existing = policies.get(policy_id)

            if existing is not None:
                if existing == serialized:
                    recovered = _decode_policy(existing)

                    if recovered.to_dict() != serialized:
                        raise ValueError(
                            "Task 9 portfolio policy recovery mismatch"
                        )

                    return recovered

                raise ValueError(
                    "Task 9 portfolio policy identity conflict"
                )

            policies[policy_id] = serialized

            self._write_payload(
                {
                    "schema_version": _STORE_SCHEMA,
                    "policies": policies,
                }
            )

        return policy

    def recover(
        self,
        portfolio_policy_id: str,
    ) -> PaperPortfolioPolicyV1 | None:
        if (
            type(portfolio_policy_id) is not str
            or not portfolio_policy_id.strip()
        ):
            raise ValueError(
                "portfolio_policy_id must be non-empty"
            )

        normalized = portfolio_policy_id.strip()

        with self._lock:
            payload = self._load_payload()
            policies = payload["policies"]

            stored = policies.get(normalized)

            if stored is None:
                return None

            recovered = _decode_policy(stored)

            if (
                recovered.portfolio_policy_id
                != normalized
            ):
                raise ValueError(
                    "Task 9 portfolio policy identity mismatch"
                )

            return recovered