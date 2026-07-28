import subprocess,sys
from pathlib import Path
def test_result_import_is_lightweight():
 r=subprocess.run([sys.executable,"-c","import sys; from services.contracts.four_market_opportunity_ranking_result_v1 import FourMarketOpportunityRankingResultV1; print('pandas' in sys.modules)"],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True,check=True)
 assert r.stdout.strip()=="False"
