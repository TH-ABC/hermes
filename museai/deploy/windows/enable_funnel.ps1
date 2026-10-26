# enable_funnel.ps1 - mở MuseAI Bridge ra Internet qua Tailscale Funnel (HTTPS :8443)
# để Tool-RD trên Vercel gọi được. Chạy bằng PowerShell (Admin) tại D:\MuseAI:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\enable_funnel.ps1
# Qua Funnel, server.py chỉ mở /v1/status, /v1/batch/async, /v1/batch/status, /media/<file>
# và bắt buộc header X-API-Key = MUSE_API_KEY (trong .env).
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $dir
$port = if ($env:MUSEAI_PORT) { $env:MUSEAI_PORT } else { "8770" }

$envFile = Join-Path $dir ".env"
if (-not (Test-Path $envFile) -or -not (Select-String -Path $envFile -Pattern '^MUSE_API_KEY=.+' -Quiet)) {
    $key = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    Add-Content $envFile -Encoding utf8 "MUSE_API_KEY=$key"
    Write-Host "Da tao MUSE_API_KEY moi trong .env"
}

# Funnel chỉ cho cổng 443/8443/10000; 443 đang dùng cho app khác nên dùng 8443.
$ts = "C:\Program Files\Tailscale\tailscale.exe"
& $ts funnel --bg --https=8443 "http://127.0.0.1:$port"
& $ts funnel status

# Restart bridge để nạp .env mới
Stop-ScheduledTask -TaskName "MuseAI_Bridge" -ErrorAction SilentlyContinue
Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-ScheduledTask -TaskName "MuseAI_Bridge"
Write-Host "Xong. Public URL: https://$((& $ts status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')):8443"
