param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ConfigDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$GeminiRoot = Split-Path -Parent $ConfigDir

$GeminiSrc = Join-Path $ConfigDir "GEMINI.global.md"
$GeminiDst = Join-Path $GeminiRoot "GEMINI.md"

$HooksSrc = Join-Path $ConfigDir "hooks.json.portable"
$HooksDst = Join-Path $ConfigDir "hooks.json"

if (Test-Path $GeminiSrc) {
    if (-not (Test-Path $GeminiDst) -or $Force) {
        Copy-Item -Path $GeminiSrc -Destination $GeminiDst -Force
        Write-Host "Installed GEMINI.md -> $GeminiDst"
    } else {
        Write-Host "Skipped GEMINI.md (already exists; pass -Force to overwrite)"
    }
}

if (Test-Path $HooksSrc) {
    if (-not (Test-Path $HooksDst) -or $Force) {
        Copy-Item -Path $HooksSrc -Destination $HooksDst -Force
        Write-Host "Installed portable hooks.json -> $HooksDst"
    } else {
        Write-Host "Skipped hooks.json (already exists; pass -Force to overwrite)"
    }
}

Write-Host "`nRunning operator_router unit tests..."
python -m unittest discover -s (Join-Path $ConfigDir "scripts\tests") -v
