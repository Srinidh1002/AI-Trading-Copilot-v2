"""B1 exact X5/X7 evidence binding without promoting unverified sources."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x5_chain_contracts_v1 import capture as x5_capture
from test_x7_research_replay_v1 import fixture as x7_fixture

from services.x5.chain_validation_v1 import validate_x5_chain_v1
from services.x7.contracts_v1 import MARKETS
from services.x8.upstream_bridge_v1 import (
    bind_x5_options_to_x8_v1,
    bind_x7_context_to_x8_v1,
)


def bind_x5(market="NIFTY", source=None, validation=None, **kw):
    source = source or x5_capture(market)
    validation = validation or validate_x5_chain_v1(source, max_age_seconds=60)
    args = dict(
        market=market,
        session_id=source.session_id,
        capture_id=source.capture_id,
        as_of=source.as_of + timedelta(seconds=2),
        source=source,
        validation=validation,
        expected_source_sha256=source.sha256(),
        expected_validation_sha256=validation.sha256(),
        result_available_at=source.as_of + timedelta(seconds=1),
        max_age_seconds=60,
    )
    args.update(kw)
    return bind_x5_options_to_x8_v1(**args)


def bind_x7(market="NIFTY", source=None, **kw):
    source = source or x7_fixture(market=market)[0]
    args = dict(
        market=market,
        session_id=source.capture.session_id,
        capture_id=source.capture.capture_id,
        as_of=source.capture.as_of + timedelta(seconds=2),
        source=source,
        expected_view_sha256=source.sha256(),
        result_available_at=source.capture.as_of + timedelta(seconds=1),
    )
    args.update(kw)
    return bind_x7_context_to_x8_v1(**args)


@pytest.mark.parametrize("market", MARKETS)
def test_x5_real_chain_validation_binds_all_five(market):
    row = bind_x5(market)
    assert row.family == "OPTIONS" and row.state == "AVAILABLE"
    assert row.point_in_time_verified and not row.independent_vote
    assert not row.execution_authority and not row.certification_authority


@pytest.mark.parametrize("market", MARKETS)
def test_x7_adapts_five_markets_without_upgrading_mcx_partial(market):
    row = bind_x7(market)
    assert row.family == "EXTERNAL_CONTEXT"
    assert row.state == ("AVAILABLE" if market in ("NIFTY", "SENSEX") else "PARTIAL")
    assert row.point_in_time_verified and not row.live_execution_eligible


@pytest.mark.parametrize("market", MARKETS)
def test_x5_detached_capture_hash_mismatch_rejected(market):
    with pytest.raises(ValueError, match="digests"):
        bind_x5(market, expected_source_sha256="a" * 64)


@pytest.mark.parametrize("market", MARKETS)
def test_x5_tampered_validation_not_accepted_even_with_matching_claimed_hash(market):
    source = x5_capture(market)
    val = validate_x5_chain_v1(source, max_age_seconds=60)
    tampered = replace(val, status="PARTIAL")
    with pytest.raises(ValueError, match="reproducible"):
        bind_x5(
            market, source=source, validation=tampered, expected_validation_sha256=tampered.sha256()
        )


@pytest.mark.parametrize("market", MARKETS)
def test_x7_hash_mismatch_rejected(market):
    with pytest.raises(ValueError, match="digest"):
        bind_x7(market, expected_view_sha256="e" * 64)


@pytest.mark.parametrize("market", MARKETS)
def test_x5_future_availability_fails_closed(market):
    source = x5_capture(market)
    with pytest.raises(ValueError, match="availability"):
        bind_x5(market, as_of=source.as_of, result_available_at=source.as_of + timedelta(seconds=1))


@pytest.mark.parametrize("market", MARKETS)
def test_x7_future_availability_fails_closed(market):
    source = x7_fixture(market=market)[0]
    with pytest.raises(ValueError, match="availability"):
        bind_x7(
            market,
            source=source,
            as_of=source.capture.as_of,
            result_available_at=source.capture.as_of + timedelta(seconds=1),
        )


def test_x5_retrospective_cannot_be_point_in_time():
    source = x5_capture(
        "NIFTY",
        point_in_time_verified=False,
        historical_retrieval=True,
        captured_at=x5_capture().as_of + timedelta(seconds=1),
    )
    assert (
        bind_x5(source=source, as_of=source.captured_at + timedelta(seconds=2)).state
        == "UNVERIFIED"
    )


def test_x7_retrospective_cannot_be_point_in_time():
    source = x7_fixture(pit=False, historical=True)[0]
    assert bind_x7(source=source).state == "UNVERIFIED"


def test_x5_wrong_market_binding_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        bind_x5("SENSEX", source=x5_capture("NIFTY"))


def test_x7_wrong_market_binding_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        bind_x7("SENSEX", source=x7_fixture(market="NIFTY")[0])


def test_x5_wrong_quality_budget_is_not_silently_accepted():
    with pytest.raises(ValueError, match="reproducible"):
        bind_x5(max_age_seconds=0.1)


@pytest.mark.parametrize("family", ("OPTIONS", "EXTERNAL_CONTEXT"))
def test_no_source_consumer_can_choose_trading_authority(family):
    row = bind_x5() if family == "OPTIONS" else bind_x7()
    with pytest.raises(ValueError):
        replace(row, execution_authority=True)
