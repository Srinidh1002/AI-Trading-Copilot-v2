from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from services.contracts.certified_live_captured_evidence_v1 import (
    CertifiedLiveCapturedEvidenceV1,
)
from services.live_option_chain_builder import LiveOptionChainBuilder
from services.live_option_decision_pipeline import LiveOptionDecisionPipeline
from services.market_session.validator import validate_session_timestamp
from tests.test_task8_parent_typed_candidate_certification import (
    captured as task8_captured,
)


NOW = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)


def _master(symbol="NIFTY", exchange="NFO", expiry="11AUG2026"):
    master = MagicMock()
    master.get_nearest_expiry.return_value = {"raw": expiry, "display": expiry}
    contracts = []
    for strike in (25000,):
        for suffix in ("CE", "PE"):
            contracts.append({
                "token": f"{symbol}-{strike}-{suffix}",
                "symbol": f"{symbol}11AUG26{strike}{suffix}",
                "expiry": expiry,
                "strike": str(strike * 100),
                "lotsize": "25",
            })
    master.get_option_contracts.return_value = contracts
    return master


def _quotes(symbol="NIFTY", exchange="NFO"):
    return {
        "status": True,
        "data": {
            "fetched": [
                {
                    "symbolToken": f"{symbol}-25000-{suffix}",
                    "ltp": 100.0 if suffix == "CE" else 110.0,
                    "tradeVolume": 1000,
                    "opnInterest": 2000,
                    "exchangeTimestamp": NOW.isoformat(),
                    "depth": {"buy": [{"price": 99.0}], "sell": [{"price": 101.0}]},
                }
                for suffix in ("CE", "PE")
            ],
            "unfetched": [],
        },
    }


def _greek(symbol="NIFTY", suffix="CE", **changes):
    value = {
        "tradingSymbol": f"{symbol}11AUG2625000{suffix}",
        "strikePrice": 25000,
        "optionType": suffix,
        "delta": 0.5 if suffix == "CE" else -0.5,
        "gamma": 0.01,
        "theta": -10.0,
        "vega": 5.0,
        "impliedVolatility": 12.5,
    }
    value.update(changes)
    return value


def _builder(client, *, symbol="NIFTY", exchange="NFO"):
    client.get_market_data.return_value = _quotes(symbol, exchange)
    return LiveOptionChainBuilder(
        instrument_master=_master(symbol, exchange),
        market_client=client,
        clock=lambda: NOW,
    )


def test_nifty_enriches_certified_contracts_once_with_valid_greeks_and_iv():
    client = MagicMock()
    client.get_option_greeks.return_value = {"data": [_greek(suffix="CE"), _greek(suffix="PE")]}

    result = _builder(client).build_chain("NIFTY", 25000, strikes_each_side=0)

    contracts = {item["option_type"]: item for item in result["contracts"]}
    assert contracts["CE"]["delta"] == 0.5
    assert contracts["CE"]["gamma"] == 0.01
    assert contracts["CE"]["theta"] == -10.0
    assert contracts["CE"]["vega"] == 5.0
    assert contracts["CE"]["iv"] == 12.5
    assert result["greek_capture"] == {"state": "SUPPORTED", "reason": None}
    client.get_option_greeks.assert_called_once_with("NIFTY", "11AUG2026")


def test_greeks_require_exact_provider_identity_and_ignore_unmatched_rows():
    client = MagicMock()
    client.get_option_greeks.return_value = {
        "data": [_greek(suffix="CE", tradingSymbol="OTHER11AUG2625000CE"), _greek(suffix="PE")]
    }

    result = _builder(client).build_chain("NIFTY", 25000, strikes_each_side=0)

    contracts = {item["option_type"]: item for item in result["contracts"]}
    assert contracts["CE"]["delta"] is None
    assert contracts["PE"]["delta"] == -0.5


def test_malformed_greek_payload_fails_closed_without_affecting_full_quote_fields():
    client = MagicMock()
    client.get_option_greeks.return_value = {"data": [_greek(delta="not-a-number")]}

    result = _builder(client).build_chain("NIFTY", 25000, strikes_each_side=0)

    contract = result["contracts"][0]
    assert result["greek_capture"]["state"] == "DATA_MALFORMED"
    assert all(contract[key] is None for key in ("delta", "gamma", "theta", "vega", "iv"))
    assert (contract["premium"], contract["bid"], contract["ask"], contract["volume"], contract["open_interest"], contract["lot_size"], contract["provider_timestamp"]) == (100.0, 99.0, 101.0, 1000, 2000, 25, NOW)


