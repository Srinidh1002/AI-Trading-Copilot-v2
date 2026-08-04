from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
@pytest.mark.parametrize("module",("services.contracts.volatility_snapshot_v1","services.broader_market_intelligence.volatility"))
@pytest.mark.parametrize("token",("pandas","numpy","scipy","requests","yfinance","smartapi","streamlit","services.broker","provider","services.execution","random"))
def test_volatility_import_isolated(module,token):
 code=f"import importlib,sys;importlib.import_module({module!r});print(any({token!r} in x.lower() for x in sys.modules))"
 result=subprocess.run([str(PYTHON),"-c",code],cwd=ROOT,text=True,capture_output=True,check=True)
 assert result.stdout.strip()=="False"
