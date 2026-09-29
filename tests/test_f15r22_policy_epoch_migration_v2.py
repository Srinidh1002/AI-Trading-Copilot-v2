from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from services.paper_orchestration.policy_epoch_migration_v2 import (
    EMPTY_EQUITY_DIVERSITY_STATE,
    PolicyEpochMigrationError,
    migrate_index_bundle,
    migrate_mcx_bundle,
)


def _write_json(
    path: Path,
    value: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            value,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _digest_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(value).hexdigest()


def test_index_migration_archives_exact_boundary_and_resets_only_certification(
    tmp_path,
):
    data = tmp_path / "paper_trades"

    state_path = data / "nifty_experimental.json"

    predictions = data / "nifty_predictions.jsonl"

    outcomes = data / "nifty_outcomes.jsonl"

    counted = [f"NIFTY_OLD_{i}" for i in range(7)]

    old_state = {
        "market": "NIFTY",
        "current_session": 18,
        "total_sessions": 100,
        "total_trades": 18,
        "winning_trades": 9,
        "losing_trades": 9,
        "total_pnl": 321.50,
        "t1_hits": 4,
        "t2_hits": 2,
        "t3_hits": 1,
        "stop_losses": 3,
        "market_close_exits": 0,
        "consecutive_wins": 1,
        "consecutive_losses": 0,
        "session_history": [
            {
                "trade_id": "OLD_HISTORY",
            }
        ],
        "completed_trades": [
            {
                "trade_id": "NIFTY_OLD_0",
                "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
                "certification_epoch": "NS_CERT_20260916_V3",
            }
        ],
        "active_trades": [],
        "orphaned_trades": [],
        "sessions_completed_today": 18,
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
        "certification_epoch": "NS_CERT_20260916_V3",
        "certification_counter": 7,
        "certification_wins": 4,
        "certification_losses": 3,
        "counted_trade_ids": counted,
        "diversity_state": {
            "trading_dates": ["2026-09-29"],
            "regimes": ["TRENDING_DOWN"],
            "session_phases": ["EARLY_CONTINUOUS"],
            "countable_by_day": {
                "2026-09-29": 7,
            },
        },
    }

    _write_json(
        state_path,
        old_state,
    )

    predictions.write_text(
        '{"old":"prediction"}\n',
        encoding="utf-8",
    )

    outcomes.write_text(
        '{"old":"outcome"}\n',
        encoding="utf-8",
    )

    state_before = state_path.read_bytes()

    prediction_before = predictions.read_bytes()

    outcome_before = outcomes.read_bytes()

    archive = tmp_path / "archive_nifty_v3"

    result = migrate_index_bundle(
        market="NIFTY",
        state_path=state_path,
        ledger_paths=[
            predictions,
            outcomes,
        ],
        archive_dir=archive,
        expected_old_strategy_version="NS_DESIGN_B_BID_AUTH_V3",
        expected_old_certification_epoch="NS_CERT_20260916_V3",
        new_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
        new_certification_epoch="NS_CERT_20260929_V4",
    )

    assert result["status"] == "MIGRATED"

    assert result["archived_certification_counter"] == 7

    assert (archive / state_path.name).read_bytes() == state_before

    assert (archive / predictions.name).read_bytes() == prediction_before

    assert (archive / outcomes.name).read_bytes() == outcome_before

    assert predictions.read_bytes() == b""

    assert outcomes.read_bytes() == b""

    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))

    state_manifest = next(
        row for row in manifest["files"] if row["archive_name"] == state_path.name
    )

    assert state_manifest["sha256"] == _digest_bytes(state_before)

    migrated = json.loads(state_path.read_text(encoding="utf-8"))

    assert migrated["strategy_version"] == "NS_DESIGN_B_BID_AUTH_V4"

    assert migrated["certification_epoch"] == "NS_CERT_20260929_V4"

    assert migrated["certification_counter"] == 0

    assert migrated["certification_wins"] == 0

    assert migrated["certification_losses"] == 0

    assert migrated["counted_trade_ids"] == []

    assert migrated["diversity_state"] == EMPTY_EQUITY_DIVERSITY_STATE

    # Operational history is preserved.
    assert migrated["total_trades"] == old_state["total_trades"]

    assert migrated["total_pnl"] == old_state["total_pnl"]

    assert migrated["current_session"] == old_state["current_session"]

    assert migrated["completed_trades"] == old_state["completed_trades"]

    assert migrated["session_history"] == old_state["session_history"]


