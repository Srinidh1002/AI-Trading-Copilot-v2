import subprocess,sys
from pathlib import Path
def test_candidate_import_is_lightweight():
 root=Path(__file__).resolve().parents[1]
 code="import sys; import services.contracts; from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1; print(any(x in sys.modules for x in ('pandas','numpy','scipy','requests','yfinance','streamlit','openai')))"
 assert subprocess.run([sys.executable,"-c",code],cwd=root,text=True,capture_output=True,check=True).stdout.strip()=="False"
