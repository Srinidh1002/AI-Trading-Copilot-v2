"""X4 B4 offline as-of replay, capture integrity, provenance and authority tests."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from services.x4.contracts_v1 import X4BasisReferenceV1
from services.x4.replay_provenance_v1 import (
    X4ReplayArchiveV1,
    replay_x4_historical_v1,
    x4_replay_rows_sha256_v1,
)

NOW = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
UNITS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}
SECONDS = {"5m": 300, "15m": 900, "1h": 3600}
CORE_PROOFS = (
    ("capture", "REVIEW:CAPTURE"),
    ("session", "REVIEW:SESSION"),
    ("candle_time", "REVIEW:BAR_START"),
    ("price_unit", "REVIEW:QUOTE_UNIT"),
)
OI_PROOFS = (("oi_unit", "REVIEW:OI_UNIT"), ("oi_timestamp", "REVIEW:OI_TIME"))
VOLUME_PROOF = (("volume_unit", "REVIEW:VOLUME_UNIT"),)


def identity(market="NIFTY"):
    return SimpleNamespace(
        market_symbol=market,
        instrument_type="FUTURE",
        provider="FYERS",
        provider_symbol=f"FYERS:{market}:FUT",
        canonical_instrument_id=f"FYERS:{market}:20261030:FUT",
        expiry=date(2026, 10, 30),
        contract_metadata_status="VERIFIED",
        metadata_source="TEST_ONLY_VERIFIED_MASTER",
        resolved_at=NOW - timedelta(days=1),
        data_only=True,
        live_execution_eligible=False,
    )


def rows(market="NIFTY", tf="5m", *, now=NOW, price=(100, 101, 102), oi=(1000, 1010, 1030)):
    duration = timedelta(seconds=SECONDS[tf])
    return tuple(
        {
            "provider": "FYERS",
            "provider_symbol": f"FYERS:{market}:FUT",
            "interval": tf,
            "timestamp": int((now - duration * (3 - i)).timestamp()),
            "open": price[i],
            "high": price[i] + 1,
            "low": price[i] - 1,
            "close": price[i],
            "volume": 10 + 10 * i,
            "open_interest": oi[i],
        }
        for i in range(3)
    )


def archive(market="NIFTY", tf="5m", *, data=None, proofs=None, **changes):
    data = rows(market, tf) if data is None else data
    args = dict(
        timeframe=tf,
        session_id="2026-10-01:S1",
        capture_id=f"VERIFIED_TEST:{market}:{tf}",
        archive_id=f"ARCHIVE:{market}:{tf}",
        archived_at=NOW + timedelta(days=1),
        rows=data,
        rows_sha256=x4_replay_rows_sha256_v1(data),
        proof_ids=(CORE_PROOFS + VOLUME_PROOF + OI_PROOFS if proofs is None else proofs),
    )
    args.update(changes)
    return X4ReplayArchiveV1(**args)


def run(*, market="NIFTY", archives=None, checkpoints=(NOW,), required=("5m", "15m"), **changes):
    if archives is None:
        archives = {tf: archive(market, tf) for tf in required}
    args = dict(
        resolved=identity(market),
        archives=archives,
        checkpoints=checkpoints,
        required_timeframes=required,
        freshness_seconds={tf: SECONDS[tf] * 3 for tf in required},
    )
    args.update(changes)
    return replay_x4_historical_v1(**args)


@pytest.mark.parametrize("market", tuple(UNITS))
def test_five_markets_replay_offline_with_noncertifying_result(market):
    out = run(market=market)[0]
    assert out.market == market
    assert out.alignment == "CONSISTENT_UP"
    assert out.status == "PARTIAL"  # No independently verified basis.
    assert out.data_only and not out.certification_eligible
    assert not out.live_execution_eligible and not out.real_provider_semantics_proven
    assert "HISTORICAL_PROVIDER_SEMANTICS_NOT_INDEPENDENTLY_PROVEN" in out.blockers
    assert "RETROSPECTIVE_ARCHIVE_CAPTURE" in out.blockers


def test_determinism_under_reversed_archive_dictionary_insertion_order():
    a = archive(tf="5m")
    b = archive(tf="15m")
    first = run(archives={"5m": a, "15m": b})[0]
    second = run(archives={"15m": b, "5m": a})[0]
    assert first.to_dict() == second.to_dict()
    assert first.sha256() == second.sha256()
    assert first.source_result_sha256 == second.source_result_sha256
    assert first.research_view_sha256 == second.research_view_sha256


def test_prefix_only_blocks_future_candle_from_earlier_signal():
    early = NOW - timedelta(minutes=10)
    first, second = run(checkpoints=(early, NOW))
    assert first.alignment == "INSUFFICIENT_DATA"
    assert second.alignment == "CONSISTENT_UP"
    assert first.source_result_sha256 != second.source_result_sha256


def test_change_to_future_candle_does_not_change_prior_research_values():
    early = NOW - timedelta(minutes=10)
    initial = run(checkpoints=(early, NOW))
    changed = list(rows(tf="5m"))
    changed[-1] = {**changed[-1], "open": 300, "high": 301, "low": 99, "close": 300}
    # The mutated last bar is outside the earlier checkpoint's closed prefix.
    updated = run(
        archives={"5m": archive(tf="5m", data=tuple(changed)), "15m": archive(tf="15m")},
        checkpoints=(early, NOW),
    )
    assert initial[0].source_result_sha256 == updated[0].source_result_sha256
    assert initial[1].source_result_sha256 != updated[1].source_result_sha256
    assert initial[0].capture_sha256_by_timeframe != updated[0].capture_sha256_by_timeframe


def test_no_closed_bars_become_explicit_missing_timeframes():
    first = run(checkpoints=(NOW - timedelta(hours=1),))[0]
    assert first.status == "UNAVAILABLE"
    assert first.alignment == "INSUFFICIENT_DATA"
    assert first.missing_timeframes == ("5m", "15m")


def test_no_archives_are_explicitly_unavailable():
    out = run(archives={})[0]
    assert out.status == "UNAVAILABLE"
    assert out.missing_timeframes == ("5m", "15m")
    assert not out.capture_sha256_by_timeframe


def test_missing_one_timeframe_never_imputed():
    out = run(archives={"5m": archive(tf="5m")})[0]
    assert out.missing_timeframes == ("15m",)
    assert out.alignment == "INSUFFICIENT_DATA"


def test_missing_oi_proofs_cannot_produce_positioning_alignment():
    archives = {tf: archive(tf=tf, proofs=CORE_PROOFS + VOLUME_PROOF) for tf in ("5m", "15m")}
    out = run(archives=archives)[0]
    assert out.alignment == "INSUFFICIENT_DATA"


def test_missing_volume_proofs_do_not_block_verified_price_oi():
    archives = {tf: archive(tf=tf, proofs=CORE_PROOFS + OI_PROOFS) for tf in ("5m", "15m")}
    out = run(archives=archives)[0]
    assert out.alignment == "CONSISTENT_UP"
    assert out.status == "PARTIAL"


@pytest.mark.parametrize("excluded", ("capture", "session", "candle_time", "price_unit"))
def test_missing_required_provenance_rejected_at_archive_construction(excluded):
    proofs = tuple(p for p in CORE_PROOFS if p[0] != excluded)
    with pytest.raises(ValueError, match="provenance"):
        archive(proofs=proofs)


@pytest.mark.parametrize("extra", ("not_allowed", "order", "certification"))
def test_unknown_proof_categories_rejected(extra):
    with pytest.raises(ValueError, match="provenance"):
        archive(proofs=CORE_PROOFS + ((extra, "FAKE"),))


def test_duplicate_proof_categories_rejected():
    with pytest.raises(ValueError, match="provenance"):
        archive(proofs=CORE_PROOFS + (CORE_PROOFS[0],))


def test_archive_hash_mismatch_rejected():
    with pytest.raises(ValueError, match="SHA256"):
        archive(rows_sha256="0" * 64)


def test_archive_is_immutable_including_nested_row_dictionary():
    item = archive()
    with pytest.raises(FrozenInstanceError):
        item.session_id = "OTHER"
    with pytest.raises(TypeError):
        item.rows[0]["close"] = 9000


def test_archive_copies_mutable_supplied_rows():
    original = list(rows())
    item = archive(data=tuple(original))
    original[0]["close"] = 5000
    assert item.rows[0]["close"] == 100
    assert item.rows_sha256 == x4_replay_rows_sha256_v1(item.rows)


@pytest.mark.parametrize("mod", ("duplicate", "reverse", "gap"))
def test_no_duplicate_out_of_order_or_gapped_bars(mod):
    data = list(rows())
    if mod == "duplicate":
        data[1] = {**data[1], "timestamp": data[0]["timestamp"]}
    elif mod == "reverse":
        data.reverse()
    else:
        data[1] = {**data[1], "timestamp": data[1]["timestamp"] + 60}
    with pytest.raises(ValueError, match="gapped|order|Overlapping"):
        run(archives={"5m": archive(tf="5m", data=tuple(data)), "15m": archive(tf="15m")})


def test_mixed_sessions_rejected():
    with pytest.raises(ValueError, match="Mixed futures sessions"):
        run(archives={"5m": archive(tf="5m"), "15m": archive(tf="15m", session_id="2026-10-01:S2")})


def test_wrong_declared_session_date_rejected():
    with pytest.raises(ValueError, match="IST session date"):
        run(archives={"5m": archive(tf="5m", session_id="2026-09-30:S1")})


def test_duplicate_capture_id_rejected():
    common = "REPEATED_CAPTURE_ID"
    with pytest.raises(ValueError, match="Capture identifier reused"):
        run(
            archives={
                "5m": archive(tf="5m", capture_id=common),
                "15m": archive(tf="15m", capture_id=common),
            }
        )


def test_archive_cannot_contain_bar_completed_after_archive_time():
    with pytest.raises(ValueError, match="not completed at archive time"):
        run(archives={"5m": archive(tf="5m", archived_at=NOW - timedelta(minutes=5))})


def test_earliest_as_of_cannot_precede_instrument_resolution():
    with pytest.raises(ValueError, match="resolution unavailable"):
        run(
            resolved=replace_identity(identity(), resolved_at=NOW - timedelta(minutes=1)),
            checkpoints=(NOW - timedelta(minutes=10), NOW),
        )


def replace_identity(value, **changes):
    return SimpleNamespace(**{**vars(value), **changes})


@pytest.mark.parametrize(
    "change",
    (
        {"provider": "ANGEL_SMARTAPI"},
        {"instrument_type": "OPTION"},
        {"data_only": False},
        {"live_execution_eligible": True},
    ),
)
def test_resolved_identity_must_be_fyers_read_only_future(change):
    with pytest.raises(ValueError, match="FYERS data-only"):
        run(resolved=replace_identity(identity(), **change))


@pytest.mark.parametrize(
    "checkpoints",
    (
        (NOW, NOW),
        (NOW, NOW - timedelta(minutes=5)),
        (datetime(2026, 10, 1, 6),),
        (),
    ),
)
def test_invalid_checkpoint_order_or_timezone_rejected(checkpoints):
    with pytest.raises(ValueError, match="checkpoints"):
        run(checkpoints=checkpoints)


def test_verified_index_basis_has_sidecar_hash_and_proof_reference():
    reference = X4BasisReferenceV1(
        market="NIFTY",
        benchmark_type="INDEX_SPOT",
        price=101.0,
        price_unit="INDEX_POINTS",
        source_id="TEST_INDEX_SPOT",
        observed_at=NOW,
        verified=True,
    )
    out = run(basis_reference=reference, basis_proof_id="REVIEW:INDEX_SPOT")[0]
    assert out.status == "AVAILABLE"
    assert len(out.basis_reference_sha256) == 64
    assert out.basis_proof_id == "REVIEW:INDEX_SPOT"


def test_future_benchmark_not_borrowed_by_earlier_checkpoint():
    reference = X4BasisReferenceV1(
        market="NIFTY",
        benchmark_type="INDEX_SPOT",
        price=101.0,
        price_unit="INDEX_POINTS",
        source_id="TEST_INDEX_SPOT",
        observed_at=NOW,
        verified=True,
    )
    early, later = run(
        checkpoints=(NOW - timedelta(minutes=10), NOW),
        basis_reference=reference,
        basis_proof_id="REVIEW:INDEX_SPOT",
    )
    assert early.basis_reference_sha256 is None
    assert early.basis_proof_id is None
    assert "FUTURE_BENCHMARK_EXCLUDED" in early.blockers
    assert later.basis_reference_sha256 is not None


def test_missing_basis_proof_fails_closed():
    reference = X4BasisReferenceV1(
        market="NIFTY",
        benchmark_type="INDEX_SPOT",
        price=101.0,
        price_unit="INDEX_POINTS",
        source_id="TEST_INDEX_SPOT",
        observed_at=NOW,
        verified=True,
    )
    with pytest.raises(ValueError, match="proof ID"):
        run(basis_reference=reference)


def test_basis_proof_without_reference_is_rejected():
    with pytest.raises(ValueError, match="proof ID"):
        run(basis_proof_id="EXTRANEOUS")


def test_replay_output_is_nonvoting_noncertifying_and_immutable():
    out = run()[0]
    assert out.data_only is True
    assert out.independent_vote is False
    assert not hasattr(out, "trade_action")
    assert not hasattr(out, "trade_score")
    assert not hasattr(out, "paper_certification_count")
    with pytest.raises(FrozenInstanceError):
        out.certification_eligible = True


def test_upstream_archive_hash_changes_checkpoint_provenance():
    old = run()[0]
    data = list(rows(tf="5m"))
    data[0] = {**data[0], "volume": 11}
    new = run(archives={"5m": archive(tf="5m", data=tuple(data)), "15m": archive(tf="15m")})[0]
    assert old.capture_sha256_by_timeframe != new.capture_sha256_by_timeframe
    assert old.sha256() != new.sha256()