def test_index_migration_refuses_active_trade(
    tmp_path,
):
    state = tmp_path / "nifty_experimental.json"

    original = {
        "market": "NIFTY",
        "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
        "certification_epoch": "NS_CERT_20260916_V3",
        "certification_counter": 0,
        "certification_wins": 0,
        "certification_losses": 0,
        "counted_trade_ids": [],
        "active_trades": [
            {
                "trade_id": "OPEN",
            }
        ],
    }

    _write_json(
        state,
        original,
    )

    before = state.read_bytes()

    archive = tmp_path / "archive"

    with pytest.raises(
        PolicyEpochMigrationError,
        match="INDEX_ACTIVE_TRADES_PRESENT",
    ):
        migrate_index_bundle(
            market="NIFTY",
            state_path=state,
            ledger_paths=[],
            archive_dir=archive,
            expected_old_strategy_version="NS_DESIGN_B_BID_AUTH_V3",
            expected_old_certification_epoch="NS_CERT_20260916_V3",
            new_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
            new_certification_epoch="NS_CERT_20260929_V4",
        )

    assert state.read_bytes() == before

    assert not archive.exists()


def test_mcx_migration_archives_exact_bundle_and_creates_fresh_epoch(
    tmp_path,
):
    data = tmp_path / "paper_trades"

    state_path = data / "mcx_crudeoilm_experimental.json"

    version_path = data / "mcx_strategy_version.json"

    predictions = data / "mcx_crudeoilm_predictions.jsonl"

    outcomes = data / "mcx_crudeoilm_outcomes.jsonl"

    decisions = data / "mcx_crudeoilm_decisions.jsonl"

    old_state = {
        "product": "CRUDEOILM",
        "epoch": "POST_PRECISION_V4",
        "strategy_version": "MCX_POST_PRECISION_V4",
        "certification_eligible": True,
        "starting_capital": 100000,
        "total_trades": 2,
        "winning_trades": 1,
        "losing_trades": 1,
        "t1_hit_wins": 1,
        "sl_losses": 1,
        "total_pnl": 550.0,
        "active_position": None,
        "completed_trades": [
            {
                "trade_id": "CRUDE_OLD_1",
            },
            {
                "trade_id": "CRUDE_OLD_2",
            },
        ],
        "_counted_trade_ids": [
            "CRUDE_OLD_1",
            "CRUDE_OLD_2",
        ],
    }

    old_authority = {
        "product": "CRUDEOILM",
        "strategy_version": "MCX_POST_PRECISION_V4",
        "epoch": "POST_PRECISION_V4",
        "certification_eligible": True,
    }

    _write_json(
        state_path,
        old_state,
    )

    _write_json(
        version_path,
        old_authority,
    )

    predictions.write_text(
        '{"old":"prediction"}\n',
        encoding="utf-8",
    )

    outcomes.write_text(
        '{"old":"outcome"}\n',
        encoding="utf-8",
    )

    decisions.write_text(
        '{"old":"decision"}\n',
        encoding="utf-8",
    )

    state_before = state_path.read_bytes()

    authority_before = version_path.read_bytes()

    prediction_before = predictions.read_bytes()

    outcome_before = outcomes.read_bytes()

    decision_before = decisions.read_bytes()

    archive = tmp_path / "archive_crude_v4"

    result = migrate_mcx_bundle(
        product="CRUDEOILM",
        state_path=state_path,
        version_path=version_path,
        ledger_paths=[
            predictions,
            outcomes,
            decisions,
        ],
        archive_dir=archive,
        expected_old_strategy_version="MCX_POST_PRECISION_V4",
        expected_old_epoch="POST_PRECISION_V4",
        new_strategy_version="MCX_POST_PRECISION_V5",
        new_epoch="POST_PRECISION_V5",
        certification_eligible=True,
    )

    assert result["status"] == "MIGRATED"

    assert result["archived_countable_trades"] == 2

    assert (archive / state_path.name).read_bytes() == state_before

    assert (archive / version_path.name).read_bytes() == authority_before

    assert (archive / predictions.name).read_bytes() == prediction_before

    assert (archive / outcomes.name).read_bytes() == outcome_before

    assert (archive / decisions.name).read_bytes() == decision_before

    assert predictions.read_bytes() == b""

    assert outcomes.read_bytes() == b""

    assert decisions.read_bytes() == b""

    fresh = json.loads(state_path.read_text(encoding="utf-8"))

    assert fresh["product"] == "CRUDEOILM"

    assert fresh["strategy_version"] == "MCX_POST_PRECISION_V5"

    assert fresh["epoch"] == "POST_PRECISION_V5"

    assert fresh["certification_eligible"] is True

    assert fresh["total_trades"] == 0

    assert fresh["t1_hit_wins"] == 0

    assert fresh["sl_losses"] == 0

    assert fresh["total_pnl"] == 0.0

    assert fresh["active_position"] is None

    assert fresh["completed_trades"] == []

    assert fresh["_counted_trade_ids"] == []

    authority = json.loads(version_path.read_text(encoding="utf-8"))

    assert authority["strategy_version"] == "MCX_POST_PRECISION_V5"

    assert authority["epoch"] == "POST_PRECISION_V5"

    assert authority["certification_eligible"] is True


