import subprocess
import sys
from pathlib import Path


def test_ranking_integration_import_is_lightweight_in_a_fresh_subprocess():
    code = """
import sys
import services.opportunity_ranking.aggregate
import services.opportunity_ranking.service
from services.opportunity_ranking import rank_four_market_opportunities, evaluate_four_market_opportunity_ranking
heavy = ('pandas', 'numpy', 'scipy', 'requests', 'yfinance', 'SmartApi', 'smartapi', 'streamlit')
prefixes = ('services.providers', 'services.brokers', 'services.execution', 'services.dashboard', 'services.decisions', 'services.strategy', 'services.risk', 'services.portfolio', 'services.news', 'services.nlp')
def forbidden(name):
    name = name.lower()
    return name == 'openai' or name.startswith('openai.') or any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes)
assert not any(name in sys.modules for name in heavy)
assert not any(forbidden(name) for name in sys.modules)
assert callable(rank_four_market_opportunities) and callable(evaluate_four_market_opportunity_ranking)
"""
    completed = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr or completed.stdout
