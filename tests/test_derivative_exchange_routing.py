from pathlib import Path


def test_live_runner_routes_option_exchange():
    source = Path(
        "live_option_decision_nifty.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "option_exchange=OPTION_EXCHANGE"
        in source
    )


def test_public_pipeline_accepts_option_exchange():
    source = Path(
        "services/live_option_decision_pipeline.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        source.count(
            'option_exchange="NFO"'
        )
        >= 2
    )


def test_pipeline_propagates_option_exchange_to_core():
    source = Path(
        "services/live_option_decision_pipeline.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "option_exchange=option_exchange"
        in source
    )


def test_pipeline_routes_option_exchange_to_chain_builder():
    source = Path(
        "services/live_option_decision_pipeline.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "option_exchange=option_exchange"
        in source
    )

    assert (
        "self.option_chain_builder.build_chain"
        in source
    )


def test_chain_builder_accepts_option_exchange():
    source = Path(
        "services/live_option_chain_builder.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        source.count(
            'option_exchange="NFO"'
        )
        == 2
    )


def test_chain_builder_routes_exchange_to_instrument_master():
    source = Path(
        "services/live_option_chain_builder.py"
    ).read_text(
        encoding="utf-8"
    )

    nearest_expiry_call = """
            .get_nearest_expiry(
                underlying,
                exchange=option_exchange,
            )
"""

    option_contracts_call = """
            .get_option_contracts(
                underlying,
                exchange=option_exchange,
            )
"""

    assert (
        nearest_expiry_call
        in source
    )

    assert (
        option_contracts_call
        in source
    )


def test_chain_builder_routes_exchange_to_market_data():
    source = Path(
        "services/live_option_chain_builder.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "option_exchange: tokens"
        in source
    )

    assert (
        '"NFO": tokens'
        not in source
    )


def test_bfo_can_be_used_as_dynamic_market_data_key():
    option_exchange = "BFO"

    tokens = [
        "12345",
    ]

    exchange_tokens = {
        option_exchange: tokens
    }

    assert exchange_tokens == {
        "BFO": [
            "12345",
        ]
    }
