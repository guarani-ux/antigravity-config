param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ConfigDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$GeminiRoot = Split-Path -Parent $ConfigDir
$PosixConfigDir = $ConfigDir -replace "\\", "/"

$PyCmd = $null
foreach ($cand in @("python", "python3", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        $PyCmd = $cand
        break
    }
}
if (-not $PyCmd) {
    Write-Error "Python (python, python3, or py) is required on PATH."
    exit 1
}

$GeminiSrc = Join-Path $ConfigDir "GEMINI.global.md"
$GeminiDst = Join-Path $GeminiRoot "GEMINI.md"

$HooksSrc = Join-Path $ConfigDir "hooks.json.portable"
$HooksDst = Join-Path $ConfigDir "hooks.json"

$McpSrc = Join-Path $ConfigDir "mcp_config.portable.json"
$McpDst = Join-Path $ConfigDir "mcp_config.json"

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
        $HooksText = Get-Content -Path $HooksSrc -Raw -Encoding UTF8
        $HooksText = $HooksText.Replace("__PYTHON__", $PyCmd).Replace("__CONFIG_DIR__", $PosixConfigDir)
        [System.IO.File]::WriteAllText($HooksDst, $HooksText, [System.Text.UTF8Encoding]::new($false))
        Write-Host "Installed hooks.json ($PyCmd, $PosixConfigDir) -> $HooksDst"
    } else {
        Write-Host "Skipped hooks.json (already exists; pass -Force to overwrite)"
    }
}

if (Test-Path $McpSrc) {
    if (-not (Test-Path $McpDst) -or $Force) {
        Copy-Item -Path $McpSrc -Destination $McpDst -Force
        Write-Host "Installed mcp_config.json -> $McpDst"
    } else {
        Write-Host "Skipped mcp_config.json (already exists; pass -Force to overwrite)"
    }
}

Write-Host "`nRunning sentinel & router unit tests..."
& $PyCmd -m unittest discover -s (Join-Path $ConfigDir "scripts\tests") -v
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
