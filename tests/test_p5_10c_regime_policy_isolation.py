from pathlib import Path
import subprocess
def test_policy_import_isolated_from_pandas():
 root=Path(__file__).resolve().parents[1];r=subprocess.run([str(root/"venv"/"Scripts"/"python.exe"),"-c","import services.contracts as c,sys;c.MarketRegimePolicyV1;print('pandas' in sys.modules)"],cwd=root,text=True,capture_output=True,check=True);assert r.stdout.strip()=="False"