def test_mcx_migration_refuses_active_position(
    tmp_path,
):
    state = tmp_path / "mcx_goldm_experimental.json"

    authority = tmp_path / "mcx_goldm_strategy_version.json"

    old_state = {
        "product": "GOLDM",
        "epoch": "GOLDM_PRECERT_V2",
        "strategy_version": "MCX_GOLDM_PRECERT_V2",
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "_counted_trade_ids": [],
        "active_position": {
            "trade_id": "OPEN_GOLD",
            "entry_time": "2026-09-29T14:00:00",
        },
    }

    old_authority = {
        "product": "GOLDM",
        "strategy_version": "MCX_GOLDM_PRECERT_V2",
        "epoch": "GOLDM_PRECERT_V2",
    }

    _write_json(
        state,
        old_state,
    )

    _write_json(
        authority,
        old_authority,
    )

    state_before = state.read_bytes()

    authority_before = authority.read_bytes()

    archive = tmp_path / "archive"

    with pytest.raises(
        PolicyEpochMigrationError,
        match="MCX_ACTIVE_POSITION_PRESENT",
    ):
        migrate_mcx_bundle(
            product="GOLDM",
            state_path=state,
            version_path=authority,
            ledger_paths=[],
            archive_dir=archive,
            expected_old_strategy_version="MCX_GOLDM_PRECERT_V2",
            expected_old_epoch="GOLDM_PRECERT_V2",
            new_strategy_version="MCX_GOLDM_PRECERT_V3",
            new_epoch="GOLDM_PRECERT_V3",
            certification_eligible=True,
        )

    assert state.read_bytes() == state_before

    assert authority.read_bytes() == authority_before

    assert not archive.exists()


