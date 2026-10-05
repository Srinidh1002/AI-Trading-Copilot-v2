from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from services.live_execution import r16_pre_live_eligibility_v1 as live


def _report(nifty="IN_PROGRESS", sensex="IN_PROGRESS"):
    return SimpleNamespace(
        markets=(
            SimpleNamespace(
                market="NIFTY",
                authority_status="PASS",
                authority_reason="OK",
                final_verdict=nifty,
            ),
            SimpleNamespace(
                market="SENSEX",
                authority_status="PASS",
                authority_reason="OK",
                final_verdict=sensex,
            ),
        )
    )


def test_current_incomplete_paper_campaign_is_not_live_eligible(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        live,
        "build_five_market_certification_final_report",
        lambda _root: _report(),
    )

    result = live.evaluate_r16_pre_live_eligibility(tmp_path)

    assert result.paper_prerequisites_pass is False
    assert result.live_authorized is False
    assert result.broker_order_submission_authorized is False
    assert "NIFTY:PAPER_CERTIFICATION_IN_PROGRESS" in result.blockers
    assert "SENSEX:PAPER_CERTIFICATION_IN_PROGRESS" in result.blockers


def test_even_two_index_paper_pass_cannot_self_authorize_live(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        live,
        "build_five_market_certification_final_report",
        lambda _root: _report("PASS", "PASS"),
    )

    result = live.evaluate_r16_pre_live_eligibility(tmp_path)

    assert result.paper_prerequisites_pass is True
    assert result.eligible_markets == ("NIFTY", "SENSEX")
    assert result.live_authorized is False
    assert result.broker_order_submission_authorized is False
    assert "LIVE_ORDER_LAYER_NOT_AUTHORIZED" in result.blockers
    assert "OPERATOR_LIVE_APPROVAL_NOT_GRANTED" in result.blockers
    assert "SUPERVISED_SMALL_CAPITAL_PILOT_NOT_ACCEPTED" in result.blockers


def test_pre_live_contract_rejects_any_live_authorization():
    base = live.R16PreLiveEligibilityV1(
        paper_prerequisites_pass=False,
        live_authorized=False,
        broker_order_submission_authorized=False,
        eligible_markets=(),
        blockers=("NOT_READY",),
    )

    import pytest

    with pytest.raises(ValueError, match="cannot authorize LIVE"):
        replace(base, live_authorized=True)

    with pytest.raises(ValueError, match="cannot authorize broker orders"):
        replace(base, broker_order_submission_authorized=True)
