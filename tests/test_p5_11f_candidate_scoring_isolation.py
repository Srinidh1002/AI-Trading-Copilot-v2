import subprocess
import sys
from pathlib import Path


def test_scoring_import_is_lightweight_in_a_fresh_subprocess():
    code = """
import sys
import services.opportunity_ranking.scoring
from services.opportunity_ranking import CandidateRankingScoreV1, score_market_opportunity_candidate
blocked = ('pandas','numpy','scipy','requests','yfinance','SmartApi','smartapi','streamlit')
forbidden_prefixes = (
    'services.providers', 'services.brokers', 'services.execution',
    'services.dashboard', 'services.decisions', 'services.strategy',
    'services.risk', 'services.portfolio', 'services.news', 'services.nlp',
)
def is_forbidden_module(name):
    normalized = name.lower()
    return normalized == 'openai' or normalized.startswith('openai.') or any(
        normalized == prefix or normalized.startswith(prefix + '.')
        for prefix in forbidden_prefixes
    )
assert not any(name in sys.modules for name in blocked)
assert not any(is_forbidden_module(name) for name in sys.modules)
assert CandidateRankingScoreV1 and callable(score_market_opportunity_candidate)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
