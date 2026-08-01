import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.dashboard_read_models.dashboard_two_market_runtime_view_v1 import (
    DashboardTwoMarketRuntimeViewV1,
)


NOW = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)


def build(**changes):
    values = dict(source_id="runtime-1", source_updated_at=NOW, runtime_safety_status="PAPER_ONLY", provider_freshness_status="FRESH", nifty_status="NO_ACTION", sensex_status="NOT_SCHEDULED", emergency_halt=False, broker_order_submission=False)
    values.update(changes)
    return DashboardTwoMarketRuntimeViewV1(**values)


def test_contract_is_immutable_paper_only_and_serializes_stably():
    value = build(selected_market="nifty", latest_paper_actions=("NO_ACTION",))
    assert value.selected_market == "NIFTY"
    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    assert value.to_dict()["broker_order_submission"] is False
    with pytest.raises(FrozenInstanceError):
        value.nifty_status = "READY"


@pytest.mark.parametrize("changes", ({"broker_order_submission": True}, {"selected_market": "BANKNIFTY"}, {"pending_p7_entry_count": -1}, {"source_updated_at": datetime(2026, 8, 1, 10, 0)}))
def test_contract_rejects_unsafe_or_invalid_values(changes):
    with pytest.raises((TypeError, ValueError)):
        build(**changes)


def test_contract_has_no_dashboard_provider_or_trading_authority_imports():
    path = Path(__file__).parents[1] / "services" / "dashboard_read_models" / "dashboard_two_market_runtime_view_v1.py"
    modules = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    forbidden = ("streamlit", "sqlite3", "services.market", "services.broker", "services.paper_orchestration", "services.paper_trading", "services.paper_portfolio")
    assert not any(any(name == item or name.startswith(item + ".") for item in forbidden) for name in modules)
