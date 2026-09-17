from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import services.certification.task9_production_startup_acquisition as module
from services.broker.shared_client import (
    get_certification_market_client,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
)


NOW = datetime(
    2026,
    8,
    17,
    6,
    30,
    tzinfo=timezone.utc,
)


class AnalysisPipeline:
    def analyse(self, *_args, **_kwargs):
        return None


class OptionPipeline:
    def __init__(
        self,
        *,
        client,
        master,
    ):
        self.option_chain_builder = (
            SimpleNamespace(
                market_client=client,
                instrument_master=master,
            )
        )

        self.calls = []

    def capture_option_inputs(
        self,
        **kwargs,
    ):
        self.calls.append(
            dict(kwargs)
        )

        market = kwargs["underlying"]
        exchange = kwargs["option_exchange"]

        return SimpleNamespace(
            blockers=(),
                warnings=(),
                marker=(
                market,
                exchange,
            )
        )

    def analyse(self, *_args, **_kwargs):
        return None


class Master:
    def __init__(self):
        self.instruments = [
            {
                "name": "NIFTY",
                "exch_seg": "NFO",
                "instrumenttype": "OPTIDX",
            },
            {
                "name": "SENSEX",
                "exch_seg": "BFO",
                "instrumenttype": "OPTIDX",
            },
            {
                "name": "INDIA VIX",
                "exch_seg": "NSE",
                "instrumenttype": "AMXIDX",
            },
        ]

    def get_metadata(self):
        return {
            "record_count": len(
                self.instruments
            ),
            "fetched_at": NOW,
        }


def test_startup_acquisition_reuses_existing_owners(
    monkeypatch,
):
    client = get_certification_market_client()
    master = Master()

    option_pipeline = OptionPipeline(
        client=client,
        master=master,
    )

    providers = CertifiedRuntimeProviderBundleV1(
        quote_reader=lambda *_: None,
        analysis_pipeline=AnalysisPipeline(),
        option_decision_pipeline=option_pipeline,
        clock=lambda: NOW,
    )

    nifty = SimpleNamespace(
        ltp=25000.0,
        provider_timestamp=NOW,
        received_at=NOW,
    )
    sensex = SimpleNamespace(
        ltp=80000.0,
        provider_timestamp=NOW,
        received_at=NOW,
    )
    full_quotes = SimpleNamespace(
        nifty=nifty,
        sensex=sensex,
    )

    monkeypatch.setattr(
        module,
        "fetch_canonical_two_market_full_quotes",
        lambda supplied_client, *, clock: (
            full_quotes
            if (
                supplied_client is client
                and clock is providers.clock
            )
            else pytest.fail(
                "startup must use existing "
                "client and clock"
            )
        ),
    )

    vix_capture = object()

    class VixReader:
        def __init__(
            self,
            *,
            master_fetcher,
            market_client,
            clock,
        ):
            assert market_client is client
            assert clock is providers.clock

            # This must return existing retained records;
            # it must not trigger another master fetch.
            assert master_fetcher() is master.instruments

        def capture(
            self,
            capture_id,
        ):
            assert capture_id == "startup-1"
            return vix_capture

    monkeypatch.setattr(
        module,
        "IndiaVixLiveReader",
        VixReader,
    )

    class Retained:
        def __init__(
            self,
            **kwargs,
        ):
            self.kwargs = kwargs

    monkeypatch.setattr(
        module,
        "Task9RetainedAngelStartupCapturesV1",
        Retained,
    )

    result = (
        module.capture_task9_production_startup_angel_facts(
            providers=providers,
            startup_capture_id="startup-1",
        )
    )

    assert (
        result.kwargs["client"]
        is client
    )

    assert (
        result.kwargs["request_controller"]
        is client.request_controller
    )

    assert (
        tuple(
            item["underlying"]
            for item in option_pipeline.calls
        )
        == (
            "NIFTY",
            "SENSEX",
        )
    )

    assert (
        tuple(
            item["option_exchange"]
            for item in option_pipeline.calls
        )
        == (
            "NFO",
            "BFO",
        )
    )

    assert (
        result.kwargs[
            "instrument_master_records"
        ]
        == tuple(master.instruments)
    )

    assert (
        result.kwargs[
            "india_vix_capture"
        ]
        is vix_capture
    )

    assert (
        result.kwargs[
            "execution_mode"
        ]
        == "PAPER"
    )

    assert (
        result.kwargs[
            "broker_order_submission"
        ]
        is False
    )

    assert (
        result.kwargs[
            "live_execution_eligible"
        ]
        is False
    )


def test_startup_acquisition_rejects_wrong_provider_bundle():
    with pytest.raises(
        TypeError,
        match="providers",
    ):
        module.capture_task9_production_startup_angel_facts(
            providers=object(),
            startup_capture_id="startup-1",
        )
