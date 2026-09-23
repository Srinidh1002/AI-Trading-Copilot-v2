$ErrorActionPreference = "Stop"
$repo = "C:\Users\sreen\OneDrive\Documents\GitHub\AI-Trading-Copilot-v2-five-market-readiness"
$py   = "C:\Users\sreen\OneDrive\Documents\GitHub\AI-Trading-Copilot-v2-fyers312-venv\Scripts\python.exe"

Set-Location $repo
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
New-Item -ItemType Directory -Force -Path "logs\scheduler" | Out-Null

$probe = & $py -c @"
from dotenv import load_dotenv; load_dotenv()
import os, base64, json, time
t = os.getenv('FYERS_ACCESS_TOKEN','')
try:
    p = t.split('.')[1]; p += '='*(-len(p)%4)
    d = json.loads(base64.urlsafe_b64decode(p))
    print(int(d['exp']) - int(time.time()))
except Exception:
    print(-1)
"@

$stamp = Get-Date -Format o
if ([int]$probe -lt 600) {
    "[$stamp] token not fresh ($probe s). Supervisor NOT started." |
        Out-File -Append "logs\scheduler\start_guard.log"
    exit 1
}

"[$stamp] token fresh ($probe s). Starting supervisor." |
    Out-File -Append "logs\scheduler\start_guard.log"

& $py -m services.paper_orchestration.automated_paper_supervisor_v2 --poll-seconds 30
