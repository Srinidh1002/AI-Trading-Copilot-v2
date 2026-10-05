from __future__ import annotations

import json
from pathlib import Path

from services.paper_orchestration import r16_strategy_authority_v1 as authority


def _write_manifest(root: Path, **overrides):
    path = authority.activation_manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = authority.build_shadow_activation_manifest()
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_missing_manifest_is_shadow_and_not_ready(tmp_path):
    result = authority.evaluate_r16_selector_activation(
        repo_root=tmp_path,
    )

    assert result.ready is False
    assert result.mode == "SHADOW_ONLY"
    assert result.paper_entry_authorized is False
    assert result.live_execution_authorized is False
    assert result.broker_order_submission_authorized is False
    assert "R16_ACTIVATION_MANIFEST_MISSING" in result.blockers


def test_explicit_paper_entry_manifest_can_be_ready_when_incumbent_is_free(
    tmp_path,
):
    _write_manifest(
        tmp_path,
        mode="PAPER_ENTRY",
        paper_entry_authorized=True,
    )
    incumbent = tmp_path / "incumbent"

    result = authority.evaluate_r16_selector_activation(
        repo_root=tmp_path,
        incumbent_runtime_root=incumbent,
    )

    assert result.ready is True
    assert result.mode == "PAPER_ENTRY"
    assert result.paper_entry_authorized is True
    assert result.blockers == ()


def test_live_or_broker_authority_is_always_rejected(tmp_path):
    _write_manifest(
        tmp_path,
        mode="PAPER_ENTRY",
        paper_entry_authorized=True,
        live_execution_authorized=True,
        broker_order_submission_authorized=True,
    )

    result = authority.evaluate_r16_selector_activation(
        repo_root=tmp_path,
    )

    assert result.ready is False
    assert "LIVE_EXECUTION_PROHIBITED" in result.blockers
    assert "BROKER_ORDER_SUBMISSION_PROHIBITED" in result.blockers
    assert result.live_execution_authorized is False
    assert result.broker_order_submission_authorized is False


def test_active_incumbent_supervisor_blocks_paper_entry(tmp_path, monkeypatch):
    _write_manifest(
        tmp_path,
        mode="PAPER_ENTRY",
        paper_entry_authorized=True,
    )
    monkeypatch.setattr(
        authority,
        "lock_available",
        lambda *_args, **_kwargs: False,
    )

    result = authority.evaluate_r16_selector_activation(
        repo_root=tmp_path,
        incumbent_runtime_root=tmp_path / "r15",
    )

    assert result.ready is False
    assert "INCUMBENT_PAPER_SUPERVISOR_ACTIVE" in result.blockers


def test_shadow_mode_does_not_probe_or_require_incumbent_lock(
    tmp_path,
    monkeypatch,
):
    _write_manifest(tmp_path)
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        return False

    monkeypatch.setattr(authority, "lock_available", fail_if_called)

    result = authority.evaluate_r16_selector_activation(
        repo_root=tmp_path,
        incumbent_runtime_root=tmp_path / "r15",
    )

    assert result.ready is False
    assert result.mode == "SHADOW_ONLY"
    assert calls == []


def test_r16_namespace_refuses_legacy_index_state_aliases(tmp_path):
    _write_manifest(
        tmp_path,
        mode="PAPER_ENTRY",
        paper_entry_authorized=True,
    )
    namespace = (
        tmp_path
        / authority.R16_STATE_NAMESPACE
    )
    (namespace / "nifty_experimental.json").write_text(
        "{}",
        encoding="utf-8",
    )

    result = authority.evaluate_r16_selector_activation(
        repo_root=tmp_path,
    )

    assert result.ready is False
    assert (
        "R16_NAMESPACE_CONTAINS_LEGACY_STATE:nifty_experimental.json"
        in result.blockers
    )


def test_strategy_and_epoch_are_distinct_from_r15():
    assert authority.R16_STRATEGY_VERSION == "R16_TWO_MARKET_PARENT_V1"
    assert authority.R16_CERTIFICATION_EPOCH == "R16_INDEX_PARENT_CERT_V1"
    assert authority.R16_STRATEGY_VERSION != "NS_DESIGN_B_BID_AUTH_V3"
    assert authority.R16_CERTIFICATION_EPOCH != "NS_CERT_20260916_V3"
