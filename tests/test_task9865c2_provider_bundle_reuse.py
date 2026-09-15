import pytest

import services.certification.task8_live_paper_default_composition as composition
from services.paper_orchestration.certified_runtime_composition import (
    build_default_runtime_providers,
)


def test_task8_dependencies_reuses_precomposed_provider_bundle(
    monkeypatch,
):
    providers = build_default_runtime_providers()

    original_option_pipeline = (
        providers.option_decision_pipeline
    )

    original_builder = (
        original_option_pipeline.option_chain_builder
    )

    original_client = (
        original_builder.market_client
    )

    original_master = (
        original_builder.instrument_master
    )

    monkeypatch.setattr(
        composition,
        "build_default_runtime_providers",
        lambda **_: pytest.fail(
            "provider bundle must not be rebuilt"
        ),
    )

    dependencies = composition.build_task8_dependencies(
        providers=providers,
    )

    assert dependencies.execution_mode == "PAPER"
    assert dependencies.broker_order_submission is False
    assert dependencies.live_execution_eligible is False

    assert (
        providers.option_decision_pipeline
        is original_option_pipeline
    )

    assert (
        providers.option_decision_pipeline.option_chain_builder
        is original_builder
    )

    assert (
        providers.option_decision_pipeline.option_chain_builder.market_client
        is original_client
    )

    assert (
        providers.option_decision_pipeline.option_chain_builder.instrument_master
        is original_master
    )


def test_injected_provider_bundle_must_expose_required_runtime_surface():
    with pytest.raises(
        TypeError,
        match="providers must expose",
    ):
        composition.build_task8_dependencies(
            providers=object(),
        )
