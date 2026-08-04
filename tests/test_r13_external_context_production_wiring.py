from pathlib import Path


COMPOSITIONS = (
    Path(
        "services/certification/"
        "task1c_parent_only_default_composition.py"
    ),
    Path(
        "services/certification/"
        "task8_live_paper_default_composition.py"
    ),
    Path(
        "services/paper_orchestration/"
        "certified_runtime_composition.py"
    ),
)


def test_production_compositions_use_external_context_source_authority():
    for path in COMPOSITIONS:
        source = path.read_text(encoding="utf-8")

        assert (
            "ExternalContextSourceAuthority" in source
        ), path

        assert (
            "external_context_reader="
            "external_context_authority"
        ) in source, path


def test_production_external_context_does_not_use_legacy_engines():
    for path in COMPOSITIONS:
        source = path.read_text(encoding="utf-8")

        assert "fii_dii_engine" not in source
        assert "economic_calendar_engine" not in source
        assert "analyze_fii_dii" not in source
        assert "analyze_economic_calendar" not in source


def test_uncertified_external_sources_use_explicit_unavailable_readers():
    for path in COMPOSITIONS:
        source = path.read_text(encoding="utf-8")

        assert (
            "global_reader="
            "UnavailableGlobalMarketReader()"
        ) in source, path

        assert (
            "institutional_reader="
            "UnavailableInstitutionalFlowReader()"
        ) in source, path

        assert (
            "event_reader="
            "UnavailableScheduledEventReader()"
        ) in source, path

        assert "global_reader=lambda" not in source
        assert "institutional_reader=lambda" not in source
        assert "event_reader=lambda" not in source
