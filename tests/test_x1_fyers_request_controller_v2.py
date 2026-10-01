from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.contracts.provider_runtime_bundle_v2 import (
    ProviderRequestControllerV2,
)
from services.x1.fyers_request_controller_v2 import (
    FailureClassV1,
    FyersRequestControllerV2Impl,
    RequestControllerError,
    RetryDecisionV1,
)
from src.rate_limiter import (
    FyersRateLimitCoordinator,
    FyersRateLimitError,
)


def make_controller(tmp_path: Path, **kwargs):
    coordinator = FyersRateLimitCoordinator(
        state_path=str(tmp_path / "state.json"),
        worker_name="x1-test",
    )
    controller = FyersRequestControllerV2Impl(
        coordinator=coordinator, **kwargs
    )
    return coordinator, controller


def test_controller_satisfies_provider_request_controller_protocol(tmp_path):
    _, controller = make_controller(tmp_path)
    assert isinstance(controller, ProviderRequestControllerV2)
    assert controller.data_only is True
    assert controller.order_capability_allowed is False
    assert controller.automatic_fallback_allowed is False


def test_wait_for_slot_consumes_a_permit(tmp_path):
    coordinator, controller = make_controller(tmp_path)
    assert controller.wait_for_slot("QUOTE", 0) == 0.0
    stats = coordinator.stats()
    assert stats["sec"] == 1
    assert stats["min"] == 1
    assert stats["day"] == 1


def test_acquire_permit_context_consumes_exactly_one_permit(tmp_path):
    coordinator, controller = make_controller(tmp_path)
    with controller.acquire_permit("QUOTE"):
        pass
    stats = coordinator.stats()
    assert stats["day"] == 1


def test_permit_is_not_consumed_if_deadline_exceeded(
    tmp_path, monkeypatch
):
    import time as _real_time

    import src.rate_limiter as rl_module

    # Preload the day cap so every iteration enters the day-cap
    # branch and the coordinator never has a permit to grant.
    now = _real_time.time()
    (tmp_path / 'state.json').write_text(
        json.dumps({'calls': [now] * 90_000}),
        encoding='utf-8',
    )

    # Replace only the module-level `time` reference inside
    # src.rate_limiter with a fake whose monotonic clock advances
    # on every call, so the deadline is exceeded at the first
    # post-lock check. `time.time()` and `time.sleep()` are
    # preserved to keep the bucket arithmetic real and the test
    # fast.
    class FakeTime:
        def __init__(self):
            self._t = 0.0

        def time(self):
            return _real_time.time()

        def monotonic(self):
            self._t += 1.0
            return self._t

        def sleep(self, seconds):
            del seconds

    monkeypatch.setattr(rl_module, 'time', FakeTime())

    coordinator = FyersRateLimitCoordinator(
        state_path=str(tmp_path / 'state.json'),
        worker_name='x1-test',
    )
    controller = FyersRequestControllerV2Impl(
        coordinator=coordinator,
        max_wait_seconds=0.5,
    )

    with pytest.raises(FyersRateLimitError) as excinfo:
        with controller.acquire_permit('QUOTE'):
            pass
    assert 'RATE_LIMIT_WAIT_DEADLINE_EXCEEDED' in str(
        excinfo.value
    )

    # The on-disk state must not have grown: no permit was consumed.
    on_disk = json.loads(
        (tmp_path / 'state.json').read_text(encoding='utf-8')
    )
    assert len(on_disk['calls']) == 90_000

def test_corrupt_state_file_fails_closed(tmp_path):
    coordinator, controller = make_controller(tmp_path)
    (tmp_path / "state.json").write_text(
        "not json at all", encoding="utf-8"
    )
    with pytest.raises(FyersRateLimitError) as excinfo:
        controller.wait_for_slot("QUOTE", 0)
    assert "RATE_LIMIT_STATE_INVALID" in str(excinfo.value)


def test_record_rate_limit_returns_bounded_backoff(tmp_path):
    _, controller = make_controller(tmp_path, base_backoff_seconds=0.5)
    b0 = controller.record_rate_limit("QUOTE", 0, 2.0)
    b1 = controller.record_rate_limit("QUOTE", 1, 2.0)
    b2 = controller.record_rate_limit("QUOTE", 2, 2.0)
    b30 = controller.record_rate_limit("QUOTE", 30, 2.0)
    assert b0 == 0.5
    assert b1 == 1.0
    assert b2 == 2.0
    assert b30 == 30.0  # capped


