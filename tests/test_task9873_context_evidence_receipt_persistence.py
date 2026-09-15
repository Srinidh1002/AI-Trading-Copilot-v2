from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_context_evidence_receipt_store import (
    Task9ContextEvidenceReceiptStore,
)
from services.contracts.task9_context_evidence_receipt_v1 import (
    Task9ContextEvidenceReceiptV1,
    task9_context_evidence_receipt_from_dict,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _receipt(
    *,
    broader_present=False,
    external_present=False,
):
    return Task9ContextEvidenceReceiptV1(
        receipt_id="task9-context:run-1:pred-1",
        official_run_id="run-1",
        parent_cycle_id="parent-1",
        prediction_id="pred-1",
        observation_id="obs-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        evaluated_at=NOW,
        broader_market_present=broader_present,
        broader_market_result_id=(
            "broader-1"
            if broader_present
            else None
        ),
        broader_market_status=(
            "READY"
            if broader_present
            else "UNAVAILABLE"
        ),
        external_context_present=external_present,
        external_context_result_id=(
            "external-1"
            if external_present
            else None
        ),
        external_context_status=(
            "READY_WITH_WARNINGS"
            if external_present
            else "UNAVAILABLE"
        ),
        source_timestamps={
            "BROADER:MARKET": NOW,
        },
    )


def test_missing_optional_context_is_explicit_unavailable_not_neutral():
    receipt = _receipt()

    assert (
        receipt.broader_market_status
        == "UNAVAILABLE"
    )

    assert (
        receipt.external_context_status
        == "UNAVAILABLE"
    )

    assert (
        receipt.broader_market_result_id
        is None
    )

    assert (
        receipt.external_context_result_id
        is None
    )


def test_available_context_requires_canonical_result_reference():
    receipt = _receipt(
        broader_present=True,
        external_present=True,
    )

    assert (
        receipt.broader_market_result_id
        == "broader-1"
    )

    assert (
        receipt.external_context_result_id
        == "external-1"
    )


def test_present_context_without_result_id_is_rejected():
    with pytest.raises(ValueError):
        Task9ContextEvidenceReceiptV1(
            receipt_id="r",
            official_run_id="run",
            parent_cycle_id="parent",
            prediction_id="prediction",
            observation_id="observation",
            underlying_symbol="NIFTY",
            exchange="NSE",
            evaluated_at=NOW,
            broader_market_present=True,
            broader_market_result_id=None,
            broader_market_status="READY",
            external_context_present=False,
            external_context_result_id=None,
            external_context_status="UNAVAILABLE",
        )


def test_receipt_round_trip_preserves_semantics():
    receipt = _receipt(
        broader_present=True,
        external_present=True,
    )

    recovered = (
        task9_context_evidence_receipt_from_dict(
            receipt.to_dict()
        )
    )

    assert recovered == receipt


def test_store_is_restart_safe_and_idempotent(
    tmp_path,
):
    path = (
        tmp_path
        / "context-evidence-receipts.json"
    )

    first = Task9ContextEvidenceReceiptStore(
        path
    )

    receipt = _receipt(
        broader_present=True,
        external_present=True,
    )

    assert first.save(receipt) == "SAVED"

    second = Task9ContextEvidenceReceiptStore(
        path
    )

    assert (
        second.recover("pred-1")
        == receipt
    )

    assert (
        second.save(receipt)
        == "DUPLICATE_SAME_PAYLOAD"
    )


def test_conflicting_duplicate_is_rejected(
    tmp_path,
):
    store = Task9ContextEvidenceReceiptStore(
        tmp_path
        / "context-evidence-receipts.json"
    )

    original = _receipt()

    assert store.save(original) == "SAVED"

    conflicting = Task9ContextEvidenceReceiptV1(
        receipt_id=original.receipt_id,
        official_run_id=original.official_run_id,
        parent_cycle_id=original.parent_cycle_id,
        prediction_id=original.prediction_id,
        observation_id=original.observation_id,
        underlying_symbol=original.underlying_symbol,
        exchange=original.exchange,
        evaluated_at=original.evaluated_at,
        broader_market_present=True,
        broader_market_result_id="different-broader",
        broader_market_status="READY",
        external_context_present=False,
        external_context_result_id=None,
        external_context_status="UNAVAILABLE",
        source_timestamps=original.source_timestamps,
    )

    with pytest.raises(
        ValueError,
        match="conflicting context evidence receipt",
    ):
        store.save(conflicting)
