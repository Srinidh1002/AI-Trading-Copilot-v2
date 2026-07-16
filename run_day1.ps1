$end = Get-Date "15:30"

New-Item -ItemType Directory -Force -Path "logs" | Out-Null

while ((Get-Date) -lt $end) {

    $time = Get-Date -Format "HH-mm"

    python live_option_decision_nifty.py *> "logs\$time.txt"

    Start-Sleep -Seconds 300
}