def test_archive_destination_collision_fails_closed(
    tmp_path,
):
    state = tmp_path / "sensex_experimental.json"

    _write_json(
        state,
        {
            "market": "SENSEX",
            "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
            "certification_epoch": "NS_CERT_20260916_V3",
            "certification_counter": 0,
            "certification_wins": 0,
            "certification_losses": 0,
            "counted_trade_ids": [],
            "active_trades": [],
        },
    )

    before = state.read_bytes()

    archive = tmp_path / "existing_archive"

    archive.mkdir()

    with pytest.raises(
        PolicyEpochMigrationError,
        match="ARCHIVE_DESTINATION_ALREADY_EXISTS",
    ):
        migrate_index_bundle(
            market="SENSEX",
            state_path=state,
            ledger_paths=[],
            archive_dir=archive,
            expected_old_strategy_version="NS_DESIGN_B_BID_AUTH_V3",
            expected_old_certification_epoch="NS_CERT_20260916_V3",
            new_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
            new_certification_epoch="NS_CERT_20260929_V4",
        )

    assert state.read_bytes() == before


# E9_R22_MIGRATION_BOUNDARY_HARDENING


def test_index_migration_refuses_unexpected_old_policy_without_mutation(
    tmp_path,
):
    state = tmp_path / "nifty_experimental.json"

    ledger = tmp_path / "nifty_predictions.jsonl"

    _write_json(
        state,
        {
            "market": "NIFTY",
            "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
            "certification_epoch": "NS_CERT_20260916_V3",
            "certification_counter": 0,
            "certification_wins": 0,
            "certification_losses": 0,
            "counted_trade_ids": [],
            "active_trades": [],
        },
    )

    ledger.write_text(
        '{"old":"prediction"}\n',
        encoding="utf-8",
    )

    state_before = state.read_bytes()

    ledger_before = ledger.read_bytes()

    archive = tmp_path / "wrong_index_archive"

    with pytest.raises(
        PolicyEpochMigrationError,
        match="INDEX_UNEXPECTED_OLD_POLICY_AUTHORITY",
    ):
        migrate_index_bundle(
            market="NIFTY",
            state_path=state,
            ledger_paths=[
                ledger,
            ],
            archive_dir=archive,
            expected_old_strategy_version="NS_DESIGN_B_BID_AUTH_V2",
            expected_old_certification_epoch="NS_CERT_20260916_V2",
            new_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
            new_certification_epoch="NS_CERT_20260929_V4",
        )

    assert state.read_bytes() == state_before

    assert ledger.read_bytes() == ledger_before

    assert not archive.exists()


def test_mcx_migration_refuses_unexpected_old_policy_without_mutation(
    tmp_path,
):
    state = tmp_path / "mcx_crudeoilm_experimental.json"

    authority = tmp_path / "mcx_strategy_version.json"

    ledger = tmp_path / "mcx_crudeoilm_outcomes.jsonl"

    _write_json(
        state,
        {
            "product": "CRUDEOILM",
            "epoch": "POST_PRECISION_V4",
            "strategy_version": "MCX_POST_PRECISION_V4",
            "certification_eligible": True,
            "t1_hit_wins": 0,
            "sl_losses": 0,
            "_counted_trade_ids": [],
            "active_position": None,
            "completed_trades": [],
        },
    )

    _write_json(
        authority,
        {
            "product": "CRUDEOILM",
            "strategy_version": "MCX_POST_PRECISION_V4",
            "epoch": "POST_PRECISION_V4",
            "certification_eligible": True,
        },
    )

    ledger.write_text(
        '{"old":"outcome"}\n',
        encoding="utf-8",
    )

    state_before = state.read_bytes()

    authority_before = authority.read_bytes()

    ledger_before = ledger.read_bytes()

    archive = tmp_path / "wrong_mcx_archive"

    with pytest.raises(
        PolicyEpochMigrationError,
        match="MCX_UNEXPECTED_OLD_POLICY_AUTHORITY",
    ):
        migrate_mcx_bundle(
            product="CRUDEOILM",
            state_path=state,
            version_path=authority,
            ledger_paths=[
                ledger,
            ],
            archive_dir=archive,
            expected_old_strategy_version="MCX_POST_PRECISION_V3",
            expected_old_epoch="POST_PRECISION_V3",
            new_strategy_version="MCX_POST_PRECISION_V5",
            new_epoch="POST_PRECISION_V5",
            certification_eligible=True,
        )

    assert state.read_bytes() == state_before

    assert authority.read_bytes() == authority_before

    assert ledger.read_bytes() == ledger_before

    assert not archive.exists()


