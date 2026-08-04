from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_implementation_plan_marks_all_work_packages_complete():
    source = read("P9_IMPLEMENTATION_PLAN.md")

    for work_package in ("WP1", "WP2", "WP3", "WP4"):
        assert (
            f"{work_package} " in source
            and "— COMPLETE" in source[
                source.index(f"{work_package} "):
            ]
        )


def test_implementation_plan_contains_final_authority_chain():
    source = read("P9_IMPLEMENTATION_PLAN.md")

    ordered = (
        "DATA",
        "SESSION",
        "ANALYSIS",
        "OPPORTUNITY",
        "P6 PLAN",
        "P8 ADMISSION",
        "P7 PAPER LIFECYCLE",
        "P8 PORTFOLIO UPDATE",
        "IMMUTABLE P9 CYCLE RESULT",
        "PERSISTENCE JOURNAL",
    )
    offsets = tuple(source.index(token) for token in ordered)

    assert offsets == tuple(sorted(offsets))


def test_audit_documents_runtime_and_idempotency_boundaries():
    source = read("P9A_ORCHESTRATION_AUDIT.md")

    assert "journal classification" in source
    assert "deterministic cycle execution" in source
    assert "atomic journal commit" in source
    assert "startup recovery" in source
    assert "opportunity coordinator" in source
    assert "monitoring coordinator" in source


def test_final_certification_matrix_exists_and_records_baseline():
    source = read("P9_FINAL_CERTIFICATION_MATRIX.md")

    assert "14,266 tests" in source
    assert "0 failures" in source
    assert "2 pre-existing warnings" in source
    assert "WP4-6" in source
