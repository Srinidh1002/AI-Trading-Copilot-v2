"""Durable Task 9 close-drain state authority."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemKind,
    Task9CloseDrainItemStatus,
    Task9CloseDrainItemV1,
    Task9CloseDrainStateV1,
    Task9CloseDrainStatus,
)


def _state_from_dict(value: object) -> Task9CloseDrainStateV1:
    if type(value) is not dict:
        raise ValueError("invalid Task9 close-drain state")

    items = tuple(
        Task9CloseDrainItemV1(
            prediction_id=item["prediction_id"],
            market=item["market"],
            kind=Task9CloseDrainItemKind(
                item["kind"]
            ),
            status=Task9CloseDrainItemStatus(
                item["status"]
            ),
            reason_codes=tuple(
                item.get("reason_codes", ())
            ),
        )
        for item in value["items"]
    )

    return Task9CloseDrainStateV1(
        official_run_id=value["official_run_id"],
        market_date=date.fromisoformat(
            value["market_date"]
        ),
        evaluated_at=datetime.fromisoformat(
            value["evaluated_at"]
        ),
        status=Task9CloseDrainStatus(
            value["status"]
        ),
        session_phases=tuple(
            (str(market), str(phase))
            for market, phase
            in value["session_phases"]
        ),
        items=items,
        reason_codes=tuple(
            value.get("reason_codes", ())
        ),
        execution_mode=value["execution_mode"],
        broker_order_submission=value[
            "broker_order_submission"
        ],
        live_execution_eligible=value[
            "live_execution_eligible"
        ],
        schema_version=value["schema_version"],
    )


def _semantic(
    state: Task9CloseDrainStateV1,
) -> dict[str, object]:
    value = state.to_dict()
    value.pop("evaluated_at", None)
    return value


class Task9CloseDrainStateStore:
    """One mutable-until-complete receipt per run/session."""

    VERSION = 1

    def __init__(self, root: str | Path):
        self.path = (
            Path(root)
            / "task9-close-drain-state.json"
        )

    @staticmethod
    def _key(
        official_run_id: str,
        market_date: date,
    ) -> str:
        if (
            type(official_run_id) is not str
            or not official_run_id.strip()
        ):
            raise ValueError("official_run_id")
        if type(market_date) is not date:
            raise TypeError("market_date")
        return (
            f"{official_run_id.strip()}:"
            f"{market_date.isoformat()}"
        )

    def _read(self) -> dict[str, object]:
        if not self.path.exists():
            return {
                "version": self.VERSION,
                "records": {},
            }

        try:
            value = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            raise ValueError(
                "invalid Task9 close-drain store"
            ) from exc

        if (
            type(value) is not dict
            or set(value)
            != {"version", "records"}
            or value["version"] != self.VERSION
            or type(value["records"]) is not dict
        ):
            raise ValueError(
                "invalid Task9 close-drain store"
            )

        return value

    def get(
        self,
        *,
        official_run_id: str,
        market_date: date,
    ) -> Task9CloseDrainStateV1 | None:
        raw = self._read()["records"].get(
            self._key(
                official_run_id,
                market_date,
            )
        )

        return (
            None
            if raw is None
            else _state_from_dict(raw)
        )

    def save(
        self,
        state: Task9CloseDrainStateV1,
    ) -> Task9CloseDrainStateV1:
        if type(state) is not Task9CloseDrainStateV1:
            raise TypeError("state")

        document = self._read()
        key = self._key(
            state.official_run_id,
            state.market_date,
        )

        existing_raw = document[
            "records"
        ].get(key)

        if existing_raw is not None:
            existing = _state_from_dict(
                existing_raw
            )

            # COMPLETE is a sealed lifecycle receipt.
            # No later fact is allowed to silently
            # regress or rewrite finalized authority.
            if (
                existing.status
                is Task9CloseDrainStatus.COMPLETE
            ):
                if (
                    _semantic(existing)
                    != _semantic(state)
                ):
                    raise ValueError(
                        "sealed Task9 close-drain conflict"
                    )
                return existing

            if (
                state.evaluated_at
                < existing.evaluated_at
            ):
                raise ValueError(
                    "Task9 close-drain time regression"
                )

        document["records"][key] = (
            state.to_dict()
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        try:
            temporary.write_text(
                json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            replace_task9_atomic_file(
                temporary,
                self.path,
            )
        finally:
            temporary.unlink(
                missing_ok=True
            )

        recovered = self.get(
            official_run_id=state.official_run_id,
            market_date=state.market_date,
        )
        if recovered is None:
            raise ValueError(
                "Task9 close-drain persistence verification"
            )

        return recovered
