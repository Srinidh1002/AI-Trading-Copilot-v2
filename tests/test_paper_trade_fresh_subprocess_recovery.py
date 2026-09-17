"""Fresh-process certification for typed P7 persistence and replay."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap


def _run_python(repository_path, source: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source), str(repository_path)],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_fresh_process_recovers_open_duplicate_noop_and_persists_t1(tmp_path):
    path = tmp_path / "open.json"
    written = _run_python(
        path,
        """
        import json, sys
        from dataclasses import replace
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import PaperTradePersistenceService
        from tests.p7_fixture_helpers import NOW, make_open_state, make_policy
        from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot

        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        snapshot = make_snapshot(
            lifecycle_policy=make_policy(allow_partial_exits=True),
            lifecycle_state=replace(make_open_state(), last_observation_id="obs-1",
                last_observation_timestamp=NOW))
        service.save(snapshot)
        print(json.dumps({"state": snapshot.lifecycle_state.current_state,
                          "json": snapshot.to_json()}))
        """,
    )
    advanced = _run_python(
        path,
        """
        import json, sys
        from datetime import timedelta
        from pathlib import Path
        from services.contracts import PaperTradePositionEvaluationInputV1
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import (PaperTradePersistenceService,
            PaperTradeRecoveryService, PaperTradeReplayCoordinator)
        from tests.p7_fixture_helpers import NOW, make_observation

        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        snapshot = PaperTradeRecoveryService(service).recover_active()[0]
        before = Path(sys.argv[1]).read_bytes()
        duplicate = PaperTradePositionEvaluationInputV1(
            snapshot.position, snapshot.lifecycle_policy, snapshot.lifecycle_state,
            snapshot.latest_observation, NOW, "sub-dup-tr", "sub-dup-state",
            "sub-dup-result", ("sub-dup-fill",), "sub-dup-pnl")
        unchanged, duplicate_result = PaperTradeReplayCoordinator(service).evaluate(
            snapshot, duplicate)
        assert unchanged.to_json() == snapshot.to_json()
        assert duplicate_result.position_decision == "HOLD"
        assert duplicate_result.pnl_evidence is None
        assert Path(sys.argv[1]).read_bytes() == before

        at = NOW + timedelta(seconds=1)
        observation = make_observation(
            observation_id="sub-t1", observed_at=at, received_at=at,
            option_last_price=110., option_open=110., option_low=109.,
            option_high=111., option_close=110.)
        evaluation = PaperTradePositionEvaluationInputV1(
            snapshot.position, snapshot.lifecycle_policy, snapshot.lifecycle_state,
            observation, at, "sub-t1-tr", "sub-t1-state", "sub-t1-result",
            ("sub-t1-fill",), "sub-t1-pnl")
        updated, result = PaperTradeReplayCoordinator(service).evaluate(snapshot, evaluation)
        assert result.status == "PARTIALLY_EXITED"
        print(json.dumps({"state": updated.lifecycle_state.current_state,
                          "fills": [fill.fill_id for fill in updated.position.exit_fills],
                          "event_sequence": updated.event_sequence,
                          "json": updated.to_json()}))
        """,
    )
    recovered = _run_python(
        path,
        """
        import json, sys
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import PaperTradePersistenceService, PaperTradeRecoveryService
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        snapshot = PaperTradeRecoveryService(service).recover_active()[0]
        print(json.dumps({"state": snapshot.lifecycle_state.current_state,
                          "fills": [fill.fill_id for fill in snapshot.position.exit_fills],
                          "event_sequence": snapshot.event_sequence,
                          "json": snapshot.to_json()}))
        """,
    )

    assert written["state"] == "OPEN"
    assert advanced["state"] == recovered["state"] == "PARTIALLY_EXITED"
    assert advanced["fills"] == recovered["fills"] == ["sub-t1-fill"]
    assert advanced["event_sequence"] == recovered["event_sequence"] == 1
    assert advanced["json"] == recovered["json"]


def test_fresh_process_recovers_partial_duplicate_noop_and_persists_t2(tmp_path):
    path = tmp_path / "partial.json"
    _run_python(
        path,
        """
        import json, sys
        from datetime import timedelta
        from services.contracts import PaperTradePositionEvaluationInputV1
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import PaperTradePersistenceService, PaperTradeReplayCoordinator
        from tests.p7_fixture_helpers import NOW, make_observation, make_policy
        from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        source = make_snapshot(lifecycle_policy=make_policy(allow_partial_exits=True))
        service.save(source)
        at = NOW + timedelta(seconds=1)
        observation = make_observation(observation_id="partial-t1", observed_at=at,
            received_at=at, option_last_price=110., option_open=110., option_low=109.,
            option_high=111., option_close=110.)
        evaluation = PaperTradePositionEvaluationInputV1(source.position,
            source.lifecycle_policy, source.lifecycle_state, observation, at,
            "partial-t1-tr", "partial-t1-state", "partial-t1-result",
            ("partial-t1-fill",), "partial-t1-pnl")
        updated, result = PaperTradeReplayCoordinator(service).evaluate(source, evaluation)
        assert result.status == "PARTIALLY_EXITED"
        print(json.dumps({"state": updated.lifecycle_state.current_state}))
        """,
    )
    advanced = _run_python(
        path,
        """
        import json, sys
        from datetime import timedelta
        from pathlib import Path
        from services.contracts import PaperTradePositionEvaluationInputV1
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import (PaperTradePersistenceService,
            PaperTradeRecoveryService, PaperTradeReplayCoordinator)
        from tests.p7_fixture_helpers import NOW, make_observation
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        snapshot = PaperTradeRecoveryService(service).recover_active()[0]
        before = Path(sys.argv[1]).read_bytes()
        duplicate = PaperTradePositionEvaluationInputV1(snapshot.position,
            snapshot.lifecycle_policy, snapshot.lifecycle_state,
            snapshot.latest_observation, NOW + timedelta(seconds=1),
            "partial-dup-tr", "partial-dup-state", "partial-dup-result",
            ("partial-dup-fill",), "partial-dup-pnl")
        unchanged, duplicate_result = PaperTradeReplayCoordinator(service).evaluate(
            snapshot, duplicate)
        assert unchanged.to_json() == snapshot.to_json()
        assert duplicate_result.pnl_evidence is None
        assert Path(sys.argv[1]).read_bytes() == before
        at = NOW + timedelta(seconds=2)
        observation = make_observation(observation_id="partial-t2", observed_at=at,
            received_at=at, option_last_price=120., option_open=120., option_low=119.,
            option_high=121., option_close=120.)
        evaluation = PaperTradePositionEvaluationInputV1(snapshot.position,
            snapshot.lifecycle_policy, snapshot.lifecycle_state, observation, at,
            "partial-t2-tr", "partial-t2-state", "partial-t2-result",
            ("partial-t2-fill",), "partial-t2-pnl")
        updated, result = PaperTradeReplayCoordinator(service).evaluate(snapshot, evaluation)
        print(json.dumps({"state": result.status,
                          "fills": [fill.fill_id for fill in updated.position.exit_fills],
                          "remaining": updated.position.remaining_quantity,
                          "json": updated.to_json()}))
        """,
    )
    recovered = _run_python(
        path,
        """
        import json, sys
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import PaperTradePersistenceService, PaperTradeRecoveryService
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        recovery = PaperTradeRecoveryService(service)
        snapshot = recovery.recover()[0]
        print(json.dumps({"active": len(recovery.recover_active()),
                          "state": snapshot.lifecycle_state.current_state,
                          "fills": [fill.fill_id for fill in snapshot.position.exit_fills],
                          "json": snapshot.to_json()}))
        """,
    )

    assert advanced["state"] == recovered["state"] == "CLOSED_TARGET_2"
    assert advanced["fills"] == recovered["fills"] == [
        "partial-t1-fill",
        "partial-t2-fill",
    ]
    assert advanced["remaining"] == 0
    assert recovered["active"] == 0
    assert advanced["json"] == recovered["json"]


def test_fresh_process_recovers_stop_as_history_and_refuses_resume(tmp_path):
    path = tmp_path / "terminal.json"
    closed = _run_python(
        path,
        """
        import json, sys
        from datetime import timedelta
        from services.contracts import PaperTradePositionEvaluationInputV1
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import PaperTradePersistenceService, PaperTradeReplayCoordinator
        from tests.p7_fixture_helpers import NOW, make_observation, make_policy
        from tests.test_paper_trade_persistence_snapshot_v1 import make_snapshot
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        source = make_snapshot(lifecycle_policy=make_policy(allow_partial_exits=True))
        service.save(source)
        at = NOW + timedelta(seconds=1)
        observation = make_observation(observation_id="sub-stop", observed_at=at,
            received_at=at, option_last_price=90., option_open=90., option_low=89.,
            option_high=91., option_close=90.)
        evaluation = PaperTradePositionEvaluationInputV1(source.position,
            source.lifecycle_policy, source.lifecycle_state, observation, at,
            "sub-stop-tr", "sub-stop-state", "sub-stop-result",
            ("sub-stop-fill",), "sub-stop-pnl")
        updated, result = PaperTradeReplayCoordinator(service).evaluate(source, evaluation)
        print(json.dumps({"state": result.status,
                          "reason": updated.position.exit_fills[-1].fill_reason,
                          "json": updated.to_json()}))
        """,
    )
    recovered = _run_python(
        path,
        """
        import json, sys
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import (PaperTradePersistenceService,
            PaperTradeRecoveryService, PaperTradeReplayCoordinator)
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        recovery = PaperTradeRecoveryService(service)
        snapshot = recovery.recover()[0]
        refused = False
        try:
            PaperTradeReplayCoordinator(service).evaluate(snapshot, object())
        except ValueError as exc:
            refused = str(exc) == "terminal snapshot cannot resume"
        print(json.dumps({"active": len(recovery.recover_active()),
                          "state": snapshot.lifecycle_state.current_state,
                          "refused": refused, "json": snapshot.to_json()}))
        """,
    )

    assert closed["state"] == recovered["state"] == "CLOSED_STOP"
    assert closed["reason"] == "STOP"
    assert recovered["active"] == 0
    assert recovered["refused"] is True
    assert closed["json"] == recovered["json"]


def test_fresh_process_durable_idempotency_retry_and_conflict_are_read_only(tmp_path):
    path = tmp_path / "idempotency.json"
    first = _run_python(
        path,
        """
        import json, sys
        from services.contracts import PaperTradePositionEvaluationInputV1
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import (PaperTradePersistenceService,
            PaperTradingEngineAdapterInputV1, PaperTradingEngineAdapterV1)
        from services.paper_trading_engine import PaperTradingEngine
        from tests.p7_fixture_helpers import (NOW, make_observation, make_open_position,
            make_open_state, make_policy)
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        evaluation = PaperTradePositionEvaluationInputV1(make_open_position(),
            make_policy(allow_partial_exits=True), make_open_state(),
            make_observation(option_last_price=110., option_open=110., option_low=109.,
                option_high=111., option_close=110.), NOW, "idem-tr", "idem-state",
            "idem-eval", ("idem-fill",), "idem-pnl")
        request = PaperTradingEngineAdapterInputV1("idem-result", "idem-trade",
            "idem-key", "EVALUATE_POSITION", NOW, position_input=evaluation)
        result = PaperTradingEngineAdapterV1(PaperTradingEngine(), service).execute(request)
        print(json.dumps({"status": result.status, "duplicate": result.duplicate,
                          "hash": service.get("idem-trade").integrity_hash}))
        """,
    )
    retried = _run_python(
        path,
        """
        import json, sys
        from pathlib import Path
        from services.contracts import PaperTradePositionEvaluationInputV1
        from services.paper_trade_repository import PaperTradeRepository
        from services.paper_trading import (PaperTradePersistenceService,
            PaperTradingEngineAdapterInputV1, PaperTradingEngineAdapterV1)
        from services.paper_trading_engine import PaperTradingEngine
        from tests.p7_fixture_helpers import (NOW, make_observation, make_open_position,
            make_open_state, make_policy)
        service = PaperTradePersistenceService(PaperTradeRepository(sys.argv[1]))
        engine = PaperTradingEngine()
        adapter = PaperTradingEngineAdapterV1(engine, service)
        def request(observation):
            evaluation = PaperTradePositionEvaluationInputV1(make_open_position(),
                make_policy(allow_partial_exits=True), make_open_state(), observation,
                NOW, "idem-tr", "idem-state", "idem-eval", ("idem-fill",), "idem-pnl")
            return PaperTradingEngineAdapterInputV1("idem-result", "idem-trade",
                "idem-key", "EVALUATE_POSITION", NOW, position_input=evaluation)
        before = Path(sys.argv[1]).read_bytes()
        duplicate = adapter.execute(request(make_observation(option_last_price=110.,
            option_open=110., option_low=109., option_high=111., option_close=110.)))
        conflict = adapter.execute(request(make_observation(observation_id="idem-conflict",
            option_last_price=111., option_open=111., option_low=110.,
            option_high=112., option_close=111.)))
        after = Path(sys.argv[1]).read_bytes()
        print(json.dumps({"duplicate": duplicate.duplicate,
                          "conflict_status": conflict.status,
                          "blockers": list(conflict.blockers),
                          "unchanged": before == after,
                          "engine_trades": engine.count_trades(),
                          "hash": service.get("idem-trade").integrity_hash}))
        """,
    )

    assert first["status"] == "PARTIALLY_EXITED"
    assert first["duplicate"] is False
    assert retried["duplicate"] is True
    assert retried["conflict_status"] == "BLOCKED"
    assert retried["blockers"] == ["IDEMPOTENCY_PAYLOAD_CONFLICT"]
    assert retried["unchanged"] is True
    assert retried["engine_trades"] == 0
    assert retried["hash"] == first["hash"]
