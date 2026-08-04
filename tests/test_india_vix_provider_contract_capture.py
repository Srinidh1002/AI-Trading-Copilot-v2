import json
from datetime import datetime, timedelta, timezone

import pytest

from services.diagnostics.india_vix_provider_contract_capture import (
    IndiaVixProviderContractEvidenceV1,
    _parse_provider_timestamp,
    collect_master_evidence,
    capture_provider_contract,
)

NOW = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)


def record(**changes):
    value = {"token": "99926017", "symbol": "India VIX", "name": "INDIA VIX", "exch_seg": "NSE", "instrumenttype": "AMXIDX", "expiry": "", "strike": "0", "tick_size": "0", "lotsize": "1"}
    value.update(changes)
    return value


class Client:
    def __init__(self, response): self.response = response; self.calls = 0; self.historical_calls = 0
    def get_market_data(self, mode, exchange_tokens):
        self.calls += 1; assert mode == "FULL"; assert exchange_tokens == {"NSE": ["99926017"]}; return self.response
    def get_historical_data(self, **kwargs):
        self.historical_calls += 1
        assert kwargs["exchange"] == "NSE" and kwargs["interval"] == "ONE_DAY"
        return {"status": True, "data": [["safe-daily-row"]], "authorization": "must-not-serialize"}


def quote(**changes):
    row = {"ltp": 15.2, "previousClose": 14.8, "tradingSymbol": "India VIX", "symbolToken": "99926017", "exchange": "NSE", "exchFeedTime": "2026-08-02T09:59:30+00:00", "authorization": "must-not-serialize"}
    row.update(changes)
    return {"status": True, "data": {"fetched": [row], "authorization": "must-not-serialize"}, "jwtToken": "must-not-serialize"}


def capture(response=None, *, previous_close_semantics_proven=True):
    values = iter((NOW, NOW, NOW + timedelta(seconds=1)))
    return capture_provider_contract(master_fetcher=lambda: [record()], market_client=Client(response or quote()), clock=lambda: next(values), previous_close_semantics_proven=previous_close_semantics_proven)


def capture_at(response, now, *, inspect_historical=False):
    client = Client(response)
    evidence = capture_provider_contract(master_fetcher=lambda: [record()], market_client=client, clock=lambda: now, previous_close_semantics_proven=True, inspect_historical=inspect_historical)
    return evidence, client


def test_exactly_one_valid_master_confirms_identity():
    evidence = collect_master_evidence([record()], fetched_at=NOW)
    assert evidence.status == "CONFIRMED" and evidence.exact_match_decision == "EXACTLY_ONE"


@pytest.mark.parametrize("changes", ({}, {"exch_seg": "BSE"}, {"instrumenttype": "INDEX"}))
def test_missing_or_wrong_master_identity_is_rejected(changes):
    records = [] if not changes else [record(**changes)]
    assert collect_master_evidence(records, fetched_at=NOW).status == "REJECTED"


def test_duplicate_master_is_ambiguous_and_cached_mismatch_blocks():
    assert collect_master_evidence([record(), record(token="99926018")], fetched_at=NOW).status == "AMBIGUOUS"
    evidence = collect_master_evidence([record()], fetched_at=NOW, cached_records=[record(token="old")])
    assert "INDIA_VIX_CACHED_MASTER_TOKEN_MISMATCH" in evidence.blockers


def test_no_invented_aliases_and_fetch_timestamp_is_required():
    assert collect_master_evidence([record(symbol="INDIAVIX")], fetched_at=NOW).status == "REJECTED"
    with pytest.raises(ValueError): collect_master_evidence([record()], fetched_at=datetime(2026, 1, 1))


def test_complete_safe_quote_schema_is_redacted_and_deterministic():
    evidence = capture()
    payload = evidence.to_json()
    assert evidence.quote.identity_matches_master and evidence.quote.safe_values["ltp"] == 15.2
    assert "authorization" not in payload and "jwtToken" not in payload and evidence.to_json() == evidence.to_json()


