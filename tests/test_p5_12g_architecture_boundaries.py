"""P5-12G architecture, metadata, and passive PAPER-data certification."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from services.opportunity_ranking import evaluate_candidate_eligibility, rank_four_market_opportunities, score_market_opportunity_candidate
from tests.fixtures.p5_12 import CANONICAL_MARKET_IDENTITIES, CPI_WARNING, CPI_WARNING_EVENT_PROFILE, STRONG_BULLISH, build_market_opportunity_candidate


ROOT = Path(__file__).resolve().parents[1]
P5_SOURCES = tuple(sorted((ROOT / "tests" / "fixtures" / "p5_12").glob("*.py"))) + tuple(sorted((ROOT / "tests").glob("test_p5_12[abcdef]_*.py")))
FORBIDDEN_EDGE_PARTS = {"providers", "provider", "broker", "brokers", "execution", "dashboard", "streamlit", "openai", "anthropic", "langchain", "transformers", "requests", "httpx", "aiohttp", "socket", "pandas", "numpy", "scipy"}
CERTIFIED_EVALUATOR_SEAM = ("tests/test_p5_12c_four_market_quality_matrix.py", "aggregate", "evaluate_candidate_eligibility")
PROTECTIVE_TARGETS = {"socket.socket.connect", "pathlib.Path.write_text", "pathlib.Path.write_bytes", "builtins.open", "os.environ"}


@dataclass(frozen=True)
class MonkeypatchClassification:
    status: str
    category: str
    target: str
    reason: str


def _classify_monkeypatch(path: Path, call: ast.Call) -> MonkeypatchClassification:
    relative = str(path.relative_to(ROOT)).replace("\\", "/")
    target = ast.unparse(call.args[0]) if call.args else "<missing target>"
    attribute = call.args[1].value if len(call.args) > 1 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str) else "<missing attribute>"
    replacement = call.args[2] if len(call.args) > 2 else None
    if (relative, target, attribute) == CERTIFIED_EVALUATOR_SEAM and isinstance(replacement, ast.Call) and isinstance(replacement.func, ast.Attribute) and isinstance(replacement.func.value, ast.Name) and replacement.func.value.id == "case" and replacement.func.attr == "evaluator_patch" and len(replacement.args) == 1 and ast.unparse(replacement.args[0]) == "aggregate.evaluate_candidate_eligibility":
        return MonkeypatchClassification("ALLOWED", "certified missing-required evaluator seam", f"{target}.{attribute}", "exact P5-12C deterministic evaluator wrapper")
    full_target = f"{target}.{attribute}"
    if full_target in PROTECTIVE_TARGETS:
        return MonkeypatchClassification("ALLOWED", "isolation protection", full_target, "exact network/filesystem/environment protection target")
    return MonkeypatchClassification("REJECTED", "unexpected production-semantic mutation", full_target, "not an exact certified evaluator seam or protective target")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}


def test_ast_import_graph_has_only_fixture_contract_ranking_and_stdlib_directions():
    graph = {str(path.relative_to(ROOT)): _imports(path) for path in P5_SOURCES}
    violations = {source: sorted(target for target in targets if set(target.lower().split(".")) & FORBIDDEN_EDGE_PARTS) for source, targets in graph.items()}
    assert not {source: targets for source, targets in violations.items() if targets}, violations
    fixture_edges = set().union(*(_imports(path) for path in (ROOT / "tests" / "fixtures" / "p5_12").glob("*.py")))
    assert any(edge.startswith("services.contracts") for edge in fixture_edges)


def test_p5_12_source_monkeypatches_do_not_change_production_semantics():
    classifications = []
    for path in P5_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"setattr", "setitem"} and isinstance(node.func.value, ast.Name) and node.func.value.id == "monkeypatch":
                classifications.append((str(path.relative_to(ROOT)), node.lineno, _classify_monkeypatch(path, node)))
    rejected = [f"{path}:{line}: {item.target}: {item.reason}" for path, line, item in classifications if item.status == "REJECTED"]
    assert not rejected, "unexpected monkeypatches:\n" + "\n".join(rejected)
    assert [(item.category, item.target) for _, _, item in classifications] == [("certified missing-required evaluator seam", "aggregate.evaluate_candidate_eligibility")]


def test_monkeypatch_classifier_rejects_semantic_mutations_and_allows_exact_protection():
    source = "monkeypatch.setattr(scoring, 'DEFAULT_WEIGHT', 1.0)"
    rejected = _classify_monkeypatch(ROOT / "tests" / "test_p5_12g_architecture_boundaries.py", ast.parse(source).body[0].value)
    assert rejected.status == "REJECTED" and "DEFAULT_WEIGHT" in rejected.target
    source = "monkeypatch.setattr(ranking, 'rank_four_market_opportunities', replacement)"
    rejected = _classify_monkeypatch(ROOT / "tests" / "test_p5_12g_architecture_boundaries.py", ast.parse(source).body[0].value)
    assert rejected.status == "REJECTED" and "rank_four_market_opportunities" in rejected.target
    source = "monkeypatch.setattr(socket.socket, 'connect', blocked)"
    allowed = _classify_monkeypatch(ROOT / "tests" / "test_p5_12g_architecture_boundaries.py", ast.parse(source).body[0].value)
    assert allowed.status == "ALLOWED" and allowed.category == "isolation protection"


def test_fixture_metadata_contains_no_provider_payload_or_runtime_object():
    candidate = build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0], CPI_WARNING, event_profile=CPI_WARNING_EVENT_PROFILE)
    ranking = rank_four_market_opportunities(tuple(build_market_opportunity_candidate(identity, STRONG_BULLISH) for identity in CANONICAL_MARKET_IDENTITIES))
    forbidden = ("provider", "broker", "execution", "request", "response", "client", "token", "secret", "payload")
    for metadata in (candidate.metadata, candidate.market_regime.metadata, ranking.metadata):
        assert not {str(key).lower() for key in metadata if any(word in str(key).lower() for word in forbidden)}


def test_paper_only_contract_values_are_passive_and_live_execution_is_disabled():
    candidate = build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0], STRONG_BULLISH)
    eligibility = evaluate_candidate_eligibility(candidate)
    score = score_market_opportunity_candidate(candidate, eligibility)
    assert candidate.execution_mode == "PAPER" and candidate.live_execution_eligible is False
    assert score.final_score >= 0 and eligibility.rankable is True
