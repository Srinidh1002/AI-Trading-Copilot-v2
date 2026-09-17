from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.dashboard_read_models.dashboard_decision_history_view_v1 import (
    DashboardDecisionHistoryRowV1,
    DashboardDecisionHistoryViewV1,
)
from services.dashboard_read_models.dashboard_market_overview_view_v1 import (
    DashboardMarketOverviewViewV1,
)
from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardComponentHealthViewV1,
    DashboardRuntimeOperationsViewV1,
)
from services.dashboard_read_models.dashboard_validation_summary_view_v1 import (
    DashboardValidationSummaryViewV1,
)


NOW = datetime(2026, 7, 30, 13, 30, tzinfo=timezone.utc)


def test_market_overview_is_immutable_and_paper_only():
    value = DashboardMarketOverviewViewV1(
        source_id="source-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_status="OPEN",
        source_updated_at=NOW,
        last_traded_price=25000,
    )

    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    with pytest.raises(FrozenInstanceError):
        value.market_status = "CLOSED"


def test_market_overview_rejects_inverted_levels():
    with pytest.raises(ValueError, match="support"):
        DashboardMarketOverviewViewV1(
            source_id="source-1",
            underlying_symbol="NIFTY",
            exchange="NSE",
            market_status="OPEN",
            source_updated_at=NOW,
            support=25100,
            resistance=25000,
        )


def test_option_view_is_typed_and_immutable():
    value = DashboardOptionIntelligenceViewV1(
        source_id="option-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        status="READY",
        source_updated_at=NOW,
        pcr=1.1,
    )
    assert value.pcr == 1.1


def test_validation_summary_checks_counts():
    with pytest.raises(ValueError, match="cannot exceed"):
        DashboardValidationSummaryViewV1(
            source_id="portfolio-1",
            source_updated_at=NOW,
            total_completed_trades=1,
            winning_trades=1,
            losing_trades=1,
            net_realized_pnl=0,
        )


def test_history_requires_exact_typed_rows():
    row = DashboardDecisionHistoryRowV1(
        source_id="decision-1",
        observed_at=NOW,
        action="WAIT",
    )
    value = DashboardDecisionHistoryViewV1(
        source_id="history-1",
        source_updated_at=NOW,
        rows=(row,),
    )
    assert value.rows == (row,)

    with pytest.raises(TypeError, match="wrong type"):
        DashboardDecisionHistoryViewV1(
            source_id="history-1",
            source_updated_at=NOW,
            rows=(object(),),
        )


def test_runtime_operations_requires_typed_components():
    component = DashboardComponentHealthViewV1(
        component="publication",
        status="OK",
    )
    value = DashboardRuntimeOperationsViewV1(
        source_id="runtime-1",
        runtime_status="RUNNING",
        source_updated_at=NOW,
        components=(component,),
    )
    assert value.components == (component,)


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        DashboardValidationSummaryViewV1(
            source_id="portfolio-1",
            source_updated_at=datetime(2026, 7, 30),
            total_completed_trades=0,
            winning_trades=0,
            losing_trades=0,
            net_realized_pnl=0,
        )
