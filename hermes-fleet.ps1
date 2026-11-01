$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$cli = Join-Path $PSScriptRoot "scripts\hermes_fleet_cli.py"

if (Test-Path $py) {
    & $py $cli @args
} else {
    & python $cli @args
}
