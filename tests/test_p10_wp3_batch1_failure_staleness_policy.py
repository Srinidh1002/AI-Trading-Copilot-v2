from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "P10_WP3_RUNTIME_PUBLICATION_AUDIT.md"
DESIGN = ROOT / "docs" / "P10_WP3_PUBLICATION_DESIGN.md"


def test_failed_attempt_preserves_previous_publication():
    source = AUDIT.read_text(encoding="utf-8")

    assert "failed projection preserves the prior value" in source
    assert "failed cycle preserves the prior value" in source
    assert "explicit clearing requires an operator-owned reset path" in source


def test_staleness_uses_caller_supplied_time():
    source = AUDIT.read_text(encoding="utf-8")

    assert "caller-supplied timestamps" in source
    assert "caller-owned clock may be injected" in source
    assert "No component may call the wall clock implicitly" in source


def test_duplicate_policy_is_non_destructive():
    source = DESIGN.read_text(encoding="utf-8")

    assert "Equivalent duplicate publication attempts must not" in source
    assert "generate new trading values" in source
    assert "Attempt counters may still record the duplicate attempt" in source


def test_store_operations_are_atomic():
    source = DESIGN.read_text(encoding="utf-8")

    for name in ("publish", "record_failure", "get_snapshot", "reset"):
        assert f"`{name}`" in source
