from datetime import datetime
from zoneinfo import ZoneInfo

from services.certification.task9_option_oi_change_authority import (
    Task9OptionOiChangeAuthority,
    Task9OptionOiSnapshotStore,
)


IST = ZoneInfo("Asia/Kolkata")


def _contract(
    *,
    oi,
    provider_change=None,
):
    value = {
        "token": "NIFTY-25000-CE",
        "symbol": "NIFTY26AUG2625000CE",
        "expiry": "2026-08-26",
        "strike": 25000.0,
        "option_type": "CE",
        "open_interest": oi,
    }

    if provider_change is not None:
        value["change_in_open_interest"] = (
            provider_change
        )

    return value


def test_provider_native_oi_change_is_ignored_on_baseline(
    tmp_path,
):
    authority = Task9OptionOiChangeAuthority(
        Task9OptionOiSnapshotStore(
            tmp_path / "oi.json"
        )
    )

    result = authority.enrich(
        underlying_symbol="NIFTY",
        spot_exchange="NSE",
        option_exchange="NFO",
        provider_timestamp=datetime(
            2026,
            8,
            17,
            10,
            0,
            tzinfo=IST,
        ),
        contracts=[
            _contract(
                oi=1000,
                provider_change=999999,
            )
        ],
    )

    assert result.status == "BASELINE_SAVED"
    assert result.provider_count == 0
    assert result.derived_count == 0
    assert (
        result.contracts[0].get(
            "change_in_open_interest"
        )
        is None
    )


def test_same_session_change_is_derived_not_provider_native(
    tmp_path,
):
    authority = Task9OptionOiChangeAuthority(
        Task9OptionOiSnapshotStore(
            tmp_path / "oi.json"
        )
    )

    authority.enrich(
        underlying_symbol="NIFTY",
        spot_exchange="NSE",
        option_exchange="NFO",
        provider_timestamp=datetime(
            2026,
            8,
            17,
            10,
            0,
            tzinfo=IST,
        ),
        contracts=[
            _contract(
                oi=1000,
                provider_change=777777,
            )
        ],
    )

    result = authority.enrich(
        underlying_symbol="NIFTY",
        spot_exchange="NSE",
        option_exchange="NFO",
        provider_timestamp=datetime(
            2026,
            8,
            17,
            10,
            1,
            tzinfo=IST,
        ),
        contracts=[
            _contract(
                oi=1125,
                provider_change=-888888,
            )
        ],
    )

    assert (
        result.status
        == "DERIVED_FROM_PREVIOUS_LIVE_SNAPSHOT"
    )
    assert result.provider_count == 0
    assert result.derived_count == 1
    assert result.matched_count == 1
    assert (
        result.contracts[0][
            "change_in_open_interest"
        ]
        == 125
    )


def test_negative_same_session_change_is_derived(
    tmp_path,
):
    authority = Task9OptionOiChangeAuthority(
        Task9OptionOiSnapshotStore(
            tmp_path / "oi.json"
        )
    )

    authority.enrich(
        underlying_symbol="SENSEX",
        spot_exchange="BSE",
        option_exchange="BFO",
        provider_timestamp=datetime(
            2026,
            8,
            17,
            11,
            0,
            tzinfo=IST,
        ),
        contracts=[
            _contract(
                oi=1500,
                provider_change=500,
            )
        ],
    )

    result = authority.enrich(
        underlying_symbol="SENSEX",
        spot_exchange="BSE",
        option_exchange="BFO",
        provider_timestamp=datetime(
            2026,
            8,
            17,
            11,
            1,
            tzinfo=IST,
        ),
        contracts=[
            _contract(
                oi=1400,
                provider_change=999,
            )
        ],
    )

    assert result.provider_count == 0
    assert result.derived_count == 1
    assert (
        result.contracts[0][
            "change_in_open_interest"
        ]
        == -100
    )
