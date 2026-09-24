$ErrorActionPreference = "Stop"
$taskName = "AI-Trading-Copilot-Supervisor"
$repo = "C:\Users\sreen\OneDrive\Documents\GitHub\AI-Trading-Copilot-v2-five-market-readiness"
$script = Join-Path $repo "tools\start_supervisor_if_fresh.ps1"

if (-not (Test-Path $script)) {
    throw "Missing scheduled-task entry script: $script"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $repo

$trigger = New-ScheduledTaskTrigger -Daily -At "08:55"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 16)

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force

Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State
