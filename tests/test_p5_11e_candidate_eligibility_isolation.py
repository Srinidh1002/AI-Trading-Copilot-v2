import subprocess,sys
from pathlib import Path
def test_import_is_lightweight():
 r=subprocess.run([sys.executable,"-c","import sys; import services.opportunity_ranking; print('pandas' in sys.modules)"],cwd=Path(__file__).resolve().parents[1],text=True,capture_output=True,check=True);assert r.stdout.strip()=="False"
