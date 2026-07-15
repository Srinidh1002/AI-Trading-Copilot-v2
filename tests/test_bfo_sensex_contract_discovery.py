from datetime import (
    datetime,
    timedelta,
)

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)

from services.live_option_chain_builder import (
    LiveOptionChainBuilder,
)


def _future_expiry(days):
    return (
        datetime.now().date()
        + timedelta(
            days=days
        )
    ).strftime(
        "%d%b%Y"
    ).upper()


def _instrument(
    *,
    exchange,
    underlying,
    symbol,
    token,
    strike,
    expiry,
    instrument_type="OPTIDX",
):
    return {
        "exch_seg": exchange,
        "instrumenttype": instrument_type,
        "symbol": symbol,
        "name": underlying,
        "token": token,
        "strike": strike,
        "expiry": expiry,
        "lotsize": "20",
    }


def _build_mixed_instruments():
    nifty_expiry = _future_expiry(
        7
    )

    sensex_near_expiry = _future_expiry(
        3
    )

    sensex_far_expiry = _future_expiry(
        10
    )

    return {
        "nifty_expiry": nifty_expiry,
        "sensex_near_expiry": (
            sensex_near_expiry
        ),
        "sensex_far_expiry": (
            sensex_far_expiry
        ),
        "instruments": [
            _instrument(
                exchange="NFO",
                underlying="NIFTY",
                symbol=(
                    "NIFTYTEST24000CE"
                ),
                token="NFO_CE",
                strike="2400000",
                expiry=nifty_expiry,
            ),
            _instrument(
                exchange="NFO",
                underlying="NIFTY",
                symbol=(
                    "NIFTYTEST24000PE"
                ),
                token="NFO_PE",
                strike="2400000",
                expiry=nifty_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXTEST80000CE"
                ),
                token="BFO_NEAR_CE",
                strike="8000000",
                expiry=sensex_near_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXTEST80000PE"
                ),
                token="BFO_NEAR_PE",
                strike="8000000",
                expiry=sensex_near_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXTEST80500CE"
                ),
                token="BFO_80500_CE",
                strike="8050000",
                expiry=sensex_near_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXTEST80500PE"
                ),
                token="BFO_80500_PE",
                strike="8050000",
                expiry=sensex_near_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXFAR80000CE"
                ),
                token="BFO_FAR_CE",
                strike="8000000",
                expiry=sensex_far_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXFAR80000PE"
                ),
                token="BFO_FAR_PE",
                strike="8000000",
                expiry=sensex_far_expiry,
            ),
            _instrument(
                exchange="NFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXWRONG80000CE"
                ),
                token="WRONG_NFO_SENSEX",
                strike="8000000",
                expiry=sensex_near_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="NIFTY",
                symbol=(
                    "NIFTYWRONG24000CE"
                ),
                token="WRONG_BFO_NIFTY",
                strike="2400000",
                expiry=nifty_expiry,
            ),
            _instrument(
                exchange="BFO",
                underlying="SENSEX",
                symbol=(
                    "SENSEXFUT80000"
                ),
                token="BFO_FUTURE",
                strike="8000000",
                expiry=sensex_near_expiry,
                instrument_type="FUTIDX",
            ),
        ],
    }


def _build_master():
    fixture = (
        _build_mixed_instruments()
    )

    master = AngelInstrumentMaster()

    master.instruments = fixture[
        "instruments"
    ]

    return (
        master,
        fixture,
    )


def test_nifty_nfo_returns_only_nfo_nifty_contracts():
    master, _ = _build_master()

    contracts = (
        master.get_option_contracts(
            underlying="NIFTY",
            exchange="NFO",
        )
    )

    tokens = {
        contract["token"]
        for contract in contracts
    }

    assert tokens == {
        "NFO_CE",
        "NFO_PE",
    }


def test_sensex_bfo_returns_only_bfo_sensex_contracts():
    master, _ = _build_master()

    contracts = (
        master.get_option_contracts(
            underlying="SENSEX",
            exchange="BFO",
        )
    )

    tokens = {
        contract["token"]
        for contract in contracts
    }

    assert tokens == {
        "BFO_NEAR_CE",
        "BFO_NEAR_PE",
        "BFO_80500_CE",
        "BFO_80500_PE",
        "BFO_FAR_CE",
        "BFO_FAR_PE",
    }


