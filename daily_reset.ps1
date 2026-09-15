Write-Host '=== DAILY RESET ===' -ForegroundColor Cyan

Write-Host 'Stopping all Python bots...' -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host 'Resetting state to 0/100...' -ForegroundColor Yellow
python reset_state.py

Write-Host 'Verifying...' -ForegroundColor Yellow
python -c "import json; n=json.load(open('data/paper_trades/state.json'))['current_session']; s=json.load(open('data/paper_trades/sensex_state.json'))['current_session']; print(f'NIFTY: {n}/100  SENSEX: {s}/100')"

Write-Host ''
Write-Host 'Ready! Now start:' -ForegroundColor Green
Write-Host '  Terminal 1: python run_nifty.py' -ForegroundColor Green
Write-Host '  Terminal 2: python run_sensex.py' -ForegroundColor Green
