"""Task 9 certified option paths must not depend on legacy option engines."""
from pathlib import Path


CERTIFIED_FILES = (
    Path(
        "services/certification/"
        "task9_live_paper_production_composition.py"
    ),
    Path(
        "services/certification/"
        "task9_live_paper_certification_launcher.py"
    ),
    Path(
        "services/analysis/"
        "live_canonical_engine_adapters.py"
    ),
    Path(
        "services/live_option_chain_builder.py"
    ),
    Path(
        "services/live_option_decision_pipeline.py"
    ),
)


LEGACY_SYMBOLS = (
    "services.options.option_chain_engine",
    "OptionChainEngine",
    "services.options.greeks_engine",
    "GreeksEngine",
)


def test_task9_certified_option_path_excludes_legacy_engines():
    violations = []

    for path in CERTIFIED_FILES:
        text = path.read_text(
            encoding="utf-8"
        )

        for symbol in LEGACY_SYMBOLS:
            if symbol in text:
                violations.append(
                    f"{path}:{symbol}"
                )

    assert violations == []


def test_live_option_chain_builder_uses_capability_aware_source():
    text = Path(
        "services/live_option_chain_builder.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "angel_option_provider_capabilities"
        in text
    )

    assert (
        "OPTION_GREEKS_PROVIDER_CAPABILITY_UNAVAILABLE"
        in text
    )

    assert (
        "get_option_greeks"
        in text
    )


def test_live_option_pipeline_binds_live_builder():
    text = Path(
        "services/live_option_decision_pipeline.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "LiveOptionChainBuilder"
        in text
    )

    assert (
        "capture_option_inputs"
        in text
    )

    assert "OptionChainEngine" not in text
    assert "GreeksEngine" not in text
