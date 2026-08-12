from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.broker.market_data_control import (
    BrokerMarketDataRequestError,
)
from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerError,
    Task9ExternalProviderBlockerStore,
)
from services.certification.task9_external_provider_recovery_probe import (
    run_recovery_probe,
)


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(
    2026,
    8,
    10,
    13,
    5,
    tzinfo=IST,
)


class Gate:
    def __init__(self):
        self.calls = 0

    def acquire(self):
        self.calls += 1


class Cooldown:
    def __init__(self, active=None):
        self.value = active

    def active(self):
        return self.value


class Client:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_historical_data(self, **kwargs):
        self.calls.append(kwargs)

        if isinstance(
            self.response,
            BaseException,
        ):
            raise self.response

        return self.response


def row():
    return {
        "status": True,
        "data": [
            [
                "2026-08-10T12:55:00+05:30",
                100,
                101,
                99,
                100,
                10,
            ]
        ],
    }


def active(root):
    return Task9ExternalProviderBlockerStore(root).record(
        "run",
        observed_at=(
            NOW - timedelta(minutes=2)
        ),
    )


def test_not_before_blocks_without_gate_or_provider(
    tmp_path,
):
    active(tmp_path)

    client = Client(row())
    gate = Gate()

    with pytest.raises(
        Task9ExternalProviderBlockerError,
        match="NOT_YET_ALLOWED",
    ):
        run_recovery_probe(
            persistence_root=tmp_path,
            official_run_id="run",
            now=(
                NOW
                - timedelta(
                    minutes=1,
                    seconds=1,
                )
            ),
            client=client,
            gate=gate,
            cooldown=Cooldown(),
        )

    assert client.calls == []
    assert gate.calls == 0


def test_success_one_request_clears_and_releases_lease(
    tmp_path,
):
    first = active(tmp_path)

    client = Client(row())
    gate = Gate()

    result = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=NOW,
        client=client,
        gate=gate,
        cooldown=Cooldown(),
    )

    assert result["status"] == "CLEARED"
    assert (
        result["first_seen_at"]
        == first["first_seen_at"]
    )
    assert result["last_probe_result"] == "SUCCESS"

    assert len(client.calls) == 1
    assert gate.calls == 1

    request = client.calls[0]

    assert request["exchange"] == "NSE"
    assert request["symboltoken"] == "99926000"
    assert request["interval"] == "FIVE_MINUTE"

    assert (
        request["fromdate"]
        == "2026-08-10 13:00"
    )
    assert (
        request["todate"]
        == "2026-08-10 13:05"
    )

    assert not (
        tmp_path
        / "task9-external-provider-probe.lock"
    ).exists()


def test_after_hours_nse_recovery_probe_requests_cash_session_final_candle(
    tmp_path,
):
    first = active(tmp_path)
    now = datetime(2026, 8, 10, 16, 0, tzinfo=IST)
    client = Client(row())

    result = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=now,
        client=client,
        gate=Gate(),
        cooldown=Cooldown(),
    )

    assert result["status"] == "CLEARED"
    assert result["first_seen_at"] == first["first_seen_at"]
    assert len(client.calls) == 1
    assert client.calls[0]["fromdate"] == "2026-08-10 15:25"
    assert client.calls[0]["todate"] == "2026-08-10 15:30"


def test_rate_and_generic_failures_remain_active_with_one_request(
    tmp_path,
):
    first = active(tmp_path)

    limited = Client(
        BrokerMarketDataRequestError(
            "historical-data",
            1,
            "rate_limited",
            "x",
        )
    )

    rate_gate = Gate()

    rate = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=NOW,
        client=limited,
        gate=rate_gate,
        cooldown=Cooldown(),
    )

    assert rate["status"] == "ACTIVE"
    assert (
        rate["last_probe_result"]
        == "RATE_LIMITED"
    )
    assert (
        rate["last_failure_reason"]
        == "HISTORICAL-DATA_RATE_LIMITED"
    )

    assert len(limited.calls) == 1
    assert rate_gate.calls == 1

    assert (
        rate["occurrence_count"]
        == first["occurrence_count"] + 1
    )
    assert rate["consecutive_rate_limit_count"] == 2

    assert not (
        tmp_path
        / "task9-external-provider-probe.lock"
    ).exists()

    before = rate["occurrence_count"]
    escalation_before = rate["consecutive_rate_limit_count"]

    generic = Client(
        RuntimeError("x")
    )

    generic_gate = Gate()

    failed = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=datetime.fromisoformat(
            rate["next_probe_not_before"]
        ),
        client=generic,
        gate=generic_gate,
        cooldown=Cooldown(),
    )

    assert failed["status"] == "ACTIVE"
    assert (
        failed["last_probe_result"]
        == "FAILED"
    )
    assert (
        failed["last_failure_reason"]
        == "HISTORICAL-DATA_UNAVAILABLE"
    )

    assert (
        failed["occurrence_count"]
        == before
    )
    assert failed["consecutive_rate_limit_count"] == escalation_before

    assert len(generic.calls) == 1
    assert generic_gate.calls == 1

    assert not (
        tmp_path
        / "task9-external-provider-probe.lock"
    ).exists()


