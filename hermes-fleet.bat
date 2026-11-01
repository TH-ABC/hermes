@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\hermes_fleet_cli.py" %*
) else (
    python "scripts\hermes_fleet_cli.py" %*
)
endlocal
