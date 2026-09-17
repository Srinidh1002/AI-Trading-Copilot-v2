from pathlib import Path
import subprocess
def test_aggregate_import_has_no_pandas():
 root=Path(__file__).resolve().parents[1];out=subprocess.run([str(root/"venv"/"Scripts"/"python.exe"),"-c","import importlib,sys;importlib.import_module('services.external_context.aggregate');print('pandas' in sys.modules)"],cwd=root,text=True,capture_output=True,check=True);assert out.stdout.strip()=="False"