def test_record_success_is_noop(tmp_path):
    _, controller = make_controller(tmp_path)
    assert controller.record_success("QUOTE") is None


def test_classify_failure_by_http_status():
    assert (
        FyersRequestControllerV2Impl.classify_failure(http_status=429)
        is FailureClassV1.RETRYABLE
    )
    assert (
        FyersRequestControllerV2Impl.classify_failure(http_status=503)
        is FailureClassV1.RETRYABLE
    )
    assert (
        FyersRequestControllerV2Impl.classify_failure(http_status=400)
        is FailureClassV1.TERMINAL
    )
    assert (
        FyersRequestControllerV2Impl.classify_failure(http_status=401)
        is FailureClassV1.TERMINAL
    )
    assert (
        FyersRequestControllerV2Impl.classify_failure()
        is FailureClassV1.TERMINAL
    )


def test_classify_failure_by_reason_code():
    assert (
        FyersRequestControllerV2Impl.classify_failure(
            provider_reason_code="RATE_LIMIT"
        )
        is FailureClassV1.RETRYABLE
    )
    assert (
        FyersRequestControllerV2Impl.classify_failure(
            provider_reason_code="AUTH_FAILED"
        )
        is FailureClassV1.TERMINAL
    )


def test_classify_failure_by_exception():
    assert (
        FyersRequestControllerV2Impl.classify_failure(
            exception=TimeoutError("x")
        )
        is FailureClassV1.RETRYABLE
    )
    assert (
        FyersRequestControllerV2Impl.classify_failure(
            exception=ValueError("x")
        )
        is FailureClassV1.TERMINAL
    )


def test_should_retry_never_exceeds_attempts(tmp_path):
    _, controller = make_controller(
        tmp_path, max_attempts=2
    )
    d0 = controller.should_retry(
        attempt=0,
        failure_class=FailureClassV1.RETRYABLE,
    )
    assert d0.retry is True
    d1 = controller.should_retry(
        attempt=1,
        failure_class=FailureClassV1.RETRYABLE,
    )
    assert d1.retry is False
    assert d1.reason_code == "RETRY_EXHAUSTED"


def test_should_retry_refuses_terminal(tmp_path):
    _, controller = make_controller(tmp_path)
    decision = controller.should_retry(
        attempt=0,
        failure_class=FailureClassV1.TERMINAL,
    )
    assert decision.retry is False
    assert decision.reason_code == "TERMINAL_FAILURE"


def test_should_retry_returns_retry_decision_dataclass(tmp_path):
    _, controller = make_controller(tmp_path)
    decision = controller.should_retry(
        attempt=0,
        failure_class=FailureClassV1.RETRYABLE,
    )
    assert isinstance(decision, RetryDecisionV1)
    assert decision.backoff_seconds > 0


def test_constructor_rejects_bad_inputs(tmp_path):
    coordinator = FyersRateLimitCoordinator(
        state_path=str(tmp_path / "state.json")
    )
    with pytest.raises(TypeError):
        FyersRequestControllerV2Impl(coordinator=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        FyersRequestControllerV2Impl(
            coordinator=coordinator, max_wait_seconds=0
        )
    with pytest.raises(ValueError):
        FyersRequestControllerV2Impl(
            coordinator=coordinator, max_attempts=0
        )
    with pytest.raises(ValueError):
        FyersRequestControllerV2Impl(
            coordinator=coordinator, base_backoff_seconds=0
        )


def test_request_controller_error_wraps_unexpected(tmp_path):
    class Boom(FyersRateLimitCoordinator):
        def wait_if_needed(self, *a, **kw):  # type: ignore[override]
            raise ValueError("boom")

    class Fakes:
        pass

    # Can't subclass directly due to __init__ signature; use a duck
    # proxy that is an instance of the class via monkey-patch.
    coordinator = FyersRateLimitCoordinator(
        state_path=str(tmp_path / "state.json")
    )
    # Replace the bound method on the instance.
    def boom(*a, **kw):
        raise RuntimeError("forced")

    coordinator.wait_if_needed = boom  # type: ignore[method-assign]
    controller = FyersRequestControllerV2Impl(coordinator=coordinator)
    with pytest.raises(RequestControllerError):
        controller.wait_for_slot("QUOTE", 0)
    with pytest.raises(RequestControllerError):
        with controller.acquire_permit("QUOTE"):
            pass