@pytest.mark.parametrize("changes, blocker", [
    ({"symbolToken": "wrong"}, "INDIA_VIX_QUOTE_IDENTITY_MISMATCH"),
    ({"tradingSymbol": "wrong"}, "INDIA_VIX_QUOTE_IDENTITY_MISMATCH"),
    ({"exchange": "BSE"}, "INDIA_VIX_QUOTE_IDENTITY_MISMATCH"),
    ({}, "INDIA_VIX_LTP_INVALID"),
])
def test_quote_identity_and_ltp_validation(changes, blocker):
    if blocker == "INDIA_VIX_LTP_INVALID": changes = {"ltp": None}
    assert blocker in capture(quote(**changes)).blockers


@pytest.mark.parametrize("ltp", (0, -1, float("nan"), float("inf")))
def test_invalid_ltp_is_rejected(ltp):
    assert "INDIA_VIX_LTP_INVALID" in capture(quote(ltp=ltp)).blockers


def test_timestamp_and_previous_close_rules_are_fail_closed():
    missing = capture(quote(exchFeedTime=None))
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN" in missing.blockers
    naive = capture(quote(exchFeedTime="2026-08-02T09:59:30"))
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN" in naive.blockers
    future = capture(quote(exchFeedTime="2026-08-02T10:01:30+00:00"))
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH" in future.blockers
    stale = capture(quote(exchFeedTime="2026-08-02T09:00:00+00:00"))
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH" in stale.blockers
    no_previous = capture(quote(previousClose=None), previous_close_semantics_proven=True)
    assert "INDIA_VIX_PREVIOUS_CLOSE_SEMANTICS_UNPROVEN" in no_previous.blockers


def test_exact_angel_timestamp_uses_explicit_india_timezone_and_is_fresh():
    parsed = _parse_provider_timestamp("31-Jul-2026 16:08:13")
    assert parsed.tzinfo.key == "Asia/Kolkata" and parsed.utcoffset() == timedelta(hours=5, minutes=30)
    evidence, _ = capture_at(quote(exchFeedTime="31-Jul-2026 16:08:13"), datetime(2026, 7, 31, 10, 40, tzinfo=timezone.utc))
    assert evidence.quote.provider_timestamp_is_provider_issued
    assert evidence.quote.timestamp_age_seconds == 107
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN" not in evidence.blockers
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH" not in evidence.blockers


def test_observed_angel_timestamp_is_stale_not_unproven_and_iso_still_works():
    evidence, _ = capture_at(quote(exchFeedTime="31-Jul-2026 16:08:13"), NOW)
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH" in evidence.blockers
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN" not in evidence.blockers
    assert _parse_provider_timestamp("2026-08-02T09:59:30+00:00").tzinfo == timezone.utc


def test_missing_timestamp_is_not_substituted_and_historical_schema_is_bounded():
    evidence, client = capture_at(quote(exchFeedTime=None), NOW)
    assert evidence.quote.parsed_provider_timestamp is None
    assert evidence.quote.received_at is not None
    assert "INDIA_VIX_PROVIDER_TIMESTAMP_UNPROVEN" in evidence.blockers
    no_previous = quote(); del no_previous["data"]["fetched"][0]["previousClose"]
    historical, historical_client = capture_at(no_previous, NOW, inspect_historical=True)
    assert historical_client.historical_calls == 1
    assert historical.quote.historical_evidence["status"] == "SCHEMA_ONLY"
    assert "authorization" not in historical.to_json()


def test_secrets_are_rejected_and_repr_is_safe():
    master = collect_master_evidence([record()], fetched_at=NOW)
    with pytest.raises(ValueError):
        IndiaVixProviderContractEvidenceV1(NOW, master, None, "REJECTED", (), (), "x")
    assert "must-not-serialize" not in repr(capture())
