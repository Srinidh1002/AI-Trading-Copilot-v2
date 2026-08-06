from datetime import datetime, timedelta, timezone

import pytest

from services.paper_orchestration.certified_live_option_quote_reader import (
    CertifiedLiveOptionQuoteReader,
    CertifiedLiveOptionQuoteV1,
    derivative_exchange_for,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)


class InstrumentMasterStub:
    def __init__(self, contracts):
        self.contracts = contracts
        self.calls = []

    def get_option_contracts(
        self,
        underlying,
        exchange="NFO",
    ):
        self.calls.append((underlying, exchange))
        return self.contracts


class MarketClientStub:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get_ltp(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        self.calls.append(
            (
                exchange,
                tradingsymbol,
                symboltoken,
            )
        )

        if self.error is not None:
            raise self.error

        return self.response


def open_snapshot(tmp_path):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    args, _, trade_service = _admitted_runtime_args(tmp_path)

    result = execute_admitted_plan_simulated_entry(
        **args
    )

    assert result.status == "OPEN"

    snapshot = trade_service.get(
        args["paper_trade_id"]
    )

    assert snapshot is not None
    assert snapshot.position is not None

    return snapshot


def reader_for(snapshot, *, contracts=None, response=None, error=None):
    position = snapshot.position
    assert position is not None

    exchange = derivative_exchange_for(
        position.underlying_symbol,
        position.exchange,
    )

    token = "123456"

    contracts = (
        contracts
        if contracts is not None
        else [
            {
                "symbol": position.option_symbol,
                "token": token,
                "exch_seg": exchange,
                "instrumenttype": "OPTIDX",
            }
        ]
    )

    response = (
        response
        if response is not None
        else {
            "status": True,
            "data": {
                "ltp": position.entry_price + 2.0,
                "tradingsymbol": position.option_symbol,
                "symboltoken": token,
                "exchange": exchange,
                "exchFeedTime": (
                    "05-Aug-2026 14:59:30"
                ),
            },
        }
    )

    master = InstrumentMasterStub(contracts)
    client = MarketClientStub(
        response=response,
        error=error,
    )

    return (
        CertifiedLiveOptionQuoteReader(
            market_client=client,
            instrument_master=master,
            clock=lambda: NOW,
        ),
        master,
        client,
    )


def test_nifty_and_sensex_derivative_exchange_mapping():
    assert derivative_exchange_for(
        "NIFTY",
        None,
    ) == "NFO"

    assert derivative_exchange_for(
        "SENSEX",
        None,
    ) == "BFO"

    assert derivative_exchange_for(
        "NIFTY",
        "NFO",
    ) == "NFO"

    assert derivative_exchange_for(
        "SENSEX",
        "BFO",
    ) == "BFO"


def test_mismatched_derivative_exchange_is_rejected():
    with pytest.raises(
        ValueError,
        match="does not match underlying",
    ):
        derivative_exchange_for(
            "NIFTY",
            "BFO",
        )


def test_reads_exact_persisted_option_quote(tmp_path):
    snapshot = open_snapshot(tmp_path)
    reader, master, client = reader_for(snapshot)

    result = reader(snapshot)

    assert type(result) is CertifiedLiveOptionQuoteV1
    assert result.paper_trade_id == snapshot.paper_trade_id
    assert result.position_id == snapshot.position.position_id
    assert result.option_symbol == snapshot.position.option_symbol
    assert result.option_last_price == (
        snapshot.position.entry_price + 2.0
    )
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False

    assert master.calls == [
        (
            snapshot.position.underlying_symbol,
            result.option_exchange,
        )
    ]

    assert client.calls == [
        (
            result.option_exchange,
            snapshot.position.option_symbol,
            "123456",
        )
    ]


def test_unresolved_option_symbol_fails_closed(tmp_path):
    snapshot = open_snapshot(tmp_path)

    reader, _, client = reader_for(
        snapshot,
        contracts=[
            {
                "symbol": "UNRELATED-CONTRACT",
                "token": "999999",
            }
        ],
    )

    with pytest.raises(
        ValueError,
        match="was not found",
    ):
        reader(snapshot)

    assert client.calls == []


def test_duplicate_tokens_fail_closed(tmp_path):
    snapshot = open_snapshot(tmp_path)
    symbol = snapshot.position.option_symbol

    reader, _, client = reader_for(
        snapshot,
        contracts=[
            {
                "symbol": symbol,
                "token": "111",
            },
            {
                "symbol": symbol,
                "token": "222",
            },
        ],
    )

    with pytest.raises(
        ValueError,
        match="multiple tokens",
    ):
        reader(snapshot)

    assert client.calls == []


def test_quote_failure_propagates_without_mutation(tmp_path):
    snapshot = open_snapshot(tmp_path)
    before = snapshot.to_json()

    reader, _, _ = reader_for(
        snapshot,
        error=RuntimeError("provider unavailable"),
    )

    with pytest.raises(
        RuntimeError,
        match="provider unavailable",
    ):
        reader(snapshot)

    assert snapshot.to_json() == before


def test_provider_identity_mismatch_fails_closed(tmp_path):
    snapshot = open_snapshot(tmp_path)

    reader, _, _ = reader_for(
        snapshot,
        response={
            "status": True,
            "data": {
                "ltp": 101.0,
                "tradingsymbol": "WRONG-SYMBOL",
                "symboltoken": "123456",
                "exchange": "NFO",
                "exchFeedTime": (
                    "05-Aug-2026 14:59:30"
                ),
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="provider option symbol",
    ):
        reader(snapshot)

def response_for(snapshot, **changes):
    position = snapshot.position
    assert position is not None

    exchange = derivative_exchange_for(
        position.underlying_symbol,
        position.exchange,
    )

    data = {
        "ltp": position.entry_price + 2.0,
        "tradingsymbol": position.option_symbol,
        "symboltoken": "123456",
        "exchange": exchange,
        "exchFeedTime": "05-Aug-2026 14:59:30",
    }
    data.update(changes)

    return {
        "status": True,
        "data": data,
    }


def test_quote_uses_provider_issued_timestamp(tmp_path):
    snapshot = open_snapshot(tmp_path)
    reader, _, _ = reader_for(snapshot)

    result = reader(snapshot)

    assert result.provider_timestamp == datetime(
        2026,
        8,
        5,
        14,
        59,
        30,
        tzinfo=timezone(
            timedelta(
                hours=5,
                minutes=30,
            )
        ),
    )


def test_false_provider_status_fails_closed(tmp_path):
    snapshot = open_snapshot(tmp_path)

    response = response_for(snapshot)
    response["status"] = False

    reader, _, _ = reader_for(
        snapshot,
        response=response,
    )

    with pytest.raises(
        ValueError,
        match="status must be true",
    ):
        reader(snapshot)


@pytest.mark.parametrize(
    "changes",
    [
        {"exchFeedTime": None},
        {"exchFeedTime": ""},
        {"exchFeedTime": "bad"},
        {"exchFeedTime": True},
    ],
)
def test_missing_or_invalid_provider_timestamp_fails_closed(
    tmp_path,
    changes,
):
    snapshot = open_snapshot(tmp_path)

    reader, _, _ = reader_for(
        snapshot,
        response=response_for(
            snapshot,
            **changes,
        ),
    )

    with pytest.raises(
        ValueError,
        match="provider timestamp",
    ):
        reader(snapshot)


def test_naive_iso_provider_timestamp_is_rejected(
    tmp_path,
):
    snapshot = open_snapshot(tmp_path)

    reader, _, _ = reader_for(
        snapshot,
        response=response_for(
            snapshot,
            exchFeedTime="2026-08-05T09:29:30",
        ),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        reader(snapshot)


def test_stale_provider_timestamp_fails_closed(
    tmp_path,
):
    snapshot = open_snapshot(tmp_path)

    reader, _, _ = reader_for(
        snapshot,
        response=response_for(
            snapshot,
            exchFeedTime="2026-08-05T09:24:59+00:00",
        ),
    )

    with pytest.raises(
        ValueError,
        match="stale",
    ):
        reader(snapshot)


def test_future_provider_timestamp_fails_closed(
    tmp_path,
):
    snapshot = open_snapshot(tmp_path)

    reader, _, _ = reader_for(
        snapshot,
        response=response_for(
            snapshot,
            exchFeedTime="2026-08-05T09:30:06+00:00",
        ),
    )

    with pytest.raises(
        ValueError,
        match="future skew",
    ):
        reader(snapshot)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-05T09:25:00+00:00",
        "2026-08-05T09:30:05+00:00",
    ],
)
def test_provider_timestamp_boundaries_are_allowed(
    tmp_path,
    timestamp,
):
    snapshot = open_snapshot(tmp_path)

    reader, _, _ = reader_for(
        snapshot,
        response=response_for(
            snapshot,
            exchFeedTime=timestamp,
        ),
    )

    result = reader(snapshot)

    assert result.provider_timestamp is not None


@pytest.mark.parametrize(
    "field",
    [
        "exchFeedTime",
        "exchangeTimestamp",
        "timestamp",
    ],
)
def test_supported_provider_timestamp_fields(
    tmp_path,
    field,
):
    snapshot = open_snapshot(tmp_path)

    response = response_for(snapshot)
    value = response["data"].pop("exchFeedTime")
    response["data"][field] = value

    reader, _, _ = reader_for(
        snapshot,
        response=response,
    )

    result = reader(snapshot)

    assert result.provider_timestamp is not None
