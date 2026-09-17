import subprocess
import sys
from pathlib import Path


def test_tie_breaking_import_is_lightweight_in_a_fresh_subprocess():
    code = """
import sys
import services.opportunity_ranking.tie_breaking
from services.opportunity_ranking import CandidateTieBreakingResultV1, resolve_candidate_order
heavy = ('pandas', 'numpy', 'scipy', 'requests', 'yfinance', 'SmartApi', 'smartapi', 'streamlit')
prefixes = ('services.providers', 'services.brokers', 'services.execution', 'services.dashboard', 'services.decisions', 'services.strategy', 'services.risk', 'services.portfolio', 'services.news', 'services.nlp')
def forbidden(name):
    name = name.lower()
    return name == 'openai' or name.startswith('openai.') or any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes)
assert not any(name in sys.modules for name in heavy)
assert not any(forbidden(name) for name in sys.modules)
assert CandidateTieBreakingResultV1 and callable(resolve_candidate_order)
"""
    completed = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