def test_migrated_index_bundle_is_accepted_by_current_runtime_and_preflight(
    tmp_path,
    monkeypatch,
):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    monkeypatch.syspath_prepend(str(root / "src"))

    monkeypatch.syspath_prepend(str(root))

    repo_root = tmp_path / "repo"

    data = repo_root / "data" / "paper_trades"

    data.mkdir(
        parents=True,
        exist_ok=True,
    )

    state = data / "nifty_experimental.json"

    predictions = data / "nifty_predictions.jsonl"

    outcomes = data / "nifty_outcomes.jsonl"

    _write_json(
        state,
        {
            "market": "NIFTY",
            "current_session": 5,
            "total_sessions": 100,
            "total_trades": 5,
            "winning_trades": 3,
            "losing_trades": 2,
            "total_pnl": 100.0,
            "session_history": [],
            "completed_trades": [],
            "active_trades": [],
            "orphaned_trades": [],
            "sessions_completed_today": 5,
            "strategy_version": "NS_DESIGN_B_BID_AUTH_V3",
            "certification_epoch": "NS_CERT_20260916_V3",
            "certification_counter": 1,
            "certification_wins": 1,
            "certification_losses": 0,
            "counted_trade_ids": [
                "OLD_NIFTY_CERT_1",
            ],
        },
    )

    predictions.write_text(
        '{"old":"prediction"}\n',
        encoding="utf-8",
    )

    outcomes.write_text(
        '{"old":"outcome"}\n',
        encoding="utf-8",
    )

    migrate_index_bundle(
        market="NIFTY",
        state_path=state,
        ledger_paths=[
            predictions,
            outcomes,
        ],
        archive_dir=tmp_path / "index_acceptance_archive",
        expected_old_strategy_version="NS_DESIGN_B_BID_AUTH_V3",
        expected_old_certification_epoch="NS_CERT_20260916_V3",
        new_strategy_version="NS_DESIGN_B_BID_AUTH_V4",
        new_certification_epoch="NS_CERT_20260929_V4",
    )

    assert predictions.read_bytes() == b""

    assert outcomes.read_bytes() == b""

    from services.paper_orchestration.state_authority_readonly_v2 import (
        validate_market,
    )

    verdict = validate_market(
        repo_root,
        "NIFTY",
    )

    assert verdict.ok is True

    assert verdict.reason == "STATE_OK"

    import importlib.util

    preflight_path = root / "tools" / "preflight_and_start_five_market_paper.py"

    spec = importlib.util.spec_from_file_location(
        "e9_index_preflight",
        preflight_path,
    )

    assert spec is not None

    assert spec.loader is not None

    preflight = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(preflight)

    result = preflight.check_state_authority(
        ("NIFTY",),
        repo_root,
    )

    assert result["NIFTY"][0] is True

    from target_focused_bot import UnifiedTradingBot

    bot = UnifiedTradingBot.__new__(UnifiedTradingBot)

    bot.market = "NIFTY"

    bot.state_file = str(state)

    assert bot.load_state() is True

    assert bot.state_load_classification == "VALID_EXISTING"

    assert bot.strategy_version == "NS_DESIGN_B_BID_AUTH_V4"

    assert bot.certification_epoch == "NS_CERT_20260929_V4"

    assert bot.certification_counter == 0

    assert bot.counted_trade_ids == set()


