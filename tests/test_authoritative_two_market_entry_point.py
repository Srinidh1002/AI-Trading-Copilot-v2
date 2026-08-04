import ast
from pathlib import Path

import pytest

from services.paper_orchestration.authoritative_two_market_entry_point import (
    AUTHORITATIVE_TWO_MARKET_ENTRY_POINT_ID,
    run_authoritative_two_market_parent_cycle,
)
from test_certified_two_market_parent_runtime import (
    candidate_for,
    cycles,
    parent,
    readers,
)


def test_authoritative_entry_point_delegates_exact_two_market_cycle():
    nifty, sensex = cycles()

    result = run_authoritative_two_market_parent_cycle(
        parent(nifty, sensex),
        nifty_cycle=nifty,
        sensex_cycle=sensex,
        readers=readers(
            lambda cycle, data, analysis, captured, shared_context, *,
            parent_cycle_id: candidate_for(
                cycle,
                data,
                score=80.0 if cycle.underlying_symbol == "NIFTY" else 60.0,
            )
        ),
    )

    assert AUTHORITATIVE_TWO_MARKET_ENTRY_POINT_ID == (
        "CERTIFIED_TWO_MARKET_PARENT_RUNTIME_V1"
    )
    assert len(result.entries) == 2
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False


def test_authoritative_entry_point_rejects_wrong_exact_inputs():
    nifty, sensex = cycles()
    runtime_readers = readers(
        lambda cycle, data, analysis, captured, shared_context, *,
        parent_cycle_id: candidate_for(
            cycle,
            data,
            score=70.0,
        )
    )

    with pytest.raises(TypeError, match="parent"):
        run_authoritative_two_market_parent_cycle(
            {},
            nifty_cycle=nifty,
            sensex_cycle=sensex,
            readers=runtime_readers,
        )

    with pytest.raises(TypeError, match="readers"):
        run_authoritative_two_market_parent_cycle(
            parent(nifty, sensex),
            nifty_cycle=nifty,
            sensex_cycle=sensex,
            readers=object(),
        )


def _imports(path: str) -> set[str]:
    source = Path(path).read_text(encoding="utf-8-sig")
    result = set()

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)

    return result


@pytest.mark.parametrize(
    "path",
    (
        "services/certification/"
        "task1c_parent_only_default_composition.py",
        "services/certification/"
        "task8_live_paper_default_composition.py",
    ),
)
def test_live_compositions_use_only_authoritative_entry_point(path):
    imports = _imports(path)

    assert (
        "services.paper_orchestration."
        "authoritative_two_market_entry_point"
    ) in imports

    assert (
        "services.paper_orchestration."
        "certified_two_market_parent_runtime"
    ) not in imports

    assert (
        "services.paper_orchestration."
        "two_market_parent_cycle_coordinator"
    ) not in imports


def test_lower_level_coordinator_is_not_a_live_composition_entry_point():
    allowed = {
        Path(
            "services/paper_orchestration/"
            "certified_two_market_parent_runtime.py"
        ),
        Path(
            "services/paper_orchestration/"
            "two_market_parent_cycle_coordinator.py"
        ),
    }

    violations = []

    for path in Path("services").rglob("*.py"):
        if path in allowed:
            continue

        source = path.read_text(encoding="utf-8-sig")

        if (
            "paper_orchestration."
            "two_market_parent_cycle_coordinator import"
        ) in source:
            violations.append(str(path))

    assert violations == []

