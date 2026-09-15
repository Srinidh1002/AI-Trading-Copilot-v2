from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_option_oi_change_authority import (
    Task9OptionOiChangeAuthority,
    Task9OptionOiSnapshotStore,
)


IST = ZoneInfo("Asia/Kolkata")
T0 = datetime(
    2026,
    8,
    13,
    14,
    0,
    tzinfo=IST,
)


def contract(
    *,
    token="100",
    strike=25000,
    option_type="CE",
    expiry="2026-08-20",
    oi=1000,
    change=None,
):
    value = {
        "token": token,
        "symbol": (
            f"NIFTY20AUG26{strike}"
            f"{option_type}"
        ),
        "option_type": option_type,
        "expiry": expiry,
        "strike": strike,
        "open_interest": oi,
    }

    if change is not None:
        value[
            "change_in_open_interest"
        ] = change

    return value


def authority(tmp_path):
    return Task9OptionOiChangeAuthority(
        Task9OptionOiSnapshotStore(
            tmp_path
            / "option-oi-snapshots.json"
        )
    )


def enrich(
    value,
    *,
    timestamp,
    contracts,
):
    return value.enrich(
        underlying_symbol="NIFTY",
        spot_exchange="NSE",
        option_exchange="NFO",
        provider_timestamp=timestamp,
        contracts=contracts,
    )


def test_first_snapshot_is_baseline_only(
    tmp_path,
):
    result = enrich(
        authority(tmp_path),
        timestamp=T0,
        contracts=(
            contract(),
            contract(
                token="200",
                option_type="PE",
                oi=1200,
            ),
        ),
    )

    assert result.status == "BASELINE_SAVED"

    assert all(
        item.get(
            "change_in_open_interest"
        )
        is None
        for item in result.contracts
    )


def test_duplicate_contract_identity_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="DUPLICATE_IDENTITY"):
        enrich(authority(tmp_path), timestamp=T0, contracts=(contract(), contract()))


def test_second_snapshot_derives_exact_oi_delta(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(
            contract(oi=1000),
            contract(
                token="200",
                option_type="PE",
                oi=1200,
            ),
        ),
    )

    result = enrich(
        value,
        timestamp=T0 + timedelta(minutes=1),
        contracts=(
            contract(oi=1035),
            contract(
                token="200",
                option_type="PE",
                oi=1170,
            ),
        ),
    )

    assert (
        result.status
        == "DERIVED_FROM_PREVIOUS_LIVE_SNAPSHOT"
    )

    assert result.derived_count == 2
    assert result.matched_count == 2

    assert (
        result.contracts[0][
            "change_in_open_interest"
        ]
        == 35
    )

    assert (
        result.contracts[1][
            "change_in_open_interest"
        ]
        == -30
    )


def test_restart_recovers_previous_snapshot(
    tmp_path,
):
    first = authority(tmp_path)

    enrich(
        first,
        timestamp=T0,
        contracts=(contract(oi=1000),),
    )

    restarted = authority(tmp_path)

    result = enrich(
        restarted,
        timestamp=T0 + timedelta(minutes=1),
        contracts=(contract(oi=1040),),
    )

    assert result.derived_count == 1

    assert (
        result.contracts[0][
            "change_in_open_interest"
        ]
        == 40
    )


def test_duplicate_same_timestamp_replays_same_change(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(contract(oi=1000),),
    )

    timestamp = T0 + timedelta(minutes=1)

    first = enrich(
        value,
        timestamp=timestamp,
        contracts=(contract(oi=1025),),
    )

    duplicate = enrich(
        value,
        timestamp=timestamp,
        contracts=(contract(oi=1025),),
    )

    assert (
        first.contracts[0][
            "change_in_open_interest"
        ]
        == 25
    )

    assert (
        duplicate.status
        == "DUPLICATE_SAME_SNAPSHOT"
    )

    assert (
        duplicate.contracts[0][
            "change_in_open_interest"
        ]
        == 25
    )


def test_same_timestamp_conflicting_oi_fails_closed(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(contract(oi=1000),),
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_OPTION_OI_SNAPSHOT_CONFLICT"
        ),
    ):
        enrich(
            value,
            timestamp=T0,
            contracts=(contract(oi=1001),),
        )


def test_out_of_order_snapshot_fails_closed(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(contract(),),
    )

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_OPTION_OI_SNAPSHOT_OUT_OF_ORDER"
        ),
    ):
        enrich(
            value,
            timestamp=T0 - timedelta(seconds=1),
            contracts=(contract(),),
        )


def test_new_trading_day_does_not_compare_with_yesterday(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(contract(oi=1000),),
    )

    result = enrich(
        value,
        timestamp=T0 + timedelta(days=1),
        contracts=(contract(oi=1100),),
    )

    assert (
        result.status
        == "NEW_TRADING_DAY_BASELINE"
    )

    assert result.derived_count == 0

    assert (
        result.contracts[0].get(
            "change_in_open_interest"
        )
        is None
    )


def test_different_contract_identity_is_not_compared(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(
            contract(
                token="100",
                strike=25000,
                oi=1000,
            ),
        ),
    )

    result = enrich(
        value,
        timestamp=T0 + timedelta(minutes=1),
        contracts=(
            contract(
                token="999",
                strike=25000,
                oi=1500,
            ),
        ),
    )

    assert result.derived_count == 0

    assert (
        result.contracts[0].get(
            "change_in_open_interest"
        )
        is None
    )


def test_provider_supplied_oi_change_is_ignored_and_derived(
    tmp_path,
):
    value = authority(tmp_path)

    enrich(
        value,
        timestamp=T0,
        contracts=(contract(oi=1000),),
    )

    result = enrich(
        value,
        timestamp=T0 + timedelta(minutes=1),
        contracts=(
            contract(
                oi=1200,
                change=77,
            ),
        ),
    )

    assert result.provider_count == 0
    assert result.derived_count == 1
    assert result.matched_count == 1
    assert (
        result.contracts[0][
            "change_in_open_interest"
        ]
        == 200
    )

