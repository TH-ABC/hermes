# setup.ps1 - one-shot install: venv + deps + chromium + firewall + scheduled task
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $dir
$port = if ($env:MUSEAI_PORT) { $env:MUSEAI_PORT } else { "8770" }

if (-not (Test-Path ".venv\Scripts\python.exe")) { uv venv .venv --python 3.12 }
uv pip install --python .venv\Scripts\python.exe -r deploy\windows\requirements.txt
.venv\Scripts\python.exe -m playwright install chromium

if (-not (Get-NetFirewallRule -DisplayName "MuseAI Bridge $port" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "MuseAI Bridge $port" -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow | Out-Null
}

$taskName = "MuseAI_Bridge"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dir\deploy\windows\run_daemon.ps1`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\Admin"
$principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\Admin" -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "MuseAI_Bridge task registered and started on port $port"
