"""P5-12G static dependency and public-API isolation certification."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P5_SOURCES = tuple(sorted((ROOT / "tests" / "fixtures" / "p5_12").glob("*.py"))) + tuple(sorted((ROOT / "tests").glob("test_p5_12[abcdef]_*.py")))
FORBIDDEN_PREFIXES = {
    "providers", "broker", "brokers", "execution", "dashboard", "streamlit", "openai", "anthropic", "langchain", "transformers", "nltk", "spacy", "requests", "httpx", "aiohttp", "yfinance", "bs4", "selenium", "websocket", "websockets", "socket", "pandas", "numpy", "scipy",
}
FORBIDDEN_NAMES = {"random", "secrets", "uuid", "uuid1", "uuid4", "urandom", "now", "utcnow", "today", "time", "perf_counter", "monotonic"}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"__import__", "import_module"} and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            names.add(node.args[0].value)
    return names


def _is_forbidden_module(name: str) -> bool:
    parts = name.lower().split(".")
    return any(part in FORBIDDEN_PREFIXES for part in parts) or name.startswith("services.providers")


def test_p5_12_sources_have_no_direct_or_dynamic_prohibited_imports():
    violations = {str(path.relative_to(ROOT)): sorted(name for name in _import_names(_tree(path)) if _is_forbidden_module(name)) for path in P5_SOURCES}
    assert not {path: names for path, names in violations.items() if names}, violations


def test_p5_12_sources_reject_nondeterministic_generation_calls():
    violations = {}
    for path in P5_SOURCES:
        tree = _tree(path)
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        calls.update(node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute))
        imports = {name.rsplit(".", 1)[-1] for name in _import_names(tree)}
        found = (calls | imports) & FORBIDDEN_NAMES
        if found:
            violations[str(path.relative_to(ROOT))] = sorted(found)
    assert not violations, violations


def test_p5_12_imports_use_public_fixture_and_ranking_surfaces():
    violations = {}
    for path in P5_SOURCES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(("tests.fixtures.p5_12", "services.opportunity_ranking")):
                private = [alias.name for alias in node.names if alias.name.startswith("_")]
                if private:
                    violations[str(path.relative_to(ROOT))] = private
    assert not violations, violations


def test_package_reexports_are_fixture_contract_and_ranking_only():
    for relative in ("tests/fixtures/p5_12/__init__.py", "services/contracts/__init__.py", "services/opportunity_ranking/__init__.py"):
        names = _import_names(_tree(ROOT / relative))
        forbidden = sorted(name for name in names if _is_forbidden_module(name))
        assert not forbidden, f"{relative}: {forbidden}"
