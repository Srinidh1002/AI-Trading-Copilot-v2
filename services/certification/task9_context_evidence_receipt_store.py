"""Atomic Task 9 canonical context-evidence receipt persistence."""

from __future__ import annotations

import json
from pathlib import Path

from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)
from services.contracts.task9_context_evidence_receipt_v1 import (
    Task9ContextEvidenceReceiptV1,
    task9_context_evidence_receipt_from_dict,
)


class Task9ContextEvidenceReceiptStore:
    def __init__(
        self,
        file_path: str | Path,
    ) -> None:
        self.file_path = Path(
            file_path
        )

    def _read(self) -> dict[str, object]:
        if not self.file_path.exists():
            return {
                "version": 1,
                "receipts": {},
            }

        try:
            document = json.loads(
                self.file_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "invalid context evidence receipt store"
            ) from exc

        if (
            type(document) is not dict
            or set(document)
            != {"version", "receipts"}
            or document["version"] != 1
            or type(document["receipts"])
            is not dict
        ):
            raise ValueError(
                "invalid context evidence receipt store"
            )

        for prediction_id, raw in (
            document["receipts"].items()
        ):
            if (
                type(raw) is not dict
                or raw.get("prediction_id")
                != prediction_id
            ):
                raise ValueError(
                    "context evidence receipt key mismatch"
                )

            task9_context_evidence_receipt_from_dict(
                raw
            )

        return document

    def _write(
        self,
        document: dict[str, object],
    ) -> None:
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.file_path.with_name(
            self.file_path.name + ".tmp"
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
                self.file_path,
            )

        finally:
            temporary.unlink(
                missing_ok=True
            )

    def save(
        self,
        receipt: Task9ContextEvidenceReceiptV1,
    ) -> str:
        if (
            type(receipt)
            is not Task9ContextEvidenceReceiptV1
        ):
            raise TypeError("receipt")

        document = self._read()
        raw = receipt.to_dict()

        existing = document[
            "receipts"
        ].get(
            receipt.prediction_id
        )

        if existing is not None:
            if existing != raw:
                raise ValueError(
                    "conflicting context evidence receipt"
                )

            return "DUPLICATE_SAME_PAYLOAD"

        document["receipts"][
            receipt.prediction_id
        ] = raw

        self._write(document)

        return "SAVED"

    def recover(
        self,
        prediction_id: str,
    ) -> Task9ContextEvidenceReceiptV1 | None:
        if (
            type(prediction_id) is not str
            or not prediction_id.strip()
        ):
            raise ValueError("prediction_id")

        raw = self._read()[
            "receipts"
        ].get(
            prediction_id
        )

        if raw is None:
            return None

        return (
            task9_context_evidence_receipt_from_dict(
                raw
            )
        )


__all__ = (
    "Task9ContextEvidenceReceiptStore",
)
