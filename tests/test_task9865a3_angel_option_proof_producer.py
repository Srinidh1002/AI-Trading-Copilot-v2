from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.certification.task9_angel_option_proof_producer import (
    produce_task9_angel_greeks_proof,
    produce_task9_angel_option_full_proof,
)
from services.contracts.live_option_capture_result_v1 import (
    LiveOptionCaptureResultV1,
)
from services.contracts.task9_angel_greeks_proof_v1 import (
    Task9AngelGreeksProbeStatus,
)
from services.contracts.task9_angel_option_full_proof_v1 import (
    Task9AngelOptionFullProbeStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    5,
    30,
    tzinfo=timezone.utc,
)


def _contract(
    token,
    *,
    greeks=True,
    timestamp=NOW,
):
    return {
        "token": token,
        "symbol": f"NIFTY-{token}",
        "strike": 25000.0,
        "option_type": "CE",
        "expiry": "27AUG2026",
        "lot_size": 25,
        "premium": 100.0,
        "bid": 99.0,
        "ask": 101.0,
        "volume": 100,
        "open_interest": 200,
        "provider_timestamp": timestamp,
        "delta": 0.5 if greeks else None,
        "gamma": 0.01 if greeks else None,
        "theta": -5.0 if greeks else None,
        "vega": 2.0 if greeks else None,
        "iv": 12.0 if greeks else None,
    }


def _capture(
    *,
    market="NIFTY",
    exchange="NFO",
    contracts=None,
    greek_state="SUPPORTED",
    greek_reason=None,
    requested=None,
    malformed=0,
    unfetched=0,
):
    contracts = list(
        contracts
        if contracts is not None
        else [
            _contract("1"),
            _contract("2"),
        ]
    )

    fetched = len(contracts)

    requested = (
        fetched + malformed + unfetched
        if requested is None
        else requested
    )

    chain = {
        "underlying": market,
        "contracts": contracts,
        "full_capture": {
            "requested_contract_count": requested,
            "fetched_contract_count": fetched,
            "unfetched_contract_count": unfetched,
            "malformed_contract_count": malformed,
            "oldest_provider_timestamp": NOW,
            "newest_provider_timestamp": NOW,
            "exchange_identity_verified": True,
        },
        "greek_capture": {
            "state": greek_state,
            "reason": greek_reason,
        },
    }

    return LiveOptionCaptureResultV1(
        underlying_symbol=market,
        option_exchange=exchange,
        option_chain=chain,
        provider_timestamp=NOW,
        evaluated_at=NOW,
        metadata={
            "capture_source":
            "LIVE_OPTION_CHAIN_BUILDER",
            "greek_capture": {
                "state": greek_state,
                "reason": greek_reason,
            },
        },
    )


def test_complete_full_capture_becomes_available():
    proof = (
        produce_task9_angel_option_full_proof(
            _capture()
        )
    )

    assert (
        proof.status
        is Task9AngelOptionFullProbeStatus.AVAILABLE
    )
    assert proof.requested_contract_count == 2
    assert proof.fetched_contract_count == 2
    assert proof.unfetched_contract_count == 0
    assert proof.malformed_contract_count == 0


def test_partial_full_capture_preserves_accounting():
    capture = _capture(
        contracts=[_contract("1")],
        requested=2,
        malformed=1,
    )

    proof = (
        produce_task9_angel_option_full_proof(
            capture
        )
    )

    assert (
        proof.status
        is Task9AngelOptionFullProbeStatus.PARTIAL
    )
    assert (
        proof.fetched_contract_count
        + proof.unfetched_contract_count
        + proof.malformed_contract_count
        == proof.requested_contract_count
    )


def test_nifty_complete_greeks_are_available():
    proof = (
        produce_task9_angel_greeks_proof(
            _capture()
        )
    )

    assert (
        proof.status
        is Task9AngelGreeksProbeStatus.AVAILABLE
    )
    assert proof.requested_contract_count == 2
    assert proof.enriched_contract_count == 2
    assert proof.unavailable_contract_count == 0


def test_nifty_partial_exact_matches_are_partial():
    proof = (
        produce_task9_angel_greeks_proof(
            _capture(
                contracts=[
                    _contract("1"),
                    _contract(
                        "2",
                        greeks=False,
                    ),
                ],
            )
        )
    )

    assert (
        proof.status
        is Task9AngelGreeksProbeStatus.PARTIAL
    )
    assert proof.enriched_contract_count == 1
    assert proof.unavailable_contract_count == 1


def test_nifty_provider_failure_is_unavailable():
    proof = (
        produce_task9_angel_greeks_proof(
            _capture(
                contracts=[
                    _contract(
                        "1",
                        greeks=False,
                    ),
                ],
                greek_state="PROVIDER_FAILURE",
                greek_reason=(
                    "OPTION_GREEKS_PROVIDER_FAILURE_RUNTIMEERROR"
                ),
            )
        )
    )

    assert (
        proof.status
        is Task9AngelGreeksProbeStatus.UNAVAILABLE
    )
    assert proof.enriched_contract_count == 0
    assert proof.unavailable_contract_count == 1


def test_sensex_bfo_is_unsupported_without_greeks():
    capture = _capture(
        market="SENSEX",
        exchange="BFO",
        contracts=[
            _contract(
                "1",
                greeks=False,
            ),
        ],
        greek_state="UNSUPPORTED_BY_PROVIDER",
        greek_reason=(
            "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE"
        ),
    )

    proof = (
        produce_task9_angel_greeks_proof(
            capture
        )
    )

    assert (
        proof.status
        is Task9AngelGreeksProbeStatus.UNSUPPORTED
    )
    assert proof.requested_contract_count == 0
    assert proof.enriched_contract_count == 0
    assert proof.unavailable_contract_count == 0
    assert proof.delta_present is False
    assert proof.gamma_present is False
    assert proof.theta_present is False
    assert proof.vega_present is False
    assert (
        proof.implied_volatility_present
        is False
    )


def test_all_proofs_remain_paper_only():
    full = (
        produce_task9_angel_option_full_proof(
            _capture()
        )
    )
    greeks = (
        produce_task9_angel_greeks_proof(
            _capture()
        )
    )

    for proof in (full, greeks):
        assert proof.execution_mode == "PAPER"
        assert (
            proof.broker_order_submission
            is False
        )
        assert (
            proof.live_execution_eligible
            is False
        )


def test_producers_have_no_market_client_dependency():
    import inspect

    full_parameters = inspect.signature(
        produce_task9_angel_option_full_proof
    ).parameters

    greek_parameters = inspect.signature(
        produce_task9_angel_greeks_proof
    ).parameters

    assert tuple(full_parameters) == (
        "capture",
    )
    assert tuple(greek_parameters) == (
        "capture",
    )
