from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
@pytest.mark.parametrize("token",("pandas","numpy","scipy","requests","yfinance","smartapi","streamlit","services.broker","provider","services.execution","random"))
def test_integration_import_isolated(token):
 code=f"import importlib,sys;importlib.import_module('services.broader_market_intelligence.integration');print(any({token!r} in x.lower() for x in sys.modules))"
 assert subprocess.run([str(PYTHON),'-c',code],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()=="False"
