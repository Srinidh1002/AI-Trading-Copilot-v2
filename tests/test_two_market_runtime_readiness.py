"""Deterministic offline readiness coverage for the NIFTY/SENSEX PAPER scope.

This module deliberately exercises the existing single-market certified child
contracts with two supplied replay snapshots.  It is not a replacement
two-market runtime or a parallel implementation of production orchestration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
    market_spec_for,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisAuthority,
    CertifiedLiveDataAuthority,
    CertifiedLiveOpportunityAuthority,
    CertifiedSessionAuthority,
)
from services.paper_orchestration.certified_runtime_safety import (
    CertifiedPaperRuntimeSafetyConfigV1,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "replay"


class ForbiddenBroker:
    """A network/order sentinel: any use is a test failure."""

    def __getattr__(self, name):
        raise AssertionError(f"broker access is forbidden in offline tests: {name}")

    def place_order(self, *args, **kwargs):
        raise AssertionError("place_order must not be invoked")

    def submit_order(self, *args, **kwargs):
        raise AssertionError("submit_order must not be invoked")

    def modify_order(self, *args, **kwargs):
        raise AssertionError("modify_order must not be invoked")

    def cancel_order(self, *args, **kwargs):
        raise AssertionError("cancel_order must not be invoked")


class OfflineAnalysisPipeline:
    def __init__(self):
        self.calls = []

    def analyse(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"spot_price": kwargs["spot_price"] if "spot_price" in kwargs else 1.0}


class OfflineOptionPipeline:
    def __init__(self):
        self.calls = []

    def analyse(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"decision": "NO_TRADE", "blockers": (), "warnings": ()}


class FixtureFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class OfflineMarketOutcome:
    identity: tuple[str, str]
    fixture_id: str
    status: str
    cycle_id: str | None
    option_exchange: str | None
    execution_mode: str
    live_execution_eligible: bool
    broker_order_submission: bool
    error_code: str | None = None


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _fixture_timestamp(replay: dict) -> datetime:
    return datetime.fromisoformat(replay["snapshot"]["market_timestamp"])


def _cycle_input(replay: dict):
    snapshot = replay["snapshot"]
    timestamp = _fixture_timestamp(replay)
    symbol = snapshot["symbol"]
    exchange = snapshot["exchange"]
    policy = PaperOrchestrationPolicyV1(
        orchestration_policy_id="two-market-offline-policy-2026-07-24",
        policy_timestamp=timestamp,
        emergency_paper_halt=False,
    )
    session = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=timestamp,
        evaluated_at=timestamp,
        id_factory=lambda: f"offline-session:{symbol}:{exchange}:2026-07-24T09:30:00",
    )
    return build_certified_cycle_input(
        cycle_kind="OPPORTUNITY",
        observation_id=f"offline-observation:{replay['fixture_id']}",
        orchestration_policy=policy,
        underlying_symbol=symbol,
        exchange=exchange,
        market_timestamp=timestamp,
        received_at=timestamp,
        cycle_requested_at=timestamp,
        session_validation=session,
        metadata={"spot_price": float(snapshot["ltp"]), "offline_replay": True},
    )


def _run_existing_certified_child_path(replay: dict) -> tuple[object, OfflineAnalysisPipeline, OfflineOptionPipeline]:
    """Invoke existing certified authorities with injected offline pipelines."""
    cycle_input = _cycle_input(replay)
    analysis_pipeline = OfflineAnalysisPipeline()
    option_pipeline = OfflineOptionPipeline()
    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *args: (_ for _ in ()).throw(
            AssertionError("quote_reader must not be used after cycle input creation")
        ),
        analysis_pipeline=analysis_pipeline,
        option_decision_pipeline=option_pipeline,
        available_capital=10_000.0,
    )
    data = CertifiedLiveDataAuthority(reader=readers.read_data)(cycle_input)
    session = CertifiedSessionAuthority()(cycle_input, data)
    parent_cycle_id = f"runtime-readiness-{replay['fixture_id']}"

    analysis = CertifiedLiveAnalysisAuthority(reader=readers.read_analysis)(
        cycle_input,
        data,
        session,
        parent_cycle_id=parent_cycle_id,
    )
    opportunity = CertifiedLiveOpportunityAuthority(reader=readers.read_opportunity)(
        cycle_input,
        analysis,
        session,
    )
    return opportunity, analysis_pipeline, option_pipeline


def _offline_outcome(replay: dict, *, fail: bool = False) -> OfflineMarketOutcome:
    """Fixture classifier used only to test deterministic offline readiness."""
    snapshot = replay["snapshot"]
    symbol = snapshot["symbol"]
    exchange = snapshot["exchange"]
    try:
        if fail:
            raise FixtureFailure("INJECTED_MARKET_FAILURE")
        spec = market_spec_for(symbol, exchange)
        cycle_input = _cycle_input(replay)
        if snapshot.get("is_stale") is True:
            status = "STALE"
        elif snapshot.get("option_chain", {}).get("status") == "UNAVAILABLE":
            status = "UNAVAILABLE"
        else:
            status = "READY"
        return OfflineMarketOutcome(
            identity=(spec.underlying_symbol, spec.exchange),
            fixture_id=replay["fixture_id"],
            status=status,
            cycle_id=cycle_input.cycle_id,
            option_exchange=spec.option_exchange,
            execution_mode=cycle_input.execution_mode,
            live_execution_eligible=cycle_input.orchestration_policy.live_execution_eligible,
            broker_order_submission=cycle_input.metadata["broker_order_submission"],
        )
    except FixtureFailure:
        return OfflineMarketOutcome(
            identity=(symbol, exchange),
            fixture_id=replay["fixture_id"],
            status="FAILED",
            cycle_id=None,
            option_exchange=None,
            execution_mode="PAPER",
            live_execution_eligible=False,
            broker_order_submission=False,
            error_code="INJECTED_MARKET_FAILURE",
        )


def _two_market_replay(*, nifty: dict, sensex: dict, fail_nifty: bool = False, fail_sensex: bool = False):
    """Test-only coordinator: evaluate supplied replay records independently."""
    return (
        _offline_outcome(nifty, fail=fail_nifty),
        _offline_outcome(sensex, fail=fail_sensex),
    )


@pytest.mark.parametrize(
    ("fixture_name", "identity", "option_exchange"),
    (
        ("nifty_bullish_valid.json", ("NIFTY", "NSE"), "NFO"),
        ("sensex_bullish_valid.json", ("SENSEX", "BSE"), "BFO"),
    ),
)
def test_valid_certified_market_identities_have_offline_child_paths(
    fixture_name,
    identity,
    option_exchange,
):
    replay = _fixture(fixture_name)

    opportunity, analysis_pipeline, option_pipeline = _run_existing_certified_child_path(replay)

    assert (opportunity.underlying_symbol, opportunity.exchange) == identity
    assert opportunity.opportunity_status == "NO_ACTION"
    assert len(analysis_pipeline.calls) == 1
    assert len(option_pipeline.calls) == 1
    assert option_pipeline.calls[0]["option_exchange"] == option_exchange
    assert option_pipeline.calls[0]["underlying"] == identity[0]
    assert option_pipeline.calls[0]["exchange"] == identity[1]


def test_unsupported_identity_fails_closed_before_any_broker_access():
    with pytest.raises(ValueError, match="NIFTY/NSE and SENSEX/BSE"):
        market_spec_for("BANKNIFTY", "NSE")


def test_broker_order_sentinel_fails_immediately_if_an_order_method_is_invoked():
    broker = ForbiddenBroker()

    for method_name in (
        "place_order",
        "submit_order",
        "modify_order",
        "cancel_order",
    ):
        with pytest.raises(AssertionError, match=method_name):
            getattr(broker, method_name)()


@pytest.mark.parametrize(
    ("nifty_fixture", "sensex_fixture", "expected"),
    (
        ("nifty_stale_blocked.json", "sensex_bullish_valid.json", ("STALE", "READY")),
        ("nifty_bullish_valid.json", "sensex_stale_blocked.json", ("READY", "STALE")),
        ("nifty_stale_blocked.json", "sensex_stale_blocked.json", ("STALE", "STALE")),
    ),
)
def test_stale_replay_statuses_are_market_specific(nifty_fixture, sensex_fixture, expected):
    outcomes = _two_market_replay(
        nifty=_fixture(nifty_fixture),
        sensex=_fixture(sensex_fixture),
    )

    assert tuple(outcome.status for outcome in outcomes) == expected
    assert tuple(outcome.identity for outcome in outcomes) == (("NIFTY", "NSE"), ("SENSEX", "BSE"))


@pytest.mark.parametrize(
    ("nifty_fixture", "sensex_fixture", "expected"),
    (
        ("nifty_missing_options.json", "sensex_bullish_valid.json", ("UNAVAILABLE", "READY")),
        ("nifty_bullish_valid.json", "sensex_missing_options.json", ("READY", "UNAVAILABLE")),
        ("nifty_missing_options.json", "sensex_missing_options.json", ("UNAVAILABLE", "UNAVAILABLE")),
    ),
)
def test_unavailable_replay_statuses_are_market_specific(nifty_fixture, sensex_fixture, expected):
    outcomes = _two_market_replay(
        nifty=_fixture(nifty_fixture),
        sensex=_fixture(sensex_fixture),
    )

    assert tuple(outcome.status for outcome in outcomes) == expected


def test_one_market_failure_is_isolated_from_the_other_market_replay():
    outcomes = _two_market_replay(
        nifty=_fixture("nifty_bullish_valid.json"),
        sensex=_fixture("sensex_bullish_valid.json"),
        fail_nifty=True,
    )

    nifty, sensex = outcomes
    assert nifty.status == "FAILED"
    assert nifty.error_code == "INJECTED_MARKET_FAILURE"
    assert sensex.status == "READY"
    assert sensex.identity == ("SENSEX", "BSE")


def test_offline_two_market_contracts_remain_paper_only_without_broker_submission():
    safety = CertifiedPaperRuntimeSafetyConfigV1(
        instruments=("NIFTY", "SENSEX"),
        observe_only=False,
    )
    outcomes = _two_market_replay(
        nifty=_fixture("nifty_bullish_valid.json"),
        sensex=_fixture("sensex_bullish_valid.json"),
    )

    assert safety.execution_mode == "PAPER"
    assert safety.live_execution_eligible is False
    assert safety.broker_order_submission is False
    assert all(outcome.execution_mode == "PAPER" for outcome in outcomes)
    assert all(outcome.live_execution_eligible is False for outcome in outcomes)
    assert all(outcome.broker_order_submission is False for outcome in outcomes)


def test_repeated_two_market_replay_is_deterministic_and_does_not_touch_broker_orders():
    first = _two_market_replay(
        nifty=_fixture("nifty_bullish_valid.json"),
        sensex=_fixture("sensex_bullish_valid.json"),
    )
    second = _two_market_replay(
        nifty=_fixture("nifty_bullish_valid.json"),
        sensex=_fixture("sensex_bullish_valid.json"),
    )

    assert first == second
    assert [outcome.cycle_id for outcome in first] == [
        outcome.cycle_id for outcome in second
    ]