def test_provider_failure_is_sanitized_and_cannot_silently_enter_certified_capture():
    client = MagicMock()
    client.get_option_greeks.side_effect = RuntimeError("provider failure")
    pipeline = LiveOptionDecisionPipeline(option_chain_builder=_builder(client))

    capture = pipeline.capture_option_inputs(
        underlying="NIFTY", spot_price=25000, option_exchange="NFO",
        provider_timestamp=NOW, evaluated_at=NOW,
    )

    assert capture.blockers == ("OPTION_GREEKS_PROVIDER_FAILURE_RUNTIMEERROR",)
    assert capture.metadata["greek_capture"]["state"] == "PROVIDER_FAILURE"
    assert all(contract["delta"] is None for contract in capture.contracts)


def test_sensex_preserves_unsupported_provider_capability_without_provider_call():
    client = MagicMock()

    result = _builder(client, symbol="SENSEX", exchange="BFO").build_chain(
        "SENSEX", 25000, strikes_each_side=0, option_exchange="BFO",
    )

    assert result["greek_capture"] == {
        "state": "UNSUPPORTED_BY_PROVIDER",
        "reason": "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE",
    }
    client.get_option_greeks.assert_not_called()


def test_duplicate_greek_rows_do_not_select_a_row_by_position():
    client = MagicMock()
    client.get_option_greeks.return_value = {"data": [_greek(suffix="CE"), _greek(suffix="CE", delta=0.9)]}

    result = _builder(client).build_chain("NIFTY", 25000, strikes_each_side=0)

    assert next(item for item in result["contracts"] if item["option_type"] == "CE")["delta"] is None


def test_valid_nifty_greeks_and_iv_reach_task8_capture_contract_evidence_and_paper_stays_disabled():
    client = MagicMock()
    client.get_option_greeks.return_value = {"data": [_greek(suffix="CE"), _greek(suffix="PE")]}
    pipeline = LiveOptionDecisionPipeline(option_chain_builder=_builder(client))

    capture = pipeline.capture_option_inputs(
        underlying="NIFTY", spot_price=25000, option_exchange="NFO",
        provider_timestamp=NOW, evaluated_at=NOW,
    )

    assert capture.blockers == ()
    assert all(item["iv"] == 12.5 and item["delta"] is not None for item in capture.contracts)
    # This capture path only composes immutable PAPER evidence; it has no
    # broker-order authority and does not alter runtime execution eligibility.
    assert capture.schema_version == "live_option_capture_result.v1"


def test_task8_candidate_does_not_report_unavailable_greeks_or_iv_when_valid_nifty_values_are_supplied():
    """Exercise the typed Task 8 bridge with contracts enriched as above."""
    source = task8_captured("NIFTY", "NSE", 25000.0, complete_options=True)
    enriched_contracts = tuple(
        {
            **dict(contract),
            "delta": 0.5 if contract["option_type"] == "CE" else -0.5,
            "gamma": 0.01,
            "theta": -10.0,
            "vega": 5.0,
            "iv": 12.5,
        }
        for contract in source.option_contracts
    )
    captured = CertifiedLiveCapturedEvidenceV1(
        underlying_symbol=source.underlying_symbol,
        spot_exchange=source.spot_exchange,
        spot_token=source.spot_token,
        option_exchange=source.option_exchange,
        spot_payload=source.spot_payload,
        candle_rows_by_timeframe=source.candle_rows_by_timeframe,
        option_contracts=enriched_contracts,
        provider_timestamp=source.provider_timestamp,
        evaluated_at=source.evaluated_at,
        provider_blockers=source.provider_blockers,
        provider_warnings=source.provider_warnings,
        cache_metadata=source.cache_metadata,
    )
    session = validate_session_timestamp(
        symbol="NIFTY", exchange="NSE", market_timestamp=source.provider_timestamp,
        evaluated_at=source.evaluated_at, validation_mode="LENIENT_ANALYSIS",
        id_factory=lambda: "task918-session:nifty",
    )

    result = evaluate_captured_certified_market_candidate(
        captured_evidence=captured,
        session_validation=session,
        policy_source=LiveCandidatePolicySourceV1("BULLISH", "ELIGIBLE", 80.0, 80.0),
        parent_cycle_id="task918-parent",
        candidate_id="task918-nifty-candidate",
        observation_id="task918-nifty-observation",
        engines=build_default_live_canonical_evidence_engines(),
    )

    assert all(contract.implied_volatility == 12.5 for contract in result.options.universe.contracts)
    assert all(contract.metadata["delta"] is not None for contract in result.options.universe.contracts)
    assert "EVIDENCE_UNAVAILABLE_GREEKS" not in result.candidate.blockers
    assert "EVIDENCE_UNAVAILABLE_IV" not in result.candidate.blockers