class AmbiguousForbiddenError(RuntimeError):
    status_code = 403


@pytest.mark.parametrize(
    ("failure", "expected_reason"),
    (
        (
            RuntimeError("Token expired raw-provider-detail"),
            "HISTORICAL-DATA_AUTH_EXPIRED",
        ),
        (
            TimeoutError("Gateway timeout raw-provider-detail"),
            "HISTORICAL-DATA_PROVIDER_TRANSIENT",
        ),
        (
            AmbiguousForbiddenError("Forbidden raw-provider-detail"),
            "HISTORICAL-DATA_UNKNOWN_PROVIDER_ERROR",
        ),
        (
            RuntimeError("raw-provider-detail"),
            "HISTORICAL-DATA_UNAVAILABLE",
        ),
    ),
)
def test_provider_failures_are_classified_without_persisting_detail(
    tmp_path,
    failure,
    expected_reason,
):
    first = active(tmp_path)
    client = Client(failure)
    gate = Gate()

    result = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=NOW,
        client=client,
        gate=gate,
        cooldown=Cooldown(),
    )

    assert result["status"] == "ACTIVE"
    assert result["last_probe_result"] == "FAILED"
    assert result["last_failure_reason"] == expected_reason
    assert result["occurrence_count"] == first["occurrence_count"]
    assert len(client.calls) == 1
    assert gate.calls == 1
    assert "raw-provider-detail" not in result["last_failure_reason"]
    assert not (tmp_path / "task9-external-provider-probe.lock").exists()


@pytest.mark.parametrize(
    ("response", "expected_reason"),
    (
        ({"status": True, "data": []}, "HISTORICAL-DATA_EMPTY_DATA"),
        ({"status": False, "message": "raw-provider-detail"}, "HISTORICAL-DATA_PROVIDER_UNSUCCESSFUL"),
        (None, "HISTORICAL-DATA_INVALID_RESPONSE"),
    ),
)
def test_probe_response_validation_failures_are_sanitized_and_non_counting(
    tmp_path,
    response,
    expected_reason,
):
    first = active(tmp_path)
    client = Client(response)
    gate = Gate()

    result = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=NOW,
        client=client,
        gate=gate,
        cooldown=Cooldown(),
    )

    assert result["status"] == "ACTIVE"
    assert result["last_probe_result"] == "FAILED"
    assert result["last_failure_reason"] == expected_reason
    assert result["occurrence_count"] == first["occurrence_count"]
    assert len(client.calls) == 1
    assert gate.calls == 1
    assert "raw-provider-detail" not in result["last_failure_reason"]
    assert not (tmp_path / "task9-external-provider-probe.lock").exists()


@pytest.mark.parametrize(
    ("failure_type", "expected_reason"),
    (
        ("empty_data", "HISTORICAL-DATA_EMPTY_DATA"),
        ("invalid_response", "HISTORICAL-DATA_INVALID_RESPONSE"),
        ("normalization_failed", "HISTORICAL-DATA_NORMALIZATION_FAILED"),
    ),
)
def test_typed_historical_payload_failures_remain_sanitized_and_non_counting(
    tmp_path,
    failure_type,
    expected_reason,
):
    first = active(tmp_path)
    client = Client(
        BrokerMarketDataRequestError(
            "historical-data",
            1,
            failure_type,
            "raw-provider-detail",
        )
    )

    result = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=NOW,
        client=client,
        gate=Gate(),
        cooldown=Cooldown(),
    )

    assert result["status"] == "ACTIVE"
    assert result["last_probe_result"] == "FAILED"
    assert result["last_failure_reason"] == expected_reason
    assert result["occurrence_count"] == first["occurrence_count"]
    assert "raw-provider-detail" not in result["last_failure_reason"]
    assert not (tmp_path / "task9-external-provider-probe.lock").exists()


@pytest.mark.parametrize(
    ("provider_failure_kind", "expected_reason"),
    (
        ("AUTH_EXPIRED", "HISTORICAL-DATA_AUTH_EXPIRED"),
        ("PROVIDER_TRANSIENT", "HISTORICAL-DATA_PROVIDER_TRANSIENT"),
        ("UNKNOWN_PROVIDER_ERROR", "HISTORICAL-DATA_UNKNOWN_PROVIDER_ERROR"),
    ),
)
def test_typed_provider_failure_kind_reaches_recovery_blocker(
    tmp_path,
    provider_failure_kind,
    expected_reason,
):
    first = active(tmp_path)
    client = Client(
        BrokerMarketDataRequestError(
            "historical-data",
            1,
            "provider_failure",
            "raw-provider-detail",
            provider_failure_kind=provider_failure_kind,
        )
    )

    result = run_recovery_probe(
        persistence_root=tmp_path,
        official_run_id="run",
        now=NOW,
        client=client,
        gate=Gate(),
        cooldown=Cooldown(),
    )

    assert result["status"] == "ACTIVE"
    assert result["last_probe_result"] == "FAILED"
    assert result["last_failure_reason"] == expected_reason
    assert result["occurrence_count"] == first["occurrence_count"]
    assert len(client.calls) == 1
    assert "raw-provider-detail" not in result["last_failure_reason"]
    assert not (tmp_path / "task9-external-provider-probe.lock").exists()
