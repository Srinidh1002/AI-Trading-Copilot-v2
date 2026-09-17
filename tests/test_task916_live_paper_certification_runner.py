from datetime import timedelta

from services.certification.task9_live_paper_certification_runner import (
    Task9LivePaperCertificationRunner,
    Task9MarketCycleEvidenceV1,
)
from tests.p7_fixture_helpers import NOW
from tests.test_task9_live_paper_trade_counting_evaluator import prediction


def test_runner_evaluates_both_children_and_never_counts_nonterminal_entries():
    calls, persisted, published = [], [], []

    def child(market, exchange, entry_allowed):
        calls.append((market, exchange, entry_allowed))
        return Task9MarketCycleEvidenceV1(
            prediction=prediction(
                prediction_id=f"prediction-{market}",
                underlying_symbol=market,
                exchange=exchange,
            )
        )

    runner = Task9LivePaperCertificationRunner(
        official_run_id="task9-live-run",
        official_start_at=NOW - timedelta(minutes=3),
        child_authority=child,
        persist=persisted.append,
        publish=published.append,
    )

    result = runner.run_cycle(cycle_id="cycle-1", evaluated_at=NOW)

    assert [item[:2] for item in calls] == [("NIFTY", "NSE"), ("SENSEX", "BSE")]
    assert all(item[2] is None for item in result.market_results)
    assert persisted == [result]
    assert published == [result]


def test_failed_child_does_not_prevent_the_other_market_from_running():
    calls, persisted = [], []

    def child(market, exchange, entry_allowed):
        calls.append(market)
        if market == "NIFTY":
            raise RuntimeError("provider unavailable")
        return Task9MarketCycleEvidenceV1(
            prediction=prediction(
                prediction_id="prediction-sensex",
                underlying_symbol="SENSEX",
                exchange="BSE",
            )
        )

    result = Task9LivePaperCertificationRunner(
        official_run_id="task9-live-run",
        official_start_at=NOW - timedelta(minutes=3),
        child_authority=child,
        persist=persisted.append,
    ).run_cycle(cycle_id="cycle-2", evaluated_at=NOW)

    assert calls == ["NIFTY", "SENSEX"]
    assert result.market_results[0][0:2] == ("NIFTY", "INTERNAL_CHILD_FAILURE")
    assert result.market_results[0][2].reason_code == "INTERNAL_CHILD_FAILURE_RUNTIMEERROR"
    assert result.market_results[1][0:2] == ("SENSEX", "ENTRY_ALLOWED")


def test_data_incident_child_is_excluded_without_counting_or_crash():
    persisted = []

    def child(market, exchange, entry_allowed):
        return Task9MarketCycleEvidenceV1(
            prediction=prediction(
                prediction_id=f"failed-{market}",
                underlying_symbol=market,
                exchange=exchange,
                terminal_status="FAILED",
                candidate_id=None,
                market_timestamp=None,
                predicted_direction="UNAVAILABLE",
                predicted_action="WAIT",
                eligibility="UNAVAILABLE",
                confidence=0.0,
                score=0.0,
                rank_value=0.0,
                eligible_for_comparison=False,
                outcome_reason="CHILD_FAILED",
                parent_decision="NO_TRADE",
                parent_selected=False,
                errors=("HISTORICAL-DATA_RATE_LIMITED",),
            ),
            evidence_status="DATA_INCIDENT",
        )

    result = Task9LivePaperCertificationRunner(
        official_run_id="task9-live-run",
        official_start_at=NOW - timedelta(minutes=3),
        child_authority=child,
        persist=persisted.append,
    ).run_cycle(cycle_id="cycle-data-incident", evaluated_at=NOW)

    assert all(item[1] == "DATA_INCIDENT" for item in result.market_results)
    assert all(item[2].status == "EXCLUDED_DATA_INCIDENT" for item in result.market_results)
    assert all(item[2].trade_target_countable is False for item in result.market_results)
    assert all("HISTORICAL-DATA_RATE_LIMITED" in item[2].reason_codes for item in result.market_results)


def test_provider_incident_does_not_prevent_independent_other_market_processing():
    def child(market, exchange, entry_allowed):
        if market == "NIFTY":
            return Task9MarketCycleEvidenceV1(
                prediction=prediction(
                    prediction_id="rate-limited-nifty",
                    underlying_symbol="NIFTY",
                    exchange="NSE",
                    terminal_status="FAILED",
                    candidate_id=None,
                    market_timestamp=None,
                    predicted_direction="UNAVAILABLE",
                    predicted_action="WAIT",
                    eligibility="UNAVAILABLE",
                    confidence=0.0,
                    score=0.0,
                    rank_value=0.0,
                    eligible_for_comparison=False,
                    outcome_reason="CHILD_FAILED",
                    parent_decision="NO_TRADE",
                    parent_selected=False,
                    errors=("HISTORICAL-DATA_RATE_LIMITED",),
                ),
                evidence_status="DATA_INCIDENT",
            )
        return Task9MarketCycleEvidenceV1(
            prediction=prediction(
                prediction_id="valid-sensex",
                underlying_symbol="SENSEX",
                exchange="BSE",
            )
        )

    result = Task9LivePaperCertificationRunner(
        official_run_id="task9-live-run",
        official_start_at=NOW - timedelta(minutes=3),
        child_authority=child,
        persist=lambda _: None,
    ).run_cycle(cycle_id="cycle-mixed", evaluated_at=NOW)

    assert result.market_results[0][0:2] == ("NIFTY", "DATA_INCIDENT")
    assert result.market_results[0][2].status == "EXCLUDED_DATA_INCIDENT"
    assert result.market_results[0][2].trade_target_countable is False
    assert result.market_results[1][0:2] == ("SENSEX", "ENTRY_ALLOWED")
