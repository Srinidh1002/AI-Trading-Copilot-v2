import subprocess,sys
from pathlib import Path
def test_policy_import_is_lightweight():
 r=subprocess.run([sys.executable,"-c","import sys; from services.contracts.four_market_ranking_policy_v1 import FourMarketRankingPolicyV1; print('pandas' in sys.modules)"],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True,check=True)
 assert r.stdout.strip()=="False"
