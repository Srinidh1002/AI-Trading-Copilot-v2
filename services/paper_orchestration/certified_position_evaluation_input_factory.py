from __future__ import annotations

import hashlib
from dataclasses import replace

from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
)
from services.paper_orchestration.certified_live_option_quote_reader import (
    CertifiedLiveOptionQuoteV1,
)


def _identity(namespace: str, *parts: object) -> str:
    payload = "|".join(
        (
            namespace,
            *(str(part).strip() for part in parts),
        )
    )
    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:24]
    return f"{namespace}-{digest}"


def _positive_float(
    value: object,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")

    if type(value) not in {
        int,
        float,
    }:
        raise TypeError(f"{name} must be numeric")

    result = float(value)

    if result <= 0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return result


def _current_underlying_price(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    prior_observation: PaperMarketObservationV1,
    position_underlying_symbol: str,
) -> float:
    value = None

    if (
        cycle_input.underlying_symbol
        == position_underlying_symbol
    ):
        value = cycle_input.metadata.get("spot_price")

        if value is None:
            captured = cycle_input.metadata.get(
                "captured_spot_payload"
            )

            if isinstance(captured, dict):
                value = captured.get(
                    "spot_price",
                    captured.get("ltp"),
                )

    if value is None:
        value = prior_observation.underlying_last_price

    return _positive_float(
        value,
        "underlying_last_price",
    )


class CertifiedPositionEvaluationInputFactory:
    """Build exact P7 monitoring evidence from one persisted active trade."""

    def __call__(
        self,
        *,
        cycle_input: PaperOrchestrationCycleInputV1,
        snapshot: PaperTradePersistenceSnapshotV1,
        quote: CertifiedLiveOptionQuoteV1,
    ) -> PaperTradePositionEvaluationInputV1:
        if type(cycle_input) is not PaperOrchestrationCycleInputV1:
            raise TypeError(
                "cycle_input must be exact "
                "PaperOrchestrationCycleInputV1"
            )

        if type(snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError(
                "snapshot must be exact "
                "PaperTradePersistenceSnapshotV1"
            )

        if type(quote) is not CertifiedLiveOptionQuoteV1:
            raise TypeError(
                "quote must be exact CertifiedLiveOptionQuoteV1"
            )

        position = snapshot.position
        prior_observation = snapshot.latest_observation

        if position is None:
            raise ValueError(
                "evaluation input requires a persisted position"
            )

        if prior_observation is None:
            raise ValueError(
                "evaluation input requires a prior observation"
            )

        if snapshot.lifecycle_state.is_terminal:
            raise ValueError(
                "terminal PAPER position must not be evaluated"
            )

        if position.lifecycle_state not in {
            "OPEN",
            "PARTIALLY_EXITED",
        }:
            raise ValueError(
                "only active PAPER positions may be evaluated"
            )

        quote_identity = (
            quote.paper_trade_id,
            quote.position_id,
            quote.underlying_symbol,
            quote.option_symbol,
        )

        persisted_identity = (
            snapshot.paper_trade_id,
            position.position_id,
            position.underlying_symbol,
            position.option_symbol,
        )

        if quote_identity != persisted_identity:
            raise ValueError(
                "quote identity does not match persisted P7 position"
            )

        if quote.provider_timestamp > cycle_input.cycle_requested_at:
            raise ValueError(
                "quote timestamp cannot follow cycle_requested_at"
            )

        if cycle_input.received_at < cycle_input.market_timestamp:
            raise ValueError(
                "cycle received_at cannot precede market_timestamp"
            )

        basis = (
            cycle_input.cycle_id,
            cycle_input.cycle_idempotency_key,
            snapshot.paper_trade_id,
            position.position_id,
        )

        observation_id = _identity(
            "monitoring-observation",
            *basis,
        )

        observation = replace(
            prior_observation,
            observation_id=observation_id,
            observed_at=cycle_input.market_timestamp,
            received_at=cycle_input.received_at,
            market_session_date=(
                cycle_input.market_timestamp.date()
            ),
            underlying_symbol=position.underlying_symbol,
            underlying_last_price=_current_underlying_price(
                cycle_input=cycle_input,
                prior_observation=prior_observation,
                position_underlying_symbol=(
                    position.underlying_symbol
                ),
            ),
            option_symbol=position.option_symbol,
            option_last_price=quote.option_last_price,
            market=position.market,
            exchange=quote.option_exchange,
            option_open=None,
            option_high=None,
            option_low=None,
            option_close=None,
            bid_price=None,
            ask_price=None,
            source="CERTIFIED_LIVE_OPTION_LTP",
            source_timestamps={
                "cycle_market_timestamp": (
                    cycle_input.market_timestamp
                ),
                "cycle_received_at": (
                    cycle_input.received_at
                ),
                "quote_provider_timestamp": (
                    quote.provider_timestamp
                ),
            },
            metadata={
                "paper_trade_id": snapshot.paper_trade_id,
                "position_id": position.position_id,
                "symboltoken": quote.symboltoken,
                "cycle_id": cycle_input.cycle_id,
                "broker_order_submission": False,
            },
        )

        exit_fill_ids = tuple(
            _identity(
                f"monitoring-exit-fill-{index}",
                *basis,
            )
            for index in range(1, 9)
        )

        return PaperTradePositionEvaluationInputV1(
            position=position,
            lifecycle_policy=snapshot.lifecycle_policy,
            lifecycle_state=snapshot.lifecycle_state,
            observation=observation,
            evaluation_timestamp=(
                cycle_input.cycle_requested_at
            ),
            requested_transition_id=_identity(
                "monitoring-transition",
                *basis,
            ),
            resulting_lifecycle_state_id=_identity(
                "monitoring-lifecycle-state",
                *basis,
            ),
            evaluation_result_id=_identity(
                "monitoring-evaluation-result",
                *basis,
            ),
            exit_fill_ids=exit_fill_ids,
            pnl_evidence_id=_identity(
                "monitoring-pnl-evidence",
                *basis,
            ),
            metadata={
                "paper_trade_id": snapshot.paper_trade_id,
                "position_id": position.position_id,
                "cycle_id": cycle_input.cycle_id,
                "quote_symboltoken": quote.symboltoken,
                "execution_mode": "PAPER",
                "broker_order_submission": False,
            },
        )