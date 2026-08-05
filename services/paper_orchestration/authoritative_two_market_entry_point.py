"""Single authoritative live two-market PAPER entry point."""
from __future__ import annotations

from collections.abc import Mapping
import math
from datetime import datetime

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)
from services.paper_orchestration.certified_two_market_parent_runtime import (
    run_certified_two_market_parent_runtime,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_orchestration.prediction_record_projector import (
    project_parent_decision_predictions,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    P6StageAuthority,
    SelectedMarketP6PlanningResultV1,
    execute_selected_market_p6_planning,
)
from services.paper_orchestration.two_market_parent_cycle_journal_adapter import (
    TwoMarketParentCycleJournalAdapter,
)


def _cycle_start_price(cycle: PaperOrchestrationCycleInputV1) -> float:
    value = cycle.metadata.get("spot_price")
    if value is None:
        captured = cycle.metadata.get("captured_spot_payload")
        if isinstance(captured, Mapping):
            value = captured.get("spot_price", captured.get("ltp"))
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{cycle.underlying_symbol} start spot price unavailable")
    return float(value)


AUTHORITATIVE_TWO_MARKET_ENTRY_POINT_ID = (
    "CERTIFIED_TWO_MARKET_PARENT_RUNTIME_V1"
)


def run_authoritative_two_market_parent_cycle(
    parent: TwoMarketParentCycleInputV1,
    *,
    nifty_cycle: PaperOrchestrationCycleInputV1,
    sensex_cycle: PaperOrchestrationCycleInputV1,
    readers: CertifiedLiveProviderReaders,
    parent_journal_adapter: (
        TwoMarketParentCycleJournalAdapter | None
    ) = None,
    prediction_ledger: PredictionLedger | None = None,
    substage_callback=None,
) -> TwoMarketDecisionResultV1:
    """Execute the approved NIFTY/SENSEX PAPER parent path.

    When persistence boundaries are supplied, the exact parent decision is
    journaled and exactly two immutable prediction records are retained.
    """

    if type(parent) is not TwoMarketParentCycleInputV1:
        raise TypeError("parent")
    if type(nifty_cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("nifty_cycle")
    if type(sensex_cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("sensex_cycle")
    if type(readers) is not CertifiedLiveProviderReaders:
        raise TypeError("readers")

    if parent.execution_mode != "PAPER":
        raise ValueError("parent must remain PAPER")
    if parent.live_execution_eligible:
        raise ValueError("parent cannot be live eligible")
    if parent.broker_order_submission:
        raise ValueError(
            "broker order submission must remain disabled"
        )

    if (
        parent_journal_adapter is not None
        and type(parent_journal_adapter)
        is not TwoMarketParentCycleJournalAdapter
    ):
        raise TypeError("parent_journal_adapter")
    if (
        prediction_ledger is not None
        and type(prediction_ledger) is not PredictionLedger
    ):
        raise TypeError("prediction_ledger")

    decision = run_certified_two_market_parent_runtime(
        parent,
        nifty_cycle=nifty_cycle,
        sensex_cycle=sensex_cycle,
        readers=readers,
        substage_callback=substage_callback,
    )

    prediction_records = (
        project_parent_decision_predictions(
            decision,
            start_underlying_prices={
                ("NIFTY", "NSE"): _cycle_start_price(nifty_cycle),
                ("SENSEX", "BSE"): _cycle_start_price(sensex_cycle),
            },
        )
        if prediction_ledger is not None
        else None
    )

    if parent_journal_adapter is not None:
        parent_journal_adapter.persist(
            parent=parent,
            decision=decision,
        )

    if (
        prediction_ledger is not None
        and prediction_records is not None
    ):
        prediction_ledger.save_pair(
            prediction_records
        )

    return decision


def run_authoritative_two_market_selected_p6_cycle(
    parent: TwoMarketParentCycleInputV1,
    *,
    nifty_cycle: PaperOrchestrationCycleInputV1,
    sensex_cycle: PaperOrchestrationCycleInputV1,
    readers: CertifiedLiveProviderReaders,
    bridge_result_id: str,
    evaluated_at: datetime,
    maximum_candidate_age_seconds: float,
    certified_p6_input_bundles: Mapping[
        tuple[str, str],
        CertifiedP6InputBundleV1,
    ],
    parent_journal_adapter: (
        TwoMarketParentCycleJournalAdapter | None
    ) = None,
    prediction_ledger: PredictionLedger | None = None,
    p6_stage_authority: P6StageAuthority | None = None,
    substage_callback=None,
) -> SelectedMarketP6PlanningResultV1:
    """Run the parent once, persist predictions, then route selected P6."""

    if not isinstance(
        certified_p6_input_bundles,
        Mapping,
    ):
        raise TypeError(
            "certified_p6_input_bundles"
        )

    decision = run_authoritative_two_market_parent_cycle(
        parent,
        nifty_cycle=nifty_cycle,
        sensex_cycle=sensex_cycle,
        readers=readers,
        parent_journal_adapter=parent_journal_adapter,
        prediction_ledger=prediction_ledger,
        substage_callback=substage_callback,
    )

    cycles = {
        (
            nifty_cycle.underlying_symbol,
            nifty_cycle.exchange,
        ): nifty_cycle,
        (
            sensex_cycle.underlying_symbol,
            sensex_cycle.exchange,
        ): sensex_cycle,
    }

    selected_market = decision.selected_market
    selected_cycle = (
        cycles.get(selected_market)
        if selected_market
        else None
    )
    bundle = (
        certified_p6_input_bundles.get(
            selected_market
        )
        if selected_market is not None
        else None
    )

    kwargs = {}
    if p6_stage_authority is not None:
        kwargs["p6_stage_authority"] = (
            p6_stage_authority
        )

    return execute_selected_market_p6_planning(
        bridge_result_id=bridge_result_id,
        decision=decision,
        selected_cycle=selected_cycle,
        certified_p6_input_bundle=bundle,
        evaluated_at=evaluated_at,
        maximum_candidate_age_seconds=(
            maximum_candidate_age_seconds
        ),
        **kwargs,
    )
