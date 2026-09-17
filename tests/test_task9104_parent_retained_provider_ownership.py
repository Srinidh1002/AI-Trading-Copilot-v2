from __future__ import annotations

import inspect

from services.certification.task9_parent_evidence_composition import (
    build_task9_parent_evidence_dependencies,
)
from services.certification.task9_production_startup_acquisition import (
    capture_task9_production_startup_angel_facts,
)


def test_task9_parent_uses_same_option_builder_ownership_seam_as_startup():
    parent_source = inspect.getsource(
        build_task9_parent_evidence_dependencies
    )

    startup_source = inspect.getsource(
        capture_task9_production_startup_angel_facts
    )

    for token in (
        '"option_chain_builder"',
        '"market_client"',
        '"instrument_master"',
    ):
        assert token in parent_source
        assert token in startup_source


def test_task9_parent_does_not_construct_second_instrument_master():
    source = inspect.getsource(
        build_task9_parent_evidence_dependencies
    )

    assert (
        "AngelInstrumentMaster().fetch_instruments"
        not in source
    )

    assert (
        "AngelInstrumentMaster()"
        not in source
    )


def test_task9_parent_vix_reuses_retained_option_builder_owners():
    source = inspect.getsource(
        build_task9_parent_evidence_dependencies
    )

    assert (
        "master_fetcher=retained_master_fetcher"
        in source
    )

    assert (
        "market_client=retained_market_client"
        in source
    )


def test_task9_startup_acquisition_owns_canonical_full_quote_fetch():
    source = inspect.getsource(
        capture_task9_production_startup_angel_facts
    )

    assert (
        "fetch_canonical_two_market_full_quotes("
        in source
    )

    assert (
        "fetch_canonical_two_market_full_quotes(\n"
        "            client,"
        in source
    )

def test_task9_parent_does_not_reacquire_shared_client_inside_owner():
    source = inspect.getsource(
        build_task9_parent_evidence_dependencies
    )

    assert (
        "get_certification_market_client()"
        not in source
    )