def test_bfo_and_nfo_contracts_do_not_mix():
    master, _ = _build_master()

    nifty_contracts = (
        master.get_option_contracts(
            underlying="NIFTY",
            exchange="NFO",
        )
    )

    sensex_contracts = (
        master.get_option_contracts(
            underlying="SENSEX",
            exchange="BFO",
        )
    )

    nifty_tokens = {
        contract["token"]
        for contract in nifty_contracts
    }

    sensex_tokens = {
        contract["token"]
        for contract in sensex_contracts
    }

    assert (
        nifty_tokens
        & sensex_tokens
    ) == set()

    assert (
        "WRONG_NFO_SENSEX"
        not in sensex_tokens
    )

    assert (
        "WRONG_BFO_NIFTY"
        not in nifty_tokens
    )


def test_available_expiries_are_isolated_by_exchange():
    master, fixture = _build_master()

    nifty_expiries = (
        master.get_available_expiries(
            underlying="NIFTY",
            exchange="NFO",
        )
    )

    sensex_expiries = (
        master.get_available_expiries(
            underlying="SENSEX",
            exchange="BFO",
        )
    )

    assert [
        item["raw"]
        for item in nifty_expiries
    ] == [
        fixture[
            "nifty_expiry"
        ],
    ]

    assert [
        item["raw"]
        for item in sensex_expiries
    ] == [
        fixture[
            "sensex_near_expiry"
        ],
        fixture[
            "sensex_far_expiry"
        ],
    ]


def test_nearest_sensex_expiry_uses_bfo_contracts():
    master, fixture = _build_master()

    nearest = (
        master.get_nearest_expiry(
            underlying="SENSEX",
            exchange="BFO",
        )
    )

    assert nearest["raw"] == (
        fixture[
            "sensex_near_expiry"
        ]
    )


class RecordingInstrumentMaster:
    def __init__(
        self,
        fixture,
    ):
        self.fixture = fixture
        self.calls = []

    def get_nearest_expiry(
        self,
        underlying,
        exchange="NFO",
    ):
        self.calls.append(
            (
                "get_nearest_expiry",
                underlying,
                exchange,
            )
        )

        return {
            "raw": self.fixture[
                "sensex_near_expiry"
            ]
        }

    def get_option_contracts(
        self,
        underlying,
        exchange="NFO",
    ):
        self.calls.append(
            (
                "get_option_contracts",
                underlying,
                exchange,
            )
        )

        return [
            instrument
            for instrument in self.fixture[
                "instruments"
            ]
            if (
                instrument.get(
                    "exch_seg"
                )
                == exchange
                and instrument.get(
                    "name"
                )
                == underlying
                and instrument.get(
                    "instrumenttype"
                )
                == "OPTIDX"
            )
        ]


class ForbiddenMarketClient:
    def get_market_data(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Market data must not be called "
            "during nearby-contract discovery."
        )


def _build_recording_builder():
    fixture = (
        _build_mixed_instruments()
    )

    instrument_master = (
        RecordingInstrumentMaster(
            fixture
        )
    )

    builder = LiveOptionChainBuilder(
        instrument_master=(
            instrument_master
        ),
        market_client=(
            ForbiddenMarketClient()
        ),
    )

    return (
        builder,
        instrument_master,
        fixture,
    )


def test_chain_builder_requests_sensex_bfo_contracts():
    (
        builder,
        instrument_master,
        _,
    ) = _build_recording_builder()

    builder.get_nearby_contracts(
        underlying="SENSEX",
        spot_price=80200,
        strikes_each_side=1,
        option_exchange="BFO",
    )

    assert instrument_master.calls == [
        (
            "get_nearest_expiry",
            "SENSEX",
            "BFO",
        ),
        (
            "get_option_contracts",
            "SENSEX",
            "BFO",
        ),
    ]


def test_chain_builder_returns_nearby_sensex_bfo_contracts():
    (
        builder,
        _,
        fixture,
    ) = _build_recording_builder()

    result = (
        builder.get_nearby_contracts(
            underlying="SENSEX",
            spot_price=80200,
            strikes_each_side=1,
            option_exchange="BFO",
        )
    )

    contracts = result[
        "contracts"
    ]

    assert contracts

    assert {
        contract["token"]
        for contract in contracts
    } == {
        "BFO_NEAR_CE",
        "BFO_NEAR_PE",
        "BFO_80500_CE",
        "BFO_80500_PE",
    }

    assert all(
        contract["expiry"]
        == fixture[
            "sensex_near_expiry"
        ]
        for contract in contracts
    )

    assert all(
        contract["name"]
        == "SENSEX"
        for contract in contracts
    )

    assert all(
        contract["exch_seg"]
        == "BFO"
        for contract in contracts
    )


