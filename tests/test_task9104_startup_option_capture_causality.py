from types import SimpleNamespace

import pytest

import services.certification.task9_production_startup_acquisition as module
from services.broker.shared_client import (
    get_certification_market_client,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
)


NOW = __import__("datetime").datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=__import__("datetime").timezone.utc,
)


class AnalysisPipeline:
    def analyse(self, *args, **kwargs):
        return {}


class Master:
    def __init__(self):
        # Deliberately unretained so these tests prove
        # capture blockers win before the downstream
        # master-retention assertion.
        self.instruments = None

    def get_metadata(self):
        pytest.fail(
            "master metadata must not be inspected "
            "after causal option-capture failure"
        )


class Builder:
    def __init__(self, *, client, master):
        self.market_client = client
        self.instrument_master = master


class OptionPipeline:
    def __init__(
        self,
        *,
        client,
        master,
        nifty_blockers=(),
        sensex_blockers=(),
    ):
        self.option_chain_builder = Builder(
            client=client,
            master=master,
        )
        self.nifty_blockers = tuple(
            nifty_blockers
        )
        self.sensex_blockers = tuple(
            sensex_blockers
        )

    def analyse(self, *args, **kwargs):
        return {}

    def capture_option_inputs(
        self,
        *,
        underlying,
        spot_price,
        option_exchange,
        provider_timestamp,
        evaluated_at,
    ):
        del (
            spot_price,
            option_exchange,
            provider_timestamp,
            evaluated_at,
        )

        blockers = (
            self.nifty_blockers
            if underlying == "NIFTY"
            else self.sensex_blockers
        )

        return SimpleNamespace(
            blockers=blockers,
            warnings=(),
        )


def _providers(
    *,
    nifty_blockers=(),
    sensex_blockers=(),
):
    client = get_certification_market_client()
    master = Master()

    pipeline = OptionPipeline(
        client=client,
        master=master,
        nifty_blockers=nifty_blockers,
        sensex_blockers=sensex_blockers,
    )

    providers = CertifiedRuntimeProviderBundleV1(
        quote_reader=lambda *_: None,
        analysis_pipeline=AnalysisPipeline(),
        option_decision_pipeline=pipeline,
        clock=lambda: NOW,
    )

    return providers


def _install_full_quotes(monkeypatch):
    full_quotes = SimpleNamespace(
        nifty=SimpleNamespace(
            ltp=25000.0,
            provider_timestamp=NOW,
            received_at=NOW,
        ),
        sensex=SimpleNamespace(
            ltp=80000.0,
            provider_timestamp=NOW,
            received_at=NOW,
        ),
    )

    monkeypatch.setattr(
        module,
        "fetch_canonical_two_market_full_quotes",
        lambda supplied_client, *, clock: (
            full_quotes
        ),
    )


def test_nifty_capture_blocker_precedes_master_retention(
    monkeypatch,
):
    _install_full_quotes(monkeypatch)

    providers = _providers(
        nifty_blockers=(
            "OPTION_CAPTURE_RUNTIMEERROR",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TASK9_STARTUP_NIFTY_OPTION_CAPTURE_BLOCKED:"
            "OPTION_CAPTURE_RUNTIMEERROR"
        ),
    ):
        module.capture_task9_production_startup_angel_facts(
            providers=providers,
            startup_capture_id="startup-causal-nifty",
        )


def test_sensex_capture_blocker_precedes_master_retention(
    monkeypatch,
):
    _install_full_quotes(monkeypatch)

    providers = _providers(
        sensex_blockers=(
            "OPTION_CAPTURE_VALUEERROR",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TASK9_STARTUP_SENSEX_OPTION_CAPTURE_BLOCKED:"
            "OPTION_CAPTURE_VALUEERROR"
        ),
    ):
        module.capture_task9_production_startup_angel_facts(
            providers=providers,
            startup_capture_id="startup-causal-sensex",
        )


def test_successful_captures_still_require_retained_master(
    monkeypatch,
):
    _install_full_quotes(monkeypatch)

    providers = _providers()

    with pytest.raises(
        RuntimeError,
        match=(
            "TASK9_STARTUP_INSTRUMENT_MASTER_NOT_RETAINED"
        ),
    ):
        module.capture_task9_production_startup_angel_facts(
            providers=providers,
            startup_capture_id="startup-master-required",
        )


def test_capture_blockers_must_use_canonical_tuple_contract(
    monkeypatch,
):
    _install_full_quotes(monkeypatch)

    providers = _providers()

    pipeline = providers.option_decision_pipeline

    pipeline.capture_option_inputs = lambda **_: (
        SimpleNamespace(
            blockers=["NOT_A_TUPLE"],
            warnings=(),
        )
    )

    with pytest.raises(
        TypeError,
        match="option capture blockers must be a tuple",
    ):
        module.capture_task9_production_startup_angel_facts(
            providers=providers,
            startup_capture_id="startup-invalid-blockers",
        )
