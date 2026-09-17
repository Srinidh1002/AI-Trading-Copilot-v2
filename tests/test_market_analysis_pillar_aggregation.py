from datetime import datetime, timezone
import pytest
from services.analysis.market_analysis_pillar_aggregation import PILLAR_ORDER, aggregate_market_analysis_pillars
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisEvidenceV1

NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)

def evidence(status="READY"):
    return MarketAnalysisEvidenceV1(status=status, source_ids=("source",) if status == "READY" else (), provenance={"source": "test"}, summary={})

def values(status="READY"):
    return {name: evidence(status) for name in PILLAR_ORDER}

def test_exact_order_and_ready_status_are_canonical():
    result = aggregate_market_analysis_pillars(pillars=values(), evaluated_at=NOW)
    assert tuple(result.ordered_pillars) == PILLAR_ORDER
    assert result.aggregation_status == "READY"

def test_missing_extra_and_wrong_type_fail_closed():
    missing = values(); missing.pop("iv")
    with pytest.raises(ValueError): aggregate_market_analysis_pillars(pillars=missing, evaluated_at=NOW)
    extra = values(); extra["extra"] = evidence()
    with pytest.raises(ValueError): aggregate_market_analysis_pillars(pillars=extra, evaluated_at=NOW)
    wrong = values(); wrong["iv"] = object()
    with pytest.raises(TypeError): aggregate_market_analysis_pillars(pillars=wrong, evaluated_at=NOW)

def test_structural_precedence_is_blocked_unavailable_conflicting_ready():
    blocked = values(); blocked["iv"] = evidence("BLOCKED")
    assert aggregate_market_analysis_pillars(pillars=blocked, evaluated_at=NOW).aggregation_status == "BLOCKED"
    unavailable = values(); unavailable["iv"] = evidence("UNAVAILABLE")
    assert aggregate_market_analysis_pillars(pillars=unavailable, evaluated_at=NOW).aggregation_status == "UNAVAILABLE"
    conflicting = values(); conflicting["iv"] = evidence("CONFLICTING")
    assert aggregate_market_analysis_pillars(pillars=conflicting, evaluated_at=NOW).aggregation_status == "CONFLICTING"
