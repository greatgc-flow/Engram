# ================================================================
# integration-test.ps1  -  Engram Full Integration Test Suite (MECE Lifecycle)
#
# Coverage:
#   A. Zero-base component completeness (install.bat)
#   B. Registration state verification (register.bat / unregister.bat)
#   C. Cleanup verification (CLEANUP.bat)
# ================================================================

$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── Resolve base dir ────────────────────────────────────────────
if ($env:BASE_DIR) { $BASE = $env:BASE_DIR }
else { $BASE = (Get-Item (Join-Path $PSScriptRoot "..\..")).FullName }
$SYS   = Join-Path $BASE "_sys"
$TOOLS = Join-Path $SYS "tools"
$ENV   = Join-Path $SYS "env"
$TMPDIR = Join-Path $SYS "data\temp"

$ts    = Get-Date -Format "yyyyMMdd_HHmmss"
$RESULT_DIR = Join-Path $BASE "_archive\test-results"
if (-not (Test-Path $RESULT_DIR)) { New-Item -ItemType Directory -Force $RESULT_DIR | Out-Null }
$REPORT = Join-Path $RESULT_DIR "integration_$ts.txt"

$pass = 0; $fail = 0; $total = 0

# ── Helpers ─────────────────────────────────────────────────────
function T { # T "label" $condition
    param($label, $ok, $detail = "")
    $script:total++
    if ($ok) {
        $script:pass++
        Add-Content $REPORT "  [PASS] $label"
        Write-Host "  [PASS] $label" -ForegroundColor Green
    } else {
        $script:fail++
        $msg = if ($detail) { "  [FAIL] $label [$detail]" } else { "  [FAIL] $label" }
        Add-Content $REPORT $msg
        Write-Host $msg -ForegroundColor Red
    }
}
function H($group) {
    Add-Content $REPORT ""
    Add-Content $REPORT "[$group]"
    Add-Content $REPORT "----"
    Write-Host "`n[$group]" -ForegroundColor Cyan
}

# ── Header ──────────────────────────────────────────────────────
$header = @"
================================================================
  Engram MECE Lifecycle Integration Test Report
  Base  : $BASE
  Run   : $ts
================================================================
"@
Set-Content $REPORT $header
Write-Host $header -ForegroundColor White

# ================================================================
# GROUP A: Install (provision.deploy)
# ================================================================
H "GROUP A: Zero-base Component Completeness (install)"

T "node.exe present"         (Test-Path "$ENV\nodejs\node.exe")
T "npm.cmd present"          (Test-Path "$ENV\nodejs\npm.cmd")
T "git.exe present"          (Test-Path "$ENV\git\cmd\git.exe")
T "python.exe present"       ((Test-Path "$ENV\python\python.exe") -or (Test-Path "$ENV\venv\Scripts\python.exe"))

T "claude.exe present"       (Test-Path "$ENV\nodejs\npm-global\node_modules\@anthropic-ai\claude-code\bin\claude.exe")
$geminiBundle = "$ENV\nodejs\npm-global\node_modules\@google\gemini-cli\bundle\gemini.js"
T "gemini bundle present"    (Test-Path $geminiBundle)

T "ripgrep rg.exe"           (Test-Path "$TOOLS\apps\ripgrep\rg.exe" -or Test-Path "$TOOLS\ripgrep\rg.exe")
T "fd.exe"                   (Test-Path "$TOOLS\apps\fd\fd.exe" -or Test-Path "$TOOLS\fd\fd.exe")

$nodeVer = & "$ENV\nodejs\node.exe" --version 2>$null
T "node.exe executes"        ($LASTEXITCODE -eq 0) "ver=$nodeVer"

T "install.state.json exists" (Test-Path "$SYS\data\state\install.state.json")

# ================================================================
# GROUP B: Register / Unregister Lifecycle
# ================================================================
H "GROUP B: Register / Unregister Lifecycle"

T "dispatch.json configured" (Test-Path "$SYS\dispatch.json")
$dispatch = Get-Content "$SYS\dispatch.json" -Raw | ConvertFrom-Json
$installPl = $dispatch.pipelines.install
T "install is MECE (no register)" (-not ($installPl -contains "registry.apply") -and -not ($installPl -contains "virtual.mount"))

# Since this test environment is currently registered (from previous steps), we check register state
$regStatePath = "$SYS\data\state\register.state.json"
T "register.state.json exists" (Test-Path $regStatePath)

if (Test-Path $regStatePath) {
    $regState = Get-Content $regStatePath -Raw | ConvertFrom-Json
    $substDrive = $regState.subst_drive
    T "SUBST drive captured in state" ($null -ne $substDrive)
}

# ================================================================
# GROUP C: Cleanup Safety
# ================================================================
H "GROUP C: Cleanup Utility Readiness"

T "CLEANUP.bat present" (Test-Path "$BASE\CLEANUP.bat")
T "scrubber.py exists"  (Test-Path "$SYS\core\scrubber.py")

Write-Host "`n================================================================"
Write-Host "  RESULT: PASS=$pass  FAIL=$fail  TOTAL=$total"
Write-Host "================================================================"

if ($fail -gt 0) { exit 1 } else { exit 0 }