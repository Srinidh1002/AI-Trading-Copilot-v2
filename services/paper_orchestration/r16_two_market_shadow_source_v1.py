"""R16 exact-two-index shadow parent cycle source.

Builds one coherent NIFTY/SENSEX opportunity parent from already-supplied
read-only market readers. The source performs no planning, PAPER entry,
position mutation, broker submission, or live execution.

This is intentionally SHADOW_ONLY. Promotion to entry authority is a separate
strategy-version/epoch decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
    market_spec_for,
)
from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_parent_cycle,
)


@dataclass(frozen=True, slots=True)
class R16TwoMarketShadowCycleV1:
    parent: TwoMarketParentCycleInputV1
    nifty_cycle: object
    sensex_cycle: object
    decision: object
    mode: str = "SHADOW_ONLY"
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.mode != "SHADOW_ONLY":
            raise ValueError("mode")
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("shadow PAPER-only boundary")


class R16TwoMarketShadowSourceV1:
    """Build and evaluate exactly one NIFTY and one SENSEX child per call."""

    def __init__(
        self,
        *,
        readers: CertifiedLiveProviderReaders,
        clock,
        interval_seconds: float = 60.0,
        max_candidate_age_seconds: float = 180.0,
        max_timestamp_skew_seconds: float = 5.0,
    ) -> None:
        if type(readers) is not CertifiedLiveProviderReaders:
            raise TypeError("readers")
        if not callable(clock):
            raise TypeError("clock")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds")
        self.readers = readers
        self.clock = clock
        self.interval_seconds = float(interval_seconds)
        self.decision_policy = TwoMarketDecisionPolicyV1(
            max_candidate_age_seconds=max_candidate_age_seconds,
            max_timestamp_skew_seconds=max_timestamp_skew_seconds,
        )
        self._lock = RLock()
        self._sequence = 0

    def _next_sequence(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    @staticmethod
    def _aware(value: object, name: str) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(name)
        return value

    def _read_child_quote(self, market: str, exchange: str):
        spec = market_spec_for(market, exchange)
        raw = self.readers.quote_reader(
            spec.exchange,
            spec.symboltoken,
            spec.underlying_symbol,
        )
        if not isinstance(raw, dict):
            try:
                raw = dict(raw)
            except Exception as exc:
                raise TypeError("quote_reader must return mapping") from exc

        market_timestamp = self._aware(
            raw.get("market_timestamp"),
            f"{market}.market_timestamp",
        )
        received_at = self._aware(
            raw.get("received_at"),
            f"{market}.received_at",
        )
        if received_at < market_timestamp:
            raise ValueError(f"{market}.received_at before market_timestamp")

        spot = raw.get("spot_price", raw.get("ltp", raw.get("last_price")))
        if (
            isinstance(spot, bool)
            or not isinstance(spot, (int, float))
            or float(spot) <= 0
        ):
            raise ValueError(f"{market}.spot_price")

        return spec, raw, market_timestamp, received_at, float(spot)

    def build_inputs(self):
        """Read both quotes exactly once and create one coherent parent."""

        sequence = self._next_sequence()
        policy_timestamp = self._aware(self.clock(), "clock")

        nifty = self._read_child_quote("NIFTY", "NSE")
        sensex = self._read_child_quote("SENSEX", "BSE")

        latest_received = max(nifty[3], sensex[3])
        cycle_requested_at = self._aware(self.clock(), "clock")
        if cycle_requested_at < latest_received:
            cycle_requested_at = latest_received

        orchestration_policy = PaperOrchestrationPolicyV1(
            orchestration_policy_id=(
                f"r16-shadow-paper-policy-{cycle_requested_at.date().isoformat()}"
            ),
            policy_timestamp=policy_timestamp,
            observation_frequency_seconds=self.interval_seconds,
            emergency_paper_halt=False,
            metadata={
                "composition": "R16_TWO_MARKET_SHADOW_V1",
                "shadow_only": True,
                "broker_order_submission": False,
            },
        )

        children = {}
        for market, values in (("NIFTY", nifty), ("SENSEX", sensex)):
            spec, raw, market_timestamp, received_at, spot = values

            session = validate_session_timestamp(
                symbol=spec.underlying_symbol,
                exchange=spec.exchange,
                market_timestamp=market_timestamp,
                evaluated_at=received_at,
                validation_mode="LENIENT_ANALYSIS",
                id_factory=lambda m=market: (
                    f"r16-shadow-session-{sequence}-{m.lower()}"
                ),
            )
            observation_id = (
                f"r16-shadow-{sequence}-{market.lower()}-"
                f"{market_timestamp.isoformat()}"
            )
            children[market] = build_certified_cycle_input(
                cycle_kind="OPPORTUNITY",
                observation_id=observation_id,
                orchestration_policy=orchestration_policy,
                underlying_symbol=spec.underlying_symbol,
                exchange=spec.exchange,
                market_timestamp=market_timestamp,
                received_at=received_at,
                cycle_requested_at=cycle_requested_at,
                session_validation=session,
                metadata={
                    "composition": "R16_TWO_MARKET_SHADOW_V1",
                    "shadow_only": True,
                    "sequence": sequence,
                    "spot_price": spot,
                    "timestamp_source": raw.get("timestamp_source"),
                    "captured_spot_payload": {
                        "spot_price": spot,
                        "timestamp_source": raw.get("timestamp_source"),
                    },
                    "execution_mode": "PAPER",
                },
            )

        completed_at = max(
            cycle_requested_at,
            nifty[3],
            sensex[3],
        )
        parent_id = f"r16-two-market-shadow-parent-{sequence}"

        parent = TwoMarketParentCycleInputV1(
            parent_cycle_id=parent_id,
            decision_result_id=f"{parent_id}:decision",
            nifty_child_result_id=f"{parent_id}:child:NIFTY",
            sensex_child_result_id=f"{parent_id}:child:SENSEX",
            nifty_observation_id=children["NIFTY"].observation_id,
            sensex_observation_id=children["SENSEX"].observation_id,
            requested_at=cycle_requested_at,
            completed_at=completed_at,
            decision_policy=self.decision_policy,
        )

        return parent, children["NIFTY"], children["SENSEX"]

    def run_shadow_cycle(
        self,
        *,
        parent_journal_adapter=None,
        prediction_ledger=None,
        prediction_lifecycle_context_store=None,
        pre_entry_actions=None,
        prediction_records_sink=None,
        substage_callback=None,
    ) -> R16TwoMarketShadowCycleV1:
        parent, nifty_cycle, sensex_cycle = self.build_inputs()

        decision = run_authoritative_two_market_parent_cycle(
            parent,
            nifty_cycle=nifty_cycle,
            sensex_cycle=sensex_cycle,
            readers=self.readers,
            parent_journal_adapter=parent_journal_adapter,
            prediction_ledger=prediction_ledger,
            prediction_lifecycle_context_store=prediction_lifecycle_context_store,
            pre_entry_actions=pre_entry_actions,
            prediction_records_sink=prediction_records_sink,
            substage_callback=substage_callback,
        )

        return R16TwoMarketShadowCycleV1(
            parent=parent,
            nifty_cycle=nifty_cycle,
            sensex_cycle=sensex_cycle,
            decision=decision,
        )
