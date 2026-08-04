from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.analysis.market_analysis_pillar_aggregation import PILLAR_ORDER
from services.certification.task2_pillar_contribution_report import build_task2_pillar_contribution_report
from services.contracts.market_analysis_pillar_contribution_v1 import MarketAnalysisPillarContributionCollectionV1, MarketAnalysisPillarContributionV1


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def _record(name, *, symbol="NIFTY", exchange="NSE", cycle="cycle:nifty", observation="observation:nifty", timestamp=NOW):
    return MarketAnalysisPillarContributionV1(f"{cycle}:{name}", name, symbol, exchange, cycle, observation, "READY", "UNAVAILABLE", None, None, "MarketCandleSeriesV1", "series:1", "ANGEL_ONE", timestamp, NOW, "GROUPED", True, metadata={"shared_source": True})


def _collection(*, symbol="NIFTY", exchange="NSE", cycle="cycle:nifty", observation="observation:nifty"):
    return MarketAnalysisPillarContributionCollectionV1(cycle, observation, symbol, exchange, NOW, tuple(_record(name, symbol=symbol, exchange=exchange, cycle=cycle, observation=observation) for name in PILLAR_ORDER))


def test_contract_restricts_identity_names_timestamps_scores_and_paper_safety():
    assert tuple(item.pillar_name for item in _collection().contributions) == PILLAR_ORDER
    with pytest.raises(ValueError): _record("unknown")
    with pytest.raises(ValueError): _record("pcr", symbol="BANKNIFTY")
    with pytest.raises(ValueError): _record("pcr", timestamp=datetime(2026, 8, 3, 10, 0))
    with pytest.raises(ValueError): MarketAnalysisPillarContributionV1("x", "pcr", "NIFTY", "NSE", "c", "o", "READY", "UNAVAILABLE", 2.0, None, "x", "x", None, NOW, NOW, "DIRECT", True)
    with pytest.raises(ValueError): MarketAnalysisPillarContributionV1("x", "pcr", "NIFTY", "NSE", "c", "o", "READY", "UNAVAILABLE", None, None, "x", "x", None, NOW, NOW, "DIRECT", True, execution_mode="LIVE")


def test_collection_is_exact_ordered_immutable_and_deterministic():
    collection = _collection()
    assert collection.to_json() == collection.to_json()
    assert collection.contributions[0].metadata["shared_source"] is True
    with pytest.raises(TypeError): collection.contributions[0].metadata["x"] = 1
    bad = list(collection.contributions); bad[1] = bad[0]
    with pytest.raises(ValueError): MarketAnalysisPillarContributionCollectionV1("cycle:nifty", "observation:nifty", "NIFTY", "NSE", NOW, tuple(bad))
    with pytest.raises(ValueError):
        MarketAnalysisPillarContributionCollectionV1("other", "observation:nifty", "NIFTY", "NSE", NOW, collection.contributions)


def test_credential_like_metadata_rejected_and_report_is_provider_free_projection():
    with pytest.raises(ValueError): MarketAnalysisPillarContributionV1("x", "pcr", "NIFTY", "NSE", "c", "o", "UNAVAILABLE", "UNAVAILABLE", None, None, None, None, None, None, NOW, "UNAVAILABLE", False, blockers=("MISSING",), metadata={"api_key": "not-allowed"})
    report = build_task2_pillar_contribution_report(_collection())
    assert report.to_dict()["market"]["contribution_count"] == 14
    assert report.to_dict()["ordered_pillar_names"] == list(PILLAR_ORDER)
