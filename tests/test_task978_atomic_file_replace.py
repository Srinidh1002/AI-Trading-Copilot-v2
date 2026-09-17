import os

import pytest

from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)


def test_retries_transient_permission_error(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "value.json.tmp"
    destination = tmp_path / "value.json"

    source.write_text('{"value":1}', encoding="utf-8")

    real_replace = os.replace
    attempts = {"count": 0}

    def flaky_replace(source_path, destination_path):
        attempts["count"] += 1

        if attempts["count"] < 3:
            raise PermissionError(
                "simulated transient Windows denial"
            )

        return real_replace(
            source_path,
            destination_path,
        )

    monkeypatch.setattr(
        "services.certification."
        "task9_atomic_file_replace.os.replace",
        flaky_replace,
    )

    monkeypatch.setattr(
        "services.certification."
        "task9_atomic_file_replace.time.sleep",
        lambda _: None,
    )

    replace_task9_atomic_file(
        source,
        destination,
    )

    assert attempts["count"] == 3
    assert destination.read_text(
        encoding="utf-8"
    ) == '{"value":1}'
    assert not source.exists()


def test_fails_closed_after_retry_exhaustion(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "value.json.tmp"
    destination = tmp_path / "value.json"

    source.write_text('{"value":1}', encoding="utf-8")

    attempts = {"count": 0}

    def always_denied(source_path, destination_path):
        attempts["count"] += 1
        raise PermissionError(
            "persistent Windows denial"
        )

    monkeypatch.setattr(
        "services.certification."
        "task9_atomic_file_replace.os.replace",
        always_denied,
    )

    monkeypatch.setattr(
        "services.certification."
        "task9_atomic_file_replace.time.sleep",
        lambda _: None,
    )

    with pytest.raises(PermissionError):
        replace_task9_atomic_file(
            source,
            destination,
        )

    assert attempts["count"] == 5
    assert source.exists()
    assert not destination.exists()
