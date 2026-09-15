"""Assemble canonical Task 9 Angel startup proofs from retained live captures.

This boundary performs no provider acquisition, authentication, WebSocket
connection, historical request, or broker/order action.  It converts already
acquired production facts into the canonical A7 proof bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.broker.market_data_control import (
    MarketDataRequestController,
)
from services.certification.task9_angel_auth_session_proof_producer import (
    produce_task9_angel_auth_session_proof,
)
from services.certification.task9_angel_india_vix_proof_producer import (
    produce_task9_angel_india_vix_proof,
)
from services.certification.task9_angel_instrument_master_proof_producer import (
    produce_task9_angel_instrument_master_proof,
)
from services.certification.task9_angel_live_proof_bundle import (
    Task9AngelLiveProofBundleV1,
)
from services.certification.task9_angel_option_proof_producer import (
    produce_task9_angel_greeks_proof,
    produce_task9_angel_option_full_proof,
)
from services.certification.task9_angel_request_budget_proof_producer import (
    produce_task9_angel_request_budget_proof,
)
from services.certification.task9_angel_spot_full_proof_producer import (
    produce_task9_angel_spot_full_proofs,
)
from services.contracts.india_vix_capture_result_v1 import (
    IndiaVixCaptureResultV1,
)
from services.contracts.live_option_capture_result_v1 import (
    LiveOptionCaptureResultV1,
)
from services.broker.two_market_quote_service import (
    CanonicalTwoMarketFullQuotes,
)


@dataclass(frozen=True, slots=True)
class Task9RetainedAngelStartupCapturesV1:
    client: AngelMarketDataClient
    request_controller: MarketDataRequestController

    instrument_master_records: Sequence[
        Mapping[str, object]
    ]
    instrument_master_metadata: Mapping[
        str,
        object,
    ]

    spot_full_quotes: CanonicalTwoMarketFullQuotes

    nifty_option_capture: LiveOptionCaptureResultV1
    sensex_option_capture: LiveOptionCaptureResultV1

    india_vix_capture: IndiaVixCaptureResultV1

    observed_at: datetime

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_retained_angel_startup_captures.v1"
    )

    def __post_init__(self) -> None:
        if type(self.client) is not AngelMarketDataClient:
            raise TypeError("client")

        if (
            type(self.request_controller)
            is not MarketDataRequestController
        ):
            raise TypeError("request_controller")

        if (
            self.client.request_controller
            is not self.request_controller
        ):
            raise ValueError(
                "TASK9_STARTUP_REQUEST_CONTROLLER_IDENTITY_MISMATCH"
            )

        if (
            isinstance(
                self.instrument_master_records,
                (str, bytes),
            )
            or not isinstance(
                self.instrument_master_records,
                Sequence,
            )
        ):
            raise TypeError(
                "instrument_master_records"
            )

        if not isinstance(
            self.instrument_master_metadata,
            Mapping,
        ):
            raise TypeError(
                "instrument_master_metadata"
            )

        if (
            type(self.spot_full_quotes)
            is not CanonicalTwoMarketFullQuotes
        ):
            raise TypeError(
                "spot_full_quotes"
            )

        if (
            type(self.nifty_option_capture)
            is not LiveOptionCaptureResultV1
        ):
            raise TypeError(
                "nifty_option_capture"
            )

        if (
            type(self.sensex_option_capture)
            is not LiveOptionCaptureResultV1
        ):
            raise TypeError(
                "sensex_option_capture"
            )

        if (
            self.nifty_option_capture.underlying_symbol
            != "NIFTY"
            or self.nifty_option_capture.option_exchange
            != "NFO"
        ):
            raise ValueError(
                "TASK9_NIFTY_OPTION_CAPTURE_IDENTITY_MISMATCH"
            )

        if (
            self.sensex_option_capture.underlying_symbol
            != "SENSEX"
            or self.sensex_option_capture.option_exchange
            != "BFO"
        ):
            raise ValueError(
                "TASK9_SENSEX_OPTION_CAPTURE_IDENTITY_MISMATCH"
            )

        if (
            type(self.india_vix_capture)
            is not IndiaVixCaptureResultV1
        ):
            raise TypeError(
                "india_vix_capture"
            )

        if (
            not isinstance(
                self.observed_at,
                datetime,
            )
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError(
                "observed_at"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 startup captures must remain PAPER-only"
            )

        if (
            self.schema_version
            != "task9_retained_angel_startup_captures.v1"
        ):
            raise ValueError(
                "schema_version"
            )


def build_task9_angel_live_proof_bundle_from_retained_captures(
    *,
    captures: Task9RetainedAngelStartupCapturesV1,
) -> Task9AngelLiveProofBundleV1:
    """Build A7 from one already-acquired startup capture set."""

    if (
        type(captures)
        is not Task9RetainedAngelStartupCapturesV1
    ):
        raise TypeError("captures")

    auth = produce_task9_angel_auth_session_proof(
        client=captures.client,
        observed_at=captures.observed_at,
    )

    master = produce_task9_angel_instrument_master_proof(
        records=captures.instrument_master_records,
        metadata=captures.instrument_master_metadata,
        observed_at=captures.observed_at,
    )

    spots = produce_task9_angel_spot_full_proofs(
        captures.spot_full_quotes
    )

    option_captures = (
        captures.nifty_option_capture,
        captures.sensex_option_capture,
    )

    option_full = tuple(
        produce_task9_angel_option_full_proof(
            capture
        )
        for capture in option_captures
    )

    greeks = tuple(
        produce_task9_angel_greeks_proof(
            capture
        )
        for capture in option_captures
    )

    india_vix = produce_task9_angel_india_vix_proof(
        captures.india_vix_capture
    )

    request_budget = (
        produce_task9_angel_request_budget_proof(
            controller=(
                captures.request_controller
            ),
            client=captures.client,
            observed_at=captures.observed_at,
        )
    )

    return Task9AngelLiveProofBundleV1(
        auth=auth,
        instrument_master=master,
        spots=spots,
        option_full=option_full,
        greeks=greeks,
        india_vix=india_vix,
        request_budget=request_budget,
    )


__all__ = (
    "Task9RetainedAngelStartupCapturesV1",
    "build_task9_angel_live_proof_bundle_from_retained_captures",
)
