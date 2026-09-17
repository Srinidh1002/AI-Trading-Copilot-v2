from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "P10_WP2_PROJECTION_DESIGN.md"


def test_design_requires_exact_source_contracts():
    source = DESIGN.read_text(encoding="utf-8")

    assert "Every adapter accepts one exact source contract" in source
    assert "legacy dashboard trade dictionaries" in source
    assert "partially reconstructed objects" in source


def test_design_forbids_hidden_identity_and_time():
    source = DESIGN.read_text(encoding="utf-8")

    assert "current time" in source
    assert "generated UUIDs" in source


def test_design_preserves_fill_order():
    source = DESIGN.read_text(encoding="utf-8")

    assert "fills preserve certified source order" in source
    assert "targets are always T1, T2, T3" in source


def test_streamlit_boundary_is_read_only():
    source = DESIGN.read_text(encoding="utf-8")

    for forbidden in (
        "P6 evaluators",
        "P7 evaluators",
        "P8 admission or portfolio mutation",
        "P9 orchestration executors",
        "broker clients",
        "provider clients",
        "SQLite",
        "legacy paper-trade managers",
    ):
        assert forbidden in source
