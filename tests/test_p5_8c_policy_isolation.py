from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
@pytest.mark.parametrize("module",("services.contracts.broader_market_intelligence_policy_v1","services.contracts"))
@pytest.mark.parametrize("token",("pandas","numpy","yfinance","requests","smartapi","streamlit","services.broker","provider","services.execution","random"))
def test_policy_import_has_no_forbidden_dependencies(module,token):
 code=f"import importlib,sys;importlib.import_module({module!r});print(any({token!r} in name.lower() for name in sys.modules))"
 result=subprocess.run([str(PYTHON),"-c",code],cwd=ROOT,text=True,capture_output=True,check=True)
 assert result.stdout.strip()=="False"
