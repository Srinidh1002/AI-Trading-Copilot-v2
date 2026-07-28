from pathlib import Path
import subprocess,pytest
ROOT=Path(__file__).resolve().parents[1];PYTHON=ROOT/"venv"/"Scripts"/"python.exe"
@pytest.mark.parametrize("token",("pandas","numpy","scipy","requests","yfinance","smartapi","streamlit","provider","broker","execution","news","nlp","openai","random"))
def test_institutional_import_isolated(token):
 code=f"import importlib,sys;importlib.import_module('services.external_context.institutional');print(any({token!r} in x.lower() for x in sys.modules))";assert subprocess.run([str(PYTHON),"-c",code],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()=="False"
