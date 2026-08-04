"""P5-12G fresh-process side-effect, environment, and module-footprint checks."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PREFIXES = ("pandas", "numpy", "scipy", "requests", "httpx", "aiohttp", "yfinance", "bs4", "selenium", "streamlit", "smartapi", "openai", "anthropic", "langchain", "transformers", "nltk", "spacy", "dashboard", "providers", "brokers", "execution", "strategy", "decisions", "risk", "portfolio")
SECRET_NAMES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SMARTAPI_API_KEY", "SMARTAPI_CLIENT_ID", "SMARTAPI_PASSWORD", "SMARTAPI_TOTP_SECRET", "DATABASE_URL", "BROKER_TOKEN", "PROVIDER_API_KEY")
CERTIFIED_MODULES = tuple(
    ["tests.fixtures.p5_12"]
    + [f"tests.fixtures.p5_12.{path.stem}" for path in sorted((ROOT / "tests" / "fixtures" / "p5_12").glob("*.py")) if path.stem != "__init__"]
    + [f"tests.{path.stem}" for path in sorted((ROOT / "tests").glob("test_p5_12[abcdef]_*.py"))]
)
SCRIPT = r'''
import builtins, importlib, json, os, pathlib, socket, sqlite3, sys, threading
def blocked(*args, **kwargs): raise AssertionError("import/build side effect attempted")
socket.socket.connect = blocked
sqlite3.connect = blocked
threading.Thread.start = blocked
_open = builtins.open
def guarded_open(file, mode="r", *args, **kwargs):
    if any(flag in mode for flag in ("w", "a", "x", "+")): raise AssertionError("filesystem write attempted")
    return _open(file, mode, *args, **kwargs)
builtins.open = guarded_open
pathlib.Path.write_text = blocked; pathlib.Path.write_bytes = blocked
for module in json.loads(os.environ["P512_G_CERTIFIED_MODULES"]): importlib.import_module(module)
from tests.fixtures.p5_12 import *
from services.opportunity_ranking import evaluate_candidate_eligibility, rank_four_market_opportunities, score_market_opportunity_candidate
for scenario, event, session in ((STRONG_BULLISH, None, None), (UNAVAILABLE, None, None), (CPI_WARNING, CPI_WARNING_EVENT_PROFILE, None), (RBI_BLOCK, RBI_BLOCK_EVENT_PROFILE, None), (HOLIDAY, None, HOLIDAY_SESSION)):
    candidate = build_market_opportunity_candidate(CANONICAL_MARKET_IDENTITIES[0], scenario, event_profile=event, session_profile=session)
    score_market_opportunity_candidate(candidate, evaluate_candidate_eligibility(candidate))
rank_four_market_opportunities(tuple(build_market_opportunity_candidate(identity, UNAVAILABLE) for identity in CANONICAL_MARKET_IDENTITIES))
relevant = sorted(name for name in sys.modules if name.split(".")[0].lower() in ''' + repr(PROHIBITED_PREFIXES) + r''')
print(json.dumps({"prohibited": relevant, "fixture": "tests.fixtures.p5_12" in sys.modules, "ranking": "services.opportunity_ranking" in sys.modules}, sort_keys=True))
'''


def _run(hash_seed: int) -> dict[str, object]:
    env = dict(os.environ, PYTHONHASHSEED=str(hash_seed))
    env["P512_G_CERTIFIED_MODULES"] = json.dumps(CERTIFIED_MODULES)
    for name in SECRET_NAMES:
        env.pop(name, None)
    completed = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_fresh_subprocess_imports_and_representative_builds_have_no_side_effects():
    result = _run(0)
    assert result == {"fixture": True, "prohibited": [], "ranking": True}


def test_module_footprint_and_output_are_hash_seed_and_environment_independent():
    assert _run(0) == _run(1) == _run(42)
