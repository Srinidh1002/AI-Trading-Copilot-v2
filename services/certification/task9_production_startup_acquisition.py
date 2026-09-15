"""Single-acquisition Task 9 production startup Angel evidence.

This is the only Task 9 startup boundary that performs the required Angel
read-only acquisition. It reuses the already-composed certification provider
bundle, its Angel client, its request controller, and its instrument master.

No WebSocket creation and no broker/order operation exist here.
"""

from __future__ import annotations

from datetime import datetime

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.broker.two_market_quote_service import (
    fetch_canonical_two_market_full_quotes,
)
from services.certification.task9_production_startup_proof_assembler import (
    Task9RetainedAngelStartupCapturesV1,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
)
from services.paper_orchestration.india_vix_live_reader import (
    IndiaVixLiveReader,
)


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def capture_task9_production_startup_angel_facts(
    *,
    providers: CertifiedRuntimeProviderBundleV1,
    startup_capture_id: str,
) -> Task9RetainedAngelStartupCapturesV1:
    """Acquire one canonical startup evidence set using existing owners."""

    if type(providers) is not CertifiedRuntimeProviderBundleV1:
        raise TypeError("providers")

    if (
        type(startup_capture_id) is not str
        or not startup_capture_id.strip()
    ):
        raise ValueError("startup_capture_id")

    option_pipeline = (
        providers.option_decision_pipeline
    )

    option_builder = getattr(
        option_pipeline,
        "option_chain_builder",
        None,
    )

    if option_builder is None:
        raise TypeError(
            "option_decision_pipeline must expose "
            "option_chain_builder"
        )

    client = getattr(
        option_builder,
        "market_client",
        None,
    )

    if type(client) is not AngelMarketDataClient:
        raise TypeError(
            "certified option builder must retain "
            "AngelMarketDataClient"
        )

    request_controller = getattr(
        client,
        "request_controller",
        None,
    )

    if request_controller is None:
        raise TypeError(
            "Angel client must retain request_controller"
        )

    instrument_master = getattr(
        option_builder,
        "instrument_master",
        None,
    )

    if instrument_master is None:
        raise TypeError(
            "certified option builder must retain "
            "instrument_master"
        )

    # One canonical Angel FULL request contains both NIFTY and SENSEX.
    full_quotes = (
        fetch_canonical_two_market_full_quotes(
            client,
            clock=providers.clock,
        )
    )

    nifty_quote = full_quotes.nifty
    sensex_quote = full_quotes.sensex

    # Each option market is acquired exactly once through the existing
    # certified capture seam. The chain builder owns master loading.
    nifty_option_capture = (
        option_pipeline.capture_option_inputs(
            underlying="NIFTY",
            spot_price=nifty_quote.ltp,
            option_exchange="NFO",
            provider_timestamp=(
                nifty_quote.provider_timestamp
            ),
            evaluated_at=nifty_quote.received_at,
        )
    )

    sensex_option_capture = (
        option_pipeline.capture_option_inputs(
            underlying="SENSEX",
            spot_price=sensex_quote.ltp,
            option_exchange="BFO",
            provider_timestamp=(
                sensex_quote.provider_timestamp
            ),
            evaluated_at=sensex_quote.received_at,
        )
    )

    # A capture result may represent a fail-closed option acquisition
    # rather than a successful chain.  Reject that causal failure before
    # asserting downstream retained-master state; otherwise an upstream
    # provider/builder failure can be misreported as
    # TASK9_STARTUP_INSTRUMENT_MASTER_NOT_RETAINED.
    for market, capture in (
        ("NIFTY", nifty_option_capture),
        ("SENSEX", sensex_option_capture),
    ):
        blockers = getattr(
            capture,
            "blockers",
            None,
        )

        if blockers is None:
            raise TypeError(
                f"{market} option capture must expose blockers"
            )

        if not isinstance(
            blockers,
            tuple,
        ):
            raise TypeError(
                f"{market} option capture blockers must be a tuple"
            )

        if blockers:
            blocker_text = "|".join(
                str(value).strip()
                for value in blockers
                if str(value).strip()
            )

            raise RuntimeError(
                "TASK9_STARTUP_"
                f"{market}_OPTION_CAPTURE_BLOCKED:"
                f"{blocker_text}"
            )

    # Option-chain acquisition has already resolved/loaded the existing
    # master. Reuse those exact retained records and metadata.
    master_records = getattr(
        instrument_master,
        "instruments",
        None,
    )

    if not isinstance(
        master_records,
        list,
    ):
        raise RuntimeError(
            "TASK9_STARTUP_INSTRUMENT_MASTER_NOT_RETAINED"
        )

    get_metadata = getattr(
        instrument_master,
        "get_metadata",
        None,
    )

    if not callable(get_metadata):
        raise TypeError(
            "instrument_master must expose get_metadata()"
        )

    master_metadata = get_metadata()

    # INDIA_VIX acquisition is optional at startup capability bootstrap, but
# it is required by the Task 9 per-cycle decision policy; when acquired
# here it must use the same client
    # and the already-retained master. The lambda prevents a second master
    # download while preserving the canonical VIX reader contract.
    vix_reader = IndiaVixLiveReader(
        master_fetcher=(
            lambda: master_records
        ),
        market_client=client,
        clock=providers.clock,
    )

    india_vix_capture = vix_reader.capture(
        startup_capture_id.strip()
    )

    observed_at = _aware(
        providers.clock(),
        "observed_at",
    )

    return Task9RetainedAngelStartupCapturesV1(
        client=client,
        request_controller=request_controller,
        instrument_master_records=(
            tuple(master_records)
        ),
        instrument_master_metadata=(
            master_metadata
        ),
        spot_full_quotes=full_quotes,
        nifty_option_capture=nifty_option_capture,
        sensex_option_capture=sensex_option_capture,
        india_vix_capture=india_vix_capture,
        observed_at=observed_at,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "capture_task9_production_startup_angel_facts",
)
