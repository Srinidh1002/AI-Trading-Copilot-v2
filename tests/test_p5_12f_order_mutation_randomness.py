"""P5-12F order, caller-mutation, subprocess, and source determinism checks."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

from services.opportunity_ranking import rank_four_market_opportunities
from tests.fixtures.p5_12 import *


def _matrix(): return {identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}


def test_representative_input_permutations_preserve_semantic_ranking():
    clean = build_four_market_candidate_set(_matrix())
    warning = build_four_market_candidate_set(_matrix(), event_profiles_by_market={CANONICAL_MARKET_IDENTITIES[1]: CPI_WARNING_EVENT_PROFILE})
    quality = build_four_market_candidate_set(_matrix(), source_timestamps_by_market={CANONICAL_MARKET_IDENTITIES[2]: build_freshness_timestamp_profile("STALE")})
    rejected = build_four_market_candidate_set({CANONICAL_MARKET_IDENTITIES[0]: STRONG_BULLISH, CANONICAL_MARKET_IDENTITIES[1]: CONFLICTING, CANONICAL_MARKET_IDENTITIES[2]: BLOCKED, CANONICAL_MARKET_IDENTITIES[3]: UNAVAILABLE})
    for candidates in (clean, warning, quality, rejected):
        baseline = rank_four_market_opportunities(candidates)
        orders = (candidates, tuple(reversed(candidates)), candidates[1:] + candidates[:1], candidates[2:] + candidates[:2])
        for ordered in orders:
            result = rank_four_market_opportunities(ordered)
            assert result.semantic_dict() == baseline.semantic_dict()
            assert result.rank_by_market == baseline.rank_by_market
            assert result.selected_market == baseline.selected_market and result.tied_markets == baseline.tied_markets


def test_fixture_and_ranking_inputs_are_not_mutated():
    matrix = _matrix()
    timestamps = {CANONICAL_MARKET_IDENTITIES[0]: build_freshness_timestamp_profile("MIXED")}
    events = {CANONICAL_MARKET_IDENTITIES[1]: CPI_WARNING_EVENT_PROFILE}
    sessions = {CANONICAL_MARKET_IDENTITIES[2]: SPECIAL_SESSION_PROFILE}
    baseline = (dict(matrix), dict(timestamps), dict(events), dict(sessions))
    candidates = build_four_market_candidate_set(matrix, source_timestamps_by_market=timestamps, event_profiles_by_market=events, session_profiles_by_market=sessions)
    ranked = rank_four_market_opportunities(candidates)
    assert (matrix, timestamps, events, sessions) == baseline
    assert candidates == tuple(candidates) and ranked.candidates == candidates and ranked.to_dict() == ranked.to_dict()


def test_fixture_sources_reject_random_uuid_clock_and_hash_ids():
    root = Path(__file__).resolve().parent / "fixtures" / "p5_12"
    forbidden = {"random", "secrets", "uuid", "uuid1", "uuid4", "urandom", "hash", "now", "utcnow", "today", "time", "perf_counter"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        calls.update(node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute))
        assert not (imported | calls) & forbidden, path


_SUBPROCESS_SCRIPT = """
import json
from tests.fixtures.p5_12 import CANONICAL_MARKET_IDENTITIES, STRONG_BULLISH, CPI_WARNING_EVENT_PROFILE, build_four_market_candidate_set
from services.opportunity_ranking import rank_four_market_opportunities
matrix = {identity: STRONG_BULLISH for identity in CANONICAL_MARKET_IDENTITIES}
candidates = build_four_market_candidate_set(matrix, event_profiles_by_market={CANONICAL_MARKET_IDENTITIES[1]: CPI_WARNING_EVENT_PROFILE})
result = rank_four_market_opportunities(tuple(reversed(candidates)))
print(json.dumps(result.semantic_dict(), sort_keys=True, separators=(\",\", \":\"), allow_nan=False))
"""


def _subprocess_output(hash_seed):
    completed = subprocess.run([sys.executable, "-c", _SUBPROCESS_SCRIPT], cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, PYTHONHASHSEED=str(hash_seed)), check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return completed.stdout


def test_fresh_subprocess_and_python_hash_seed_outputs_are_identical():
    outputs = (_subprocess_output(0), _subprocess_output(1), _subprocess_output(42), _subprocess_output(0))
    assert outputs.count(outputs[0]) == len(outputs)
    assert json.loads(outputs[0]) == json.loads(outputs[-1])


def test_ranking_id_is_stable_for_reordered_semantic_candidate_set():
    candidates = build_four_market_candidate_set(_matrix())
    first = rank_four_market_opportunities(candidates); second = rank_four_market_opportunities(tuple(reversed(candidates)))
    assert first.ranking_result_id == second.ranking_result_id and first.semantic_dict() == second.semantic_dict()
