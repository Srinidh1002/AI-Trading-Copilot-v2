"""Reusable constructor-backed harness for real P7 persistence/replay tests.

The harness deliberately goes through ``PaperTradeRepository`` and the public
WP4 services.  A continuation input always references the exact position,
lifecycle policy, and lifecycle state recovered from the preceding snapshot.
Only the next caller-owned observation, IDs, and timestamps are constructed.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from services.contracts import (
    PaperTradePersistenceSnapshotV1,
    PaperTradePositionEvaluationInputV1,
)
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading import (
    PaperTradePersistenceService,
    PaperTradeRecoveryService,
    PaperTradeReplayCoordinator,
    evaluate_paper_trade_entry,
)
from tests.p7_fixture_helpers import (
    NOW,
    make_entry_input,
    make_integrated,
    make_observation,
    make_open_state,
    make_policy,
)


@dataclass(frozen=True, slots=True)
class ReplayStepIds:
    """Every caller-owned identity and timestamp for one replay step."""

    label: str
    observation_id: str
    observed_at: datetime
    received_at: datetime
    evaluation_timestamp: datetime
    requested_transition_id: str
    resulting_lifecycle_state_id: str
    evaluation_result_id: str
    exit_fill_ids: tuple[str, ...]
    pnl_evidence_id: str

    @classmethod
    def at(
        cls,
        label: str,
        seconds: int = 1,
        *,
        timestamp: datetime | None = None,
        fill_count: int = 4,
    ) -> "ReplayStepIds":
        if type(label) is not str or not label.strip():
            raise ValueError("label")
        if type(seconds) is not int or isinstance(seconds, bool) or seconds < 0:
            raise ValueError("seconds")
        if type(fill_count) is not int or isinstance(fill_count, bool) or fill_count < 1:
            raise ValueError("fill_count")
        label = label.strip()
        moment = timestamp if timestamp is not None else NOW + timedelta(seconds=seconds)
        if not isinstance(moment, datetime) or moment.tzinfo is None:
            raise ValueError("timestamp")
        slug = label.lower().replace(" ", "-")
        return cls(
            label=label,
            observation_id=f"{slug}-observation",
            observed_at=moment,
            received_at=moment,
            evaluation_timestamp=moment,
            requested_transition_id=f"{slug}-transition",
            resulting_lifecycle_state_id=f"{slug}-state",
            evaluation_result_id=f"{slug}-result",
            exit_fill_ids=tuple(f"{slug}-fill-{index}" for index in range(1, fill_count + 1)),
            pnl_evidence_id=f"{slug}-pnl",
        )


@dataclass(frozen=True, slots=True)
class ReplayFixtureProfile:
    name: str
    integrated_trade_plan_result: Any
    entry_observation: Any
    initial_snapshot: PaperTradePersistenceSnapshotV1


@dataclass(frozen=True, slots=True)
class ReplayTraceStep:
    action: str
    label: str
    paper_trade_id: str
    lifecycle_state: str
    event_sequence: int
    canonical_json: str


_PROFILE_SPECS = {
    "three_target": dict(
        symbol="NIFTY26JAN24000CE", underlying="NIFTY", exchange="NSE",
        direction="BULLISH", allocations=(1, 1, 1, 0), runner_close_mode="TARGET_3",
    ),
    "t2_terminal": dict(
        symbol="NIFTY26JAN24000CE", underlying="NIFTY", exchange="NSE",
        direction="BULLISH", allocations=(1, 1, 0, 0), runner_close_mode="TARGET_3",
    ),
    "runner": dict(
        symbol="NIFTY26JAN24000CE", underlying="NIFTY", exchange="NSE",
        direction="BULLISH", allocations=(1, 1, 1, 1), runner_close_mode="TARGET_3",
    ),
    "simple_terminal": dict(
        symbol="NIFTY26JAN24000CE", underlying="NIFTY", exchange="NSE",
        direction="BULLISH", allocations=(1, 0, 0, 0), runner_close_mode="TARGET_3",
    ),
    "nifty_call": dict(
        symbol="NIFTY26JAN24000CE", underlying="NIFTY", exchange="NSE",
        direction="BULLISH", allocations=(1, 1, 0, 0), runner_close_mode="TARGET_3",
    ),
    "nifty_put": dict(
        symbol="NIFTY26JAN24000PE", underlying="NIFTY", exchange="NSE",
        direction="BEARISH", allocations=(1, 1, 0, 0), runner_close_mode="TARGET_3",
    ),
    "sensex": dict(
        symbol="SENSEX26JAN24000CE", underlying="SENSEX", exchange="BSE",
        direction="BULLISH", allocations=(1, 1, 0, 0), runner_close_mode="TARGET_3",
    ),
}


def make_replay_profile(name: str) -> ReplayFixtureProfile:
    """Construct one canonical OPEN snapshot from a real P6J plan and entry."""

    if name not in _PROFILE_SPECS:
        raise ValueError(f"unsupported replay profile: {name}")
    spec = _PROFILE_SPECS[name]
    plan = make_integrated(
        symbol=spec["symbol"],
        underlying=spec["underlying"],
        exchange=spec["exchange"],
        direction=spec["direction"],
    )
    allocations = spec["allocations"]
    planned_lots = sum(allocations)
    lot_size = plan.capital_quantity_result.lot_size
    estimated_premium_outlay = planned_lots * 2500.0
    estimated_total_trading_cost = planned_lots * 25.0
    capital = replace(
        plan.capital_quantity_result,
        upstream_affordable_lot_limit=max(planned_lots, 2),
        planned_lot_count=planned_lots,
        planned_quantity=planned_lots * lot_size,
        estimated_premium_outlay=estimated_premium_outlay,
        estimated_risk_amount=planned_lots * 250.0,
        target_1_lot_count=allocations[0],
        target_2_lot_count=allocations[1],
        target_3_lot_count=allocations[2],
        runner_lot_count=allocations[3],
        trading_cost_policy_id=f"{name}-cost-policy",
        trading_cost_evidence_id=f"{name}-cost-evidence",
        trading_cost_calculation_mode="P6J_TEST_EVIDENCE",
        estimated_brokerage=planned_lots * 10.0,
        estimated_exchange_transaction_charges=planned_lots * 3.0,
        estimated_clearing_charges=planned_lots * 1.0,
        estimated_stt=planned_lots * 4.0,
        estimated_sebi_charges=planned_lots * 1.0,
        estimated_stamp_duty=planned_lots * 2.0,
        estimated_gst=planned_lots * 2.0,
        estimated_slippage=planned_lots * 2.0,
        estimated_total_trading_cost=estimated_total_trading_cost,
        estimated_total_capital_requirement=(
            estimated_premium_outlay + estimated_total_trading_cost
        ),
        cost_adjusted_capital_feasible=True,
    )
    plan = replace(plan, capital_quantity_result=capital)
    policy = make_policy(
        entry_activation_mode="PREFERRED_ENTRY_TOUCH",
        allow_partial_exits=planned_lots > 1,
        runner_enabled=allocations[3] > 0,
        runner_close_mode=spec["runner_close_mode"],
        metadata={"replay_profile": name},
    )
    entry_observation = make_observation(
        observation_id=f"{name}-entry-observation",
        underlying_symbol=spec["underlying"],
        option_symbol=spec["symbol"],
        market=spec["underlying"],
        exchange="BFO" if spec["underlying"] == "SENSEX" else "NFO",
        option_open=100.0,
        option_low=99.0,
        option_high=101.0,
        option_close=100.0,
        metadata={"replay_profile": name},
    )
    entry = evaluate_paper_trade_entry(
        make_entry_input(
            integrated_trade_plan_result=plan,
            lifecycle_policy=policy,
            observation=entry_observation,
            requested_transition_id=f"{name}-entry-transition",
            position_id=f"{name}-position",
            entry_fill_id=f"{name}-entry-fill",
            metadata={"replay_profile": name},
        )
    )
    if entry.position is None:
        raise AssertionError(f"{name} profile did not activate an OPEN position")
    open_state = replace(
        make_open_state(),
        lifecycle_state_id=f"{name}-open-state",
        last_transition_code=f"{name}-entry-transition",
        last_observation_id=entry_observation.observation_id,
        last_observation_timestamp=entry_observation.observed_at,
        metadata={"replay_profile": name},
    )
    snapshot = PaperTradePersistenceSnapshotV1(
        paper_trade_id=f"{name}-paper-trade",
        adapter_idempotency_key=f"{name}-idempotency-key",
        idempotency_payload_hash=hashlib.sha256(name.encode("utf-8")).hexdigest(),
        lifecycle_policy=policy,
        lifecycle_state=open_state,
        position=entry.position,
        latest_observation=entry_observation,
        pnl_evidence=None,
        created_at=NOW,
        updated_at=NOW,
        event_sequence=1,
    )
    return ReplayFixtureProfile(name, plan, entry_observation, snapshot)


class ReplayHarness:
    """Real-repository orchestration for deterministic restart scenarios."""

    def __init__(self, temporary_root: str | Path, profile: str | ReplayFixtureProfile = "three_target"):
        self.profile = make_replay_profile(profile) if isinstance(profile, str) else profile
        if type(self.profile) is not ReplayFixtureProfile:
            raise TypeError("profile")
        root = Path(temporary_root)
        self.repository_path = root if root.suffix == ".json" else root / f"{self.profile.name}-replay.json"
        self.repository = PaperTradeRepository(self.repository_path)
        self.persistence = PaperTradePersistenceService(self.repository)
        self.recovery = PaperTradeRecoveryService(self.persistence)
        self.coordinator = PaperTradeReplayCoordinator(self.persistence)
        self._trace: list[ReplayTraceStep] = []

    @property
    def trace(self) -> tuple[ReplayTraceStep, ...]:
        return tuple(self._trace)

    def _record(self, action: str, label: str, snapshot: PaperTradePersistenceSnapshotV1) -> None:
        self._trace.append(
            ReplayTraceStep(
                action,
                label,
                snapshot.paper_trade_id,
                snapshot.lifecycle_state.current_state,
                snapshot.event_sequence,
                snapshot.to_json(),
            )
        )

    def persist(self, snapshot: PaperTradePersistenceSnapshotV1 | None = None) -> PaperTradePersistenceSnapshotV1:
        source = self.profile.initial_snapshot if snapshot is None else snapshot
        saved = self.persistence.save(source)
        self._record("PERSIST", "persist", saved)
        return saved

    def recover(
        self,
        *,
        paper_trade_id: str | None = None,
        position_id: str | None = None,
        trade_plan_id: str | None = None,
        include_terminal: bool = True,
    ) -> PaperTradePersistenceSnapshotV1:
        identities = sum(value is not None for value in (paper_trade_id, position_id, trade_plan_id))
        if identities > 1:
            raise ValueError("select one recovery identity")
        if paper_trade_id is not None:
            snapshot = self.persistence.get(paper_trade_id)
            matches = () if snapshot is None else (snapshot,)
        elif trade_plan_id is not None:
            matches = self.persistence.get_by_trade_plan_id(trade_plan_id)
        else:
            matches = self.recovery.recover(include_terminal=include_terminal)
            if position_id is not None:
                matches = tuple(
                    item for item in matches
                    if item.position is not None and item.position.position_id == position_id
                )
        if not include_terminal:
            matches = tuple(item for item in matches if not item.lifecycle_state.is_terminal)
        if len(matches) != 1:
            raise LookupError(f"expected one recovered snapshot, found {len(matches)}")
        snapshot = matches[0]
        self._record("RECOVER", "recover", snapshot)
        return snapshot

    def recover_active(self) -> tuple[PaperTradePersistenceSnapshotV1, ...]:
        snapshots = self.recovery.recover_active()
        for snapshot in snapshots:
            self._record("RECOVER_ACTIVE", "recover-active", snapshot)
        return snapshots

    def recover_history(self) -> tuple[PaperTradePersistenceSnapshotV1, ...]:
        snapshots = tuple(item for item in self.recovery.recover() if item.lifecycle_state.is_terminal)
        for snapshot in snapshots:
            self._record("RECOVER_HISTORY", "recover-history", snapshot)
        return snapshots

    def fresh_recover(self, paper_trade_id: str | None = None) -> PaperTradePersistenceSnapshotV1:
        service = PaperTradePersistenceService(PaperTradeRepository(self.repository_path))
        recovery = PaperTradeRecoveryService(service)
        if paper_trade_id is not None:
            snapshot = service.get(paper_trade_id)
            if snapshot is None:
                raise LookupError(paper_trade_id)
        else:
            snapshots = recovery.recover()
            if len(snapshots) != 1:
                raise LookupError(f"expected one recovered snapshot, found {len(snapshots)}")
            snapshot = snapshots[0]
        self._record("FRESH_RECOVER", "fresh-recover", snapshot)
        return snapshot

    def build_observation(
        self,
        snapshot: PaperTradePersistenceSnapshotV1,
        step: ReplayStepIds,
        *,
        option_price: float = 100.0,
        **changes: Any,
    ):
        if snapshot.latest_observation is None or snapshot.position is None:
            raise ValueError("replay requires recovered observation and position evidence")
        values = dict(
            observation_id=step.observation_id,
            observed_at=step.observed_at,
            received_at=step.received_at,
            market_session_date=step.observed_at.date(),
            option_last_price=option_price,
            option_open=option_price,
            option_low=max(0.01, option_price - 1.0),
            option_high=option_price + 1.0,
            option_close=option_price,
            is_expiry_session=step.observed_at.date() >= datetime.fromisoformat(
                snapshot.position.expiry + "T00:00:00+00:00"
            ).date(),
        )
        values.update(changes)
        return replace(snapshot.latest_observation, **values)

    def build_input(
        self,
        snapshot: PaperTradePersistenceSnapshotV1,
        step: ReplayStepIds,
        *,
        observation=None,
        option_price: float = 100.0,
        observation_changes: Mapping[str, Any] | None = None,
        input_changes: Mapping[str, Any] | None = None,
    ) -> PaperTradePositionEvaluationInputV1:
        if snapshot.position is None:
            raise ValueError("snapshot has no resumable position")
        if snapshot.lifecycle_state.is_terminal:
            raise ValueError("terminal snapshot cannot resume")
        if observation is None:
            observation = self.build_observation(
                snapshot,
                step,
                option_price=option_price,
                **dict(observation_changes or {}),
            )
        values = dict(
            position=snapshot.position,
            lifecycle_policy=snapshot.lifecycle_policy,
            lifecycle_state=snapshot.lifecycle_state,
            observation=observation,
            evaluation_timestamp=step.evaluation_timestamp,
            requested_transition_id=step.requested_transition_id,
            resulting_lifecycle_state_id=step.resulting_lifecycle_state_id,
            evaluation_result_id=step.evaluation_result_id,
            exit_fill_ids=step.exit_fill_ids,
            pnl_evidence_id=step.pnl_evidence_id,
            metadata={"replay_step": step.label},
        )
        values.update(dict(input_changes or {}))
        return PaperTradePositionEvaluationInputV1(**values)

    def evaluate_input(self, snapshot, evaluation_input, *, label: str = "evaluate"):
        updated, result = self.coordinator.evaluate(snapshot, evaluation_input)
        self._record("EVALUATE", label, updated)
        return updated, result

    def evaluate(self, snapshot, step: ReplayStepIds, **changes):
        evaluation_input = self.build_input(snapshot, step, **changes)
        return self.evaluate_input(snapshot, evaluation_input, label=step.label)

    def repository_bytes(self) -> bytes:
        return self.repository_path.read_bytes()

    @staticmethod
    def assert_snapshot_exact(expected, actual) -> None:
        assert actual == expected
        assert actual.to_dict() == expected.to_dict()
        assert actual.to_json() == expected.to_json()
        assert actual.integrity_hash == expected.integrity_hash

    @staticmethod
    def economic_fingerprint(snapshot) -> tuple[Any, ...]:
        position = snapshot.position
        pnl = snapshot.pnl_evidence
        return (
            None if position is None else position.remaining_lot_count,
            None if position is None else position.remaining_quantity,
            () if position is None else tuple(fill.to_json() for fill in position.exit_fills),
            None if position is None else position.realized_gross_pnl,
            None if position is None else position.realized_net_pnl,
            None if position is None else position.unrealized_pnl,
            None if position is None else position.total_pnl,
            None if pnl is None else pnl.pnl_evidence_id,
            snapshot.lifecycle_state.transition_sequence,
            snapshot.event_sequence,
        )

    @classmethod
    def assert_economic_no_change(cls, before, after, result=None) -> None:
        cls.assert_snapshot_exact(before, after)
        assert cls.economic_fingerprint(after) == cls.economic_fingerprint(before)
        if result is not None:
            assert result.generated_exit_fills == ()
            assert result.pnl_evidence is None
            assert result.resulting_position is before.position
            assert result.resulting_lifecycle_state is before.lifecycle_state


__all__ = [
    "ReplayFixtureProfile",
    "ReplayHarness",
    "ReplayStepIds",
    "ReplayTraceStep",
    "make_replay_profile",
]
