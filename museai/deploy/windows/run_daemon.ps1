# run_daemon.ps1 - MuseAI Bridge 24/7 launcher with auto-restart (Windows on-prem)
$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $dir
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
# Nạp biến từ D:\MuseAI\.env (MUSE_API_KEY, MUSE_CORS_ORIGINS...) nếu có
$envFile = Join-Path $dir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { Set-Item -Path "Env:$($matches[1])" -Value $matches[2] }
    }
}
$port = if ($env:MUSEAI_PORT) { $env:MUSEAI_PORT } else { "8770" }
$py = Join-Path $dir ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path (Join-Path $dir "logs") | Out-Null
$log = Join-Path $dir "logs\museai.log"
$errLog = Join-Path $dir "logs\museai_err.log"

while ($true) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) { $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Start-Sleep 1 }
    Add-Content $log -Encoding utf8 "`n=== MuseAI Bridge started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') on port $port ==="
    cmd /c "`"$py`" -u bridge\server.py --port $port >> `"$log`" 2>> `"$errLog`""
    Add-Content $log -Encoding utf8 "=== MuseAI Bridge exited with code $LASTEXITCODE at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
    Start-Sleep -Seconds 5
}