def test_nearby_contract_discovery_does_not_call_market_data():
    (
        builder,
        _,
        _,
    ) = _build_recording_builder()

    contracts = (
        builder.get_nearby_contracts(
            underlying="SENSEX",
            spot_price=80200,
            strikes_each_side=1,
            option_exchange="BFO",
        )
    )

    assert contracts


class RecordingMarketClient:
    def __init__(self):
        self.calls = []

    def get_market_data(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(
            {
                "args": args,
                "kwargs": kwargs,
            }
        )

        return {
            "status": True,
            "data": {
                "fetched": [],
                "unfetched": [],
            },
        }


def _build_market_request_builder():
    fixture = (
        _build_mixed_instruments()
    )

    instrument_master = (
        RecordingInstrumentMaster(
            fixture
        )
    )

    market_client = (
        RecordingMarketClient()
    )

    builder = LiveOptionChainBuilder(
        instrument_master=(
            instrument_master
        ),
        market_client=(
            market_client
        ),
    )

    return (
        builder,
        instrument_master,
        market_client,
    )


def test_build_chain_sends_bfo_full_market_data_request():
    (
        builder,
        _,
        market_client,
    ) = _build_market_request_builder()

    try:
        builder.build_chain(
            underlying="SENSEX",
            spot_price=80200,
            strikes_each_side=1,
            option_exchange="BFO",
        )

    except RuntimeError as exc:
        assert (
            "No live option contracts"
            in str(
                exc
            )
        )

    assert len(
        market_client.calls
    ) == 1

    call = market_client.calls[
        0
    ]

    assert call["args"] == ()

    assert call[
        "kwargs"
    ][
        "mode"
    ] == "FULL"

    exchange_tokens = call[
        "kwargs"
    ][
        "exchange_tokens"
    ]

    assert exchange_tokens == {
        "BFO": [
            "BFO_NEAR_CE",
            "BFO_NEAR_PE",
            "BFO_80500_CE",
            "BFO_80500_PE",
        ]
    }


def test_sensex_bfo_market_data_request_has_no_nfo_key():
    (
        builder,
        _,
        market_client,
    ) = _build_market_request_builder()

    try:
        builder.build_chain(
            underlying="SENSEX",
            spot_price=80200,
            strikes_each_side=1,
            option_exchange="BFO",
        )

    except RuntimeError:
        pass

    assert len(
        market_client.calls
    ) == 1

    exchange_tokens = (
        market_client.calls[
            0
        ][
            "kwargs"
        ][
            "exchange_tokens"
        ]
    )

    assert (
        "BFO"
        in exchange_tokens
    )

    assert (
        "NFO"
        not in exchange_tokens
    )

    assert list(
        exchange_tokens
    ) == [
        "BFO",
    ]


class ValidBfoMarketClient:
    def __init__(self):
        self.calls = []

    @staticmethod
    def _market_item(
        token,
        premium,
        bid,
        ask,
        volume,
        open_interest,
    ):
        return {
            "symbolToken": token,
            "ltp": premium,
            "tradeVolume": volume,
            "opnInterest": open_interest,
            "depth": {
                "buy": [
                    {
                        "price": bid,
                    }
                ],
                "sell": [
                    {
                        "price": ask,
                    }
                ],
            },
        }

    def get_market_data(
        self,
        *args,
        **kwargs,
    ):
        self.calls.append(
            {
                "args": args,
                "kwargs": kwargs,
            }
        )

        return {
            "status": True,
            "data": {
                "fetched": [
                    self._market_item(
                        "BFO_NEAR_CE",
                        210.0,
                        209.5,
                        210.5,
                        1200,
                        5400,
                    ),
                    self._market_item(
                        "BFO_NEAR_PE",
                        198.0,
                        197.5,
                        198.5,
                        1300,
                        5600,
                    ),
                    self._market_item(
                        "BFO_80500_CE",
                        145.0,
                        144.5,
                        145.5,
                        900,
                        4100,
                    ),
                    self._market_item(
                        "BFO_80500_PE",
                        255.0,
                        254.5,
                        255.5,
                        1000,
                        4700,
                    ),
                ],
                "unfetched": [],
            },
        }


def _build_valid_bfo_chain_builder():
    fixture = (
        _build_mixed_instruments()
    )

    instrument_master = (
        RecordingInstrumentMaster(
            fixture
        )
    )

    original_get_nearest_expiry = (
        instrument_master.get_nearest_expiry
    )

    def get_nearest_expiry_with_display(
        underlying,
        exchange="NFO",
    ):
        expiry = dict(
            original_get_nearest_expiry(
                underlying,
                exchange=exchange,
            )
        )

        expiry.setdefault(
            "display",
            expiry.get(
                "raw"
            ),
        )

        return expiry

    instrument_master.get_nearest_expiry = (
        get_nearest_expiry_with_display
    )

    market_client = (
        ValidBfoMarketClient()
    )

    builder = LiveOptionChainBuilder(
        instrument_master=(
            instrument_master
        ),
        market_client=(
            market_client
        ),
    )

    return (
        builder,
        instrument_master,
        market_client,
    )


def test_sensex_bfo_response_normalizes_to_valid_chain():
    (
        builder,
        _,
        market_client,
    ) = _build_valid_bfo_chain_builder()

    result = builder.build_chain(
        underlying="SENSEX",
        spot_price=80200,
        strikes_each_side=1,
        option_exchange="BFO",
    )

    assert len(
        market_client.calls
    ) == 1

    assert (
        result["underlying"]
        == "SENSEX"
    )

    assert (
        result["spot_price"]
        == 80200
    )

    assert (
        result["received_contracts"]
        == 4
    )

    assert (
        result["validated_contracts"]
        == 4
    )

    assert (
        result["rejected_contracts"]
        == 0
    )

    assert (
        result["integrity_validated"]
        is True
    )

    assert len(
        result["contracts"]
    ) == 4

    contracts_by_token = {
        contract["token"]: contract
        for contract in result[
            "contracts"
        ]
    }

    assert set(
        contracts_by_token
    ) == {
        "BFO_NEAR_CE",
        "BFO_NEAR_PE",
        "BFO_80500_CE",
        "BFO_80500_PE",
    }

    near_ce = contracts_by_token[
        "BFO_NEAR_CE"
    ]

    assert (
        near_ce["premium"]
        == 210.0
    )

    assert (
        near_ce["bid"]
        == 209.5
    )

    assert (
        near_ce["ask"]
        == 210.5
    )

    assert (
        near_ce["volume"]
        == 1200
    )

    assert (
        near_ce["open_interest"]
        == 5400
    )

    assert (
        near_ce["option_type"]
        == "CE"
    )

    assert (
        near_ce["strike"]
        == 80000.0
    )

    assert (
        near_ce["delta"]
        is None
    )

    assert (
        near_ce["gamma"]
        is None
    )

    assert (
        near_ce["theta"]
        is None
    )

    assert (
        near_ce["vega"]
        is None
    )

    assert (
        near_ce["iv"]
        is None
    )


def test_sensex_bfo_validated_chain_contains_only_bfo_tokens():
    (
        builder,
        _,
        _,
    ) = _build_valid_bfo_chain_builder()

    result = builder.build_chain(
        underlying="SENSEX",
        spot_price=80200,
        strikes_each_side=1,
        option_exchange="BFO",
    )

    tokens = {
        contract["token"]
        for contract in result[
            "contracts"
        ]
    }

    assert tokens

    assert all(
        token.startswith(
            "BFO_"
        )
        for token in tokens
    )

    assert not any(
        token.startswith(
            "NFO_"
        )
        for token in tokens
    )


def test_sensex_bfo_chain_preserves_ce_and_pe_contracts():
    (
        builder,
        _,
        _,
    ) = _build_valid_bfo_chain_builder()

    result = builder.build_chain(
        underlying="SENSEX",
        spot_price=80200,
        strikes_each_side=1,
        option_exchange="BFO",
    )

    option_types = {
        contract[
            "option_type"
        ]
        for contract in result[
            "contracts"
        ]
    }

    assert option_types == {
        "CE",
        "PE",
    }

    contracts_by_type = {
        option_type: [
            contract
            for contract in result[
                "contracts"
            ]
            if contract[
                "option_type"
            ] == option_type
        ]
        for option_type in option_types
    }

    assert len(
        contracts_by_type["CE"]
    ) == 2

    assert len(
        contracts_by_type["PE"]
    ) == 2