def test_migrated_mcx_bundle_is_accepted_by_current_runtime_and_preflight(
    tmp_path,
    monkeypatch,
):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    monkeypatch.syspath_prepend(str(root / "src"))

    monkeypatch.syspath_prepend(str(root))

    repo_root = tmp_path / "repo"

    data = repo_root / "data" / "paper_trades"

    data.mkdir(
        parents=True,
        exist_ok=True,
    )

    state = data / "mcx_crudeoilm_experimental.json"

    authority = data / "mcx_strategy_version.json"

    predictions = data / "mcx_crudeoilm_predictions.jsonl"

    outcomes = data / "mcx_crudeoilm_outcomes.jsonl"

    decisions = data / "mcx_crudeoilm_decisions.jsonl"

    _write_json(
        state,
        {
            "product": "CRUDEOILM",
            "epoch": "POST_PRECISION_V4",
            "strategy_version": "MCX_POST_PRECISION_V4",
            "certification_eligible": True,
            "starting_capital": 100000,
            "total_trades": 1,
            "winning_trades": 1,
            "losing_trades": 0,
            "t1_hit_wins": 1,
            "sl_losses": 0,
            "total_pnl": 100.0,
            "active_position": None,
            "completed_trades": [
                {
                    "trade_id": "OLD_CRUDE_1",
                }
            ],
            "_counted_trade_ids": [
                "OLD_CRUDE_1",
            ],
        },
    )

    _write_json(
        authority,
        {
            "product": "CRUDEOILM",
            "strategy_version": "MCX_POST_PRECISION_V4",
            "epoch": "POST_PRECISION_V4",
            "certification_eligible": True,
        },
    )

    predictions.write_text(
        '{"old":"prediction"}\n',
        encoding="utf-8",
    )

    outcomes.write_text(
        '{"old":"outcome"}\n',
        encoding="utf-8",
    )

    decisions.write_text(
        '{"old":"decision"}\n',
        encoding="utf-8",
    )

    migrate_mcx_bundle(
        product="CRUDEOILM",
        state_path=state,
        version_path=authority,
        ledger_paths=[
            predictions,
            outcomes,
            decisions,
        ],
        archive_dir=tmp_path / "mcx_acceptance_archive",
        expected_old_strategy_version="MCX_POST_PRECISION_V4",
        expected_old_epoch="POST_PRECISION_V4",
        new_strategy_version="MCX_POST_PRECISION_V5",
        new_epoch="POST_PRECISION_V5",
        certification_eligible=True,
    )

    assert predictions.read_bytes() == b""

    assert outcomes.read_bytes() == b""

    assert decisions.read_bytes() == b""

    from services.paper_orchestration.state_authority_readonly_v2 import (
        validate_market,
    )

    verdict = validate_market(
        repo_root,
        "CRUDEOILM",
    )

    assert verdict.ok is True

    assert verdict.reason == "STATE_OK"

    import importlib.util

    preflight_path = root / "tools" / "preflight_and_start_five_market_paper.py"

    spec = importlib.util.spec_from_file_location(
        "e9_mcx_preflight",
        preflight_path,
    )

    assert spec is not None

    assert spec.loader is not None

    preflight = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(preflight)

    result = preflight.check_state_authority(
        ("CRUDEOILM",),
        repo_root,
    )

    assert result["CRUDEOILM"][0] is True

    from mcx import mcx_paper_bot, mcx_version

    cfg = mcx_version.PRODUCT_EPOCHS["CRUDEOILM"]

    monkeypatch.setitem(
        cfg,
        "version_path",
        str(authority),
    )

    version_result = mcx_version.initialize_or_verify_for_product("CRUDEOILM")

    assert version_result["status"] == "OK"

    monkeypatch.setattr(
        mcx_paper_bot,
        "PRODUCT",
        "CRUDEOILM",
    )

    monkeypatch.setattr(
        mcx_paper_bot,
        "STATE_PATH",
        str(state),
    )

    loaded = mcx_paper_bot.load_state()

    assert loaded["strategy_version"] == "MCX_POST_PRECISION_V5"

    assert loaded["epoch"] == "POST_PRECISION_V5"

    assert loaded["t1_hit_wins"] == 0

    assert loaded["sl_losses"] == 0

    assert loaded["_counted_trade_ids"] == []
