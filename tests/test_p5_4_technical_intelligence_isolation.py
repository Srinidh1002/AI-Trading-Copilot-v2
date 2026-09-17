import subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
MODULES=("services.technical_intelligence","services.technical_intelligence.timeframe_analysis","services.technical_intelligence.aggregation","services.technical_intelligence.pipeline")
TOKENS=("pandas","numpy","yfinance","requests","urllib","smartapi","angel","nse","streamlit","provider")
@pytest.mark.parametrize("module",MODULES)
@pytest.mark.parametrize("token",TOKENS)
def test_clean_import_has_no_forbidden_dependency(module,token):
 code=f"import sys, {module}; print(any('{token}' in name.lower() for name in sys.modules))"
 out=subprocess.run([str(PYTHON),"-c",code],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
 assert out=="False"
