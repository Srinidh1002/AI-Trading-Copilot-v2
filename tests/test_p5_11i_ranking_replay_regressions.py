import ast
import json
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

from services.opportunity_ranking import rank_four_market_opportunities
from tests.test_p5_11i_ranking_replay_matrix import REPLAY_CASES


def _contains_mapping_proxy(value):
    if isinstance(value, MappingProxyType): return True
    if isinstance(value, dict): return any(_contains_mapping_proxy(item) for item in value.values())
    if isinstance(value, list): return any(_contains_mapping_proxy(item) for item in value)
    return False


def test_fail_closed_conflict_and_serialization_boundaries():
    blocked = rank_four_market_opportunities(REPLAY_CASES["BLOCKED_HIGH_SCORE_CANNOT_WIN"].candidates)
    assert blocked.rank_by_market[("NIFTY", "NSE")] is None
    unavailable = rank_four_market_opportunities(REPLAY_CASES["UNAVAILABLE_HIGH_SCORE_CANNOT_WIN"].candidates)
    assert unavailable.rank_by_market[("NIFTY", "NSE")] is None
    conflict = rank_four_market_opportunities(REPLAY_CASES["CONFLICTING_POLICY_ALLOWED"].candidates, REPLAY_CASES["CONFLICTING_POLICY_ALLOWED"].policy)
    assert ("NIFTY", "NSE") in conflict.conflicting_markets and conflict.rank_by_market[("NIFTY", "NSE")] == 1
    payload = conflict.to_dict()
    assert not _contains_mapping_proxy(payload)
    assert json.loads(conflict.to_json())["metadata"]["pipeline_version"] == "P5-11H"


def test_ranking_source_has_no_forbidden_nondeterministic_calls():
    root = Path(__file__).resolve().parents[1]
    files = [root / path for path in (
        "services/opportunity_ranking/eligibility.py", "services/opportunity_ranking/scoring.py",
        "services/opportunity_ranking/tie_breaking.py", "services/opportunity_ranking/aggregate.py",
        "services/opportunity_ranking/service.py", "services/contracts/four_market_opportunity_ranking_result_v1.py",
    )]
    forbidden = {"now", "utcnow", "today", "uuid4", "random", "choice"}
    for file in files:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not calls & forbidden, file


def test_public_ranking_import_is_lightweight():
    code = """
import sys
from services.opportunity_ranking import rank_four_market_opportunities, evaluate_four_market_opportunity_ranking
heavy=('pandas','numpy','scipy','requests','yfinance','SmartApi','smartapi','streamlit')
prefixes=('services.providers','services.brokers','services.execution','services.dashboard','services.decisions','services.strategy','services.risk','services.portfolio','services.news','services.nlp')
def forbidden(name):
 name=name.lower(); return name=='openai' or name.startswith('openai.') or any(name==prefix or name.startswith(prefix+'.') for prefix in prefixes)
assert not any(name in sys.modules for name in heavy)
assert not any(forbidden(name) for name in sys.modules)
assert callable(rank_four_market_opportunities) and callable(evaluate_four_market_opportunity_ranking)
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout
