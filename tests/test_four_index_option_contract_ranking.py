from datetime import date, datetime, timezone

import pytest

from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_chain_metric_v1 import (
    OptionChainMetricV1,
)
from services.contracts.option_contract_universe_v1 import (
    OptionContractUniverseV1,
)
from services.contracts.option_contract_v1 import (
    OptionContractV1,
)
from services.option_contract_ranking.ranking_pipeline import (
    build_canonical_option_contract_ranking,
)


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)
EXPIRY = date(2026, 7, 30)


@pytest.mark.parametrize(
    "symbol,exchange,bias,signal,option_type",
    [
        ("NIFTY", "NSE", "BULLISH", "BULLISH", "CALL"),
        ("NIFTY", "NSE", "BEARISH", "BEARISH", "PUT"),
        ("BANKNIFTY", "NSE", "BULLISH", "BULLISH", "CALL"),
        ("BANKNIFTY", "NSE", "BEARISH", "BEARISH", "PUT"),
        ("FINNIFTY", "NSE", "BULLISH", "BULLISH", "CALL"),
        ("FINNIFTY", "NSE", "BEARISH", "BEARISH", "PUT"),
        ("SENSEX", "BSE", "BULLISH", "BULLISH", "CALL"),
        ("SENSEX", "BSE", "BEARISH", "BEARISH", "PUT"),
    ],
)
def test_four_index_directional_ranking(
    symbol,
    exchange,
    bias,
    signal,
    option_type,
):
    metric = OptionChainMetricV1(
        metric_name="PCR_OPEN_INTEREST",
        value=1.2,
        signal=signal,
        status="VALID",
        sample_size=10,
    )

    intelligence = OptionChainIntelligenceResultV1(
        option_chain_intelligence_result_id=(
            f"intel-{symbol}-{bias}"
        ),
        created_at=NOW,
        option_chain_snapshot_id=f"snapshot-{symbol}",
        option_chain_quality_result_id=f"quality-{symbol}",
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        metrics=(metric,),
        intelligence_status="READY",
        aggregate_bias=bias,
        aggregate_strength=0.8,
        bullish_metrics=(
            ("PCR_OPEN_INTEREST",)
            if bias == "BULLISH"
            else ()
        ),
        bearish_metrics=(
            ("PCR_OPEN_INTEREST",)
            if bias == "BEARISH"
            else ()
        ),
        neutral_metrics=(),
        unavailable_metrics=(),
        valid_metric_count=1,
        unavailable_metric_count=0,
    )

    strike = {
        "NIFTY": 25000,
        "BANKNIFTY": 52000,
        "FINNIFTY": 24000,
        "SENSEX": 82000,
    }[symbol]

    contract = OptionContractV1(
        contract_id=f"{symbol}-{option_type}",
        underlying_symbol=symbol,
        exchange=exchange,
        trading_symbol=f"{symbol}-{strike}-{option_type}",
        option_type=option_type,
        strike=strike,
        expiry_date=EXPIRY,
        lot_size=25,
        market_timestamp=NOW,
        last_price=100,
        bid_price=99,
        ask_price=101,
        open_interest=2000,
        volume=1000,
        implied_volatility=18,
    )

    universe = OptionContractUniverseV1(
        universe_id=f"universe-{symbol}",
        underlying_symbol=symbol,
        exchange=exchange,
        captured_at=NOW,
        spot_price=strike,
        contracts=(contract,),
        source_name="synthetic",
        trusted=True,
    )

    result = build_canonical_option_contract_ranking(
        intelligence_result=intelligence,
        universe=universe,
        now=NOW,
        ranking_id_factory=lambda: f"ranking-{symbol}-{bias}",
    )

    assert result.ranking_status == "RANKED"
    assert result.underlying_symbol == symbol
    assert result.exchange == exchange
    assert result.directional_bias == bias
    assert result.required_option_type == option_type
    assert result.selected_candidate is not None
    assert (
        result.selected_candidate.contract.option_type
        == option_type
    )


@pytest.mark.parametrize(
    "symbol,correct_exchange,wrong_exchange",
    [
        ("NIFTY", "NSE", "BSE"),
        ("BANKNIFTY", "NSE", "BSE"),
        ("FINNIFTY", "NSE", "BSE"),
        ("SENSEX", "BSE", "NSE"),
    ],
)
def test_cross_exchange_contract_identity_is_rejected(
    symbol,
    correct_exchange,
    wrong_exchange,
):
    with pytest.raises(ValueError):
        OptionContractV1(
            contract_id="invalid",
            underlying_symbol=symbol,
            exchange=wrong_exchange,
            trading_symbol="INVALID",
            option_type="CALL",
            strike=25000,
            expiry_date=EXPIRY,
            lot_size=25,
            market_timestamp=NOW,
        )