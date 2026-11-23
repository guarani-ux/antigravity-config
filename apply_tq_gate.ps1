param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ConfigDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = Join-Path $ConfigDir "scripts\hook_v4.py.with_tq_gate"
$Dst = Join-Path $ConfigDir "scripts\hook_v4.py"

if (-not (Test-Path $Src)) {
    throw "Missing staged hook file: $Src"
}

Copy-Item -Path $Src -Destination $Dst -Force
Write-Host "Activated Test Quality Gate (TQ-01..TQ-05) inside $Dst"

Write-Host "`nRunning antigravity-config unit tests..."
python -m unittest discover -s (Join-Path $ConfigDir "scripts\tests") -v
