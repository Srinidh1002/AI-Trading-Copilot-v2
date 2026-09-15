from dataclasses import replace

import pytest

from services.broker.shared_client import (
    get_certification_market_client,
    get_shared_request_controller,
)
from services.certification.task9_production_startup_proof_assembler import (
    Task9RetainedAngelStartupCapturesV1,
    build_task9_angel_live_proof_bundle_from_retained_captures,
)
from tests.test_task9865a7_angel_live_proof_bundle import (
    NOW,
    _bundle,
)


def _captures():
    expected = _bundle()

    client = get_certification_market_client()
    controller = get_shared_request_controller()

    # C2B itself is conversion-only. Existing focused producer fixtures are
    # injected by monkeypatch in individual tests below; no provider request
    # is permitted by this test module.
    return client, controller, expected


def test_retained_capture_contract_requires_same_request_controller():
    client, _, expected = _captures()

    from services.broker.market_data_control import (
        MarketDataRequestController,
    )

    other = MarketDataRequestController()

    with pytest.raises(
        ValueError,
        match="REQUEST_CONTROLLER_IDENTITY_MISMATCH",
    ):
        Task9RetainedAngelStartupCapturesV1(
            client=client,
            request_controller=other,
            instrument_master_records=(),
            instrument_master_metadata={},
            spot_full_quotes=object(),
            nifty_option_capture=object(),
            sensex_option_capture=object(),
            india_vix_capture=object(),
            observed_at=NOW,
        )


def test_assembler_calls_only_existing_proof_producers(
    monkeypatch,
):
    import services.certification.task9_production_startup_proof_assembler as module

    client, controller, expected = _captures()

    class DummyCaptures:
        pass

    # Construct without invoking the strict retained-capture constructor;
    # this test verifies assembler delegation only.
    captures = object.__new__(
        Task9RetainedAngelStartupCapturesV1
    )

    object.__setattr__(
        captures,
        "client",
        client,
    )
    object.__setattr__(
        captures,
        "request_controller",
        controller,
    )
    object.__setattr__(
        captures,
        "instrument_master_records",
        (),
    )
    object.__setattr__(
        captures,
        "instrument_master_metadata",
        {},
    )
    object.__setattr__(
        captures,
        "spot_full_quotes",
        object(),
    )
    object.__setattr__(
        captures,
        "nifty_option_capture",
        object(),
    )
    object.__setattr__(
        captures,
        "sensex_option_capture",
        object(),
    )
    object.__setattr__(
        captures,
        "india_vix_capture",
        object(),
    )
    object.__setattr__(
        captures,
        "observed_at",
        NOW,
    )
    object.__setattr__(
        captures,
        "execution_mode",
        "PAPER",
    )
    object.__setattr__(
        captures,
        "broker_order_submission",
        False,
    )
    object.__setattr__(
        captures,
        "live_execution_eligible",
        False,
    )
    object.__setattr__(
        captures,
        "schema_version",
        "task9_retained_angel_startup_captures.v1",
    )

    monkeypatch.setattr(
        module,
        "produce_task9_angel_auth_session_proof",
        lambda **_: expected.auth,
    )
    monkeypatch.setattr(
        module,
        "produce_task9_angel_instrument_master_proof",
        lambda **_: expected.instrument_master,
    )
    monkeypatch.setattr(
        module,
        "produce_task9_angel_spot_full_proofs",
        lambda _: expected.spots,
    )

    option_full = iter(
        expected.option_full
    )
    greeks = iter(
        expected.greeks
    )

    monkeypatch.setattr(
        module,
        "produce_task9_angel_option_full_proof",
        lambda _: next(option_full),
    )
    monkeypatch.setattr(
        module,
        "produce_task9_angel_greeks_proof",
        lambda _: next(greeks),
    )
    monkeypatch.setattr(
        module,
        "produce_task9_angel_india_vix_proof",
        lambda _: expected.india_vix,
    )
    monkeypatch.setattr(
        module,
        "produce_task9_angel_request_budget_proof",
        lambda **_: expected.request_budget,
    )

    actual = (
        build_task9_angel_live_proof_bundle_from_retained_captures(
            captures=captures
        )
    )

    assert actual == expected

    assert captures.execution_mode == "PAPER"
    assert captures.broker_order_submission is False
    assert captures.live_execution_eligible is False


def test_assembler_rejects_noncanonical_capture_contract():
    with pytest.raises(TypeError):
        build_task9_angel_live_proof_bundle_from_retained_captures(
            captures=object()
        )
