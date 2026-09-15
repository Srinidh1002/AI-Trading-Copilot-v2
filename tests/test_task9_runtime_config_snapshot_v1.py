from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from services.certification.task9_runtime_config_builder import build_task9_runtime_config
from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperRunManifestV1,
    load_or_create_task9_run_manifest,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9LegacyConfigConflictObservationV1,
    Task9RuntimeConfigSnapshotV1,
    build_task9_runtime_config_snapshot,
)


_POLICIES = {
    "canonical_directional": "directional.v1", "session": "session.v1", "risk": "risk.v1",
    "contract_selection": "selection.v1", "lifecycle": "lifecycle.v1", "counting": "counting.v1",
    "failure_disposition": "future", "contract_spread": "spread.v1", "liquidity": "liquidity.v1",
    "minimum_risk_reward": "rr.v1", "stop_target": "stop-target.v1", "portfolio_concurrency": "portfolio.v1",
}


def _config(**overrides):
    values = dict(
        runtime_config_id="runtime-1", runtime_config_version="1", campaign_registry_location="task9/campaigns",
        campaign_id="campaign-1", market_date=date(2026, 8, 15), official_run_id="run-1",
        official_root="task9/official", certification_registry_root="task9/registry",
        authoritative_persistence_root="task9/runtime", dashboard_publication_location="task9/dashboard",
        available_capital=25000.0, risk_fraction=0.02, maximum_quantity=50,
        policy_references=_POLICIES,
        legacy_values={"config_capital": 100000, "trading_runtime_capital": 10000, "config_risk_fraction": 0.02, "trading_runtime_risk_percent": 1.0},
    )
    values.update(overrides)
    return build_task9_runtime_config(**values)


def _observations():
    return (
        Task9LegacyConfigConflictObservationV1("capital", 25000.0, "config.DEFAULT_CAPITAL", 100000, "CURRENCY", "EXPLICIT_CANONICAL_WINS"),
        Task9LegacyConfigConflictObservationV1("capital", 25000.0, "TradingRuntimeConfig.DEFAULT_CAPITAL", 10000, "CURRENCY", "EXPLICIT_CANONICAL_WINS"),
        Task9LegacyConfigConflictObservationV1("risk_fraction", 0.02, "config.RISK_PER_TRADE", 0.02, "DECIMAL_FRACTION", "EXPLICIT_CANONICAL_WINS"),
        Task9LegacyConfigConflictObservationV1("risk_fraction", 0.02, "TradingRuntimeConfig.DEFAULT_RISK_PER_TRADE_PERCENT", 1.0, "PERCENT", "EXPLICIT_CANONICAL_WINS"),
    )


def test_snapshot_is_deterministic_immutable_and_round_trips():
    first = build_task9_runtime_config_snapshot(_config(), conflict_observations=_observations())
    second = build_task9_runtime_config_snapshot(_config(), conflict_observations=_observations())
    assert first.content_sha256 == second.content_sha256
    assert first.snapshot_id == second.snapshot_id
    assert Task9RuntimeConfigSnapshotV1.from_dict(first.to_dict()) == first
    with pytest.raises(FrozenInstanceError):
        first.snapshot_id = "other"


def test_nonsecret_config_change_changes_hash_and_no_secret_can_enter_snapshot():
    first = build_task9_runtime_config_snapshot(_config())
    second = build_task9_runtime_config_snapshot(_config(maximum_quantity=75))
    assert first.content_sha256 != second.content_sha256
    assert "super-secret" not in first.to_dict().__repr__()
    invalid = first.to_dict()
    invalid["canonical_config"]["angel_api_key"] = "super-secret"
    with pytest.raises(ValueError, match="canonical_config"):
        Task9RuntimeConfigSnapshotV1.from_dict(invalid)


def test_invalid_hash_and_unresolved_or_duplicate_conflicts_are_rejected():
    snapshot = build_task9_runtime_config_snapshot(_config())
    invalid = snapshot.to_dict()
    invalid["content_sha256"] = "not-a-hash"
    with pytest.raises(ValueError):
        Task9RuntimeConfigSnapshotV1.from_dict(invalid)
    with pytest.raises(ValueError, match="unresolved"):
        Task9LegacyConfigConflictObservationV1("capital", 1.0, "legacy", 2.0, "CURRENCY", "FAIL_IF_UNRESOLVED")
    duplicate = Task9LegacyConfigConflictObservationV1("capital", 25000.0, "legacy", 10000, "CURRENCY", "EXPLICIT_CANONICAL_WINS")
    with pytest.raises(ValueError, match="conflicting legacy"):
        build_task9_runtime_config_snapshot(_config(), conflict_observations=(duplicate, duplicate))


def test_manifest_accepts_paired_valid_reference_and_rejects_malformed_hash():
    snapshot = build_task9_runtime_config_snapshot(_config())
    started_at = datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc)
    manifest = Task9LivePaperRunManifestV1(
        "run-1", started_at, runtime_config_snapshot_id=snapshot.snapshot_id,
        runtime_config_sha256=snapshot.content_sha256,
    )
    assert manifest.runtime_config_snapshot_id == snapshot.snapshot_id
    with pytest.raises(ValueError):
        Task9LivePaperRunManifestV1("run-1", started_at, runtime_config_snapshot_id="bad", runtime_config_sha256="0" * 64)


def test_full_pre_provenance_manifest_is_explicitly_legacy_without_a_snapshot(tmp_path):
    started_at = datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc)
    (tmp_path / "task9-live-paper-run.json").write_text(
        '{"official_run_id":"run-1","official_start_at":"2026-08-15T09:15:00+00:00",'
        '"run_classification":"OFFICIAL_CERTIFICATION","execution_mode":"PAPER",'
        '"broker_order_submission":false,"live_execution_eligible":false}', encoding="utf-8",
    )
    manifest = load_or_create_task9_run_manifest(
        persistence_root=tmp_path, official_run_id="run-1", started_at=started_at,
    )
    assert manifest.runtime_config_snapshot_id is None
    assert manifest.runtime_config_sha256 is None
