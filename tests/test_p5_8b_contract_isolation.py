from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
MODULES=("services.contracts.cross_market_evidence_v1","services.contracts.market_breadth_evidence_v1","services.contracts.volatility_context_v1","services.contracts.broader_market_intelligence_result_v1","services.contracts")
TOKENS=("pandas","numpy","yfinance","requests","smartapi","streamlit","services.broker","provider","services.execution","random")
@pytest.mark.parametrize("module",MODULES)
@pytest.mark.parametrize("token",TOKENS)
def test_clean_import_has_no_forbidden_runtime_dependencies(module,token):
 code=f"import importlib,sys;importlib.import_module({module!r});print(any({token!r} in x.lower() for x in sys.modules))"
 result=subprocess.run([str(PYTHON),"-c",code],cwd=ROOT,text=True,capture_output=True,check=True)
 assert result.stdout.strip()=="False"
