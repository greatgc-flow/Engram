# test-runner.ps1 — Porta-Flow Full Test Suite Orchestrator
#
# Runs all test layers and produces a unified report:
#   Layer 1: host-test.ps1    — host-side (settings, statusline, VS Code, npm)
#   Layer 2: sandbox-test.bat — unit tests (WSB preferred, local fallback)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File test-runner.ps1 [options]
#
# Options:
#   -Local      Force local run (skip WSB even if available)
#   -WsbOnly    Run WSB sandbox layer only
#   -HostOnly   Run host-test.ps1 layer only
#   -BaseDir    Portable env root (default: auto-detected)
#   -Quiet      Suppress per-test output

param(
    [switch]$Local,
    [switch]$WsbOnly,
    [switch]$HostOnly,
    [string]$BaseDir = "",
    [switch]$Quiet
)

Set-StrictMode -Off
$ErrorActionPreference = "SilentlyContinue"

# ----------------------------------------------------------------
# Paths
# ----------------------------------------------------------------
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$SysDir     = Split-Path -Parent $ScriptDir
if (-not $BaseDir) { $BaseDir = Split-Path -Parent $SysDir }

$ResultsDir = Join-Path $ScriptDir "results"
New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null
$Timestamp  = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportFile = Join-Path $ResultsDir "full-report_$Timestamp.txt"

function log {
    param([string]$msg, [string]$color = "White")
    Write-Host $msg -ForegroundColor $color
    Add-Content -Path $ReportFile -Value $msg -Encoding UTF8
}

# ----------------------------------------------------------------
# Header
# ----------------------------------------------------------------
log ""
log "=============================================================" "Cyan"
log "  Porta-Flow Full Test Suite" "Cyan"
log "  Run: $Timestamp" "Cyan"
log "  BaseDir: $BaseDir" "Cyan"
log "=============================================================" "Cyan"

$HostResult   = $null
$SandboxPass  = 0
$SandboxFail  = 0
$SandboxTotal = 0
$SandboxRan   = $false

# ================================================================
# LAYER 1: Host-Side Tests
# ================================================================
if (-not $WsbOnly) {
    log ""
    log "--- LAYER 1: Host-Side Tests ---" "Yellow"

    $hostScript = Join-Path $ScriptDir "host-test.ps1"
    if (-not (Test-Path $hostScript)) {
        log "[ERROR] host-test.ps1 not found: $hostScript" "Red"
    } else {
        try {
            $HostResult = & $hostScript -BaseDir $BaseDir -Quiet:$Quiet
        } catch {
            log "[ERROR] host-test.ps1 threw: $_" "Red"
            $HostResult = [pscustomobject]@{ Pass=0; Fail=1; Skip=0; Total=1; OK=$false }
        }
    }
}

# ================================================================
# LAYER 2: Sandbox Tests
# ================================================================
if (-not $HostOnly) {
    log ""
    log "--- LAYER 2: Sandbox Tests ---" "Yellow"

    $sandboxBat = Join-Path $ScriptDir "sandbox-test.bat"
    if (-not (Test-Path $sandboxBat)) {
        log "[ERROR] sandbox-test.bat not found" "Red"
    } else {
        $UseWsb = $false

        if (-not $Local) {
            try {
                $feat = Get-WindowsOptionalFeature -Online -FeatureName "Containers-DisposableClientVM" -ErrorAction Stop
                $UseWsb = ($feat.State -eq "Enabled")
            } catch { $UseWsb = $false }

            if ($UseWsb) {
                log "  Windows Sandbox: AVAILABLE — isolated environment" "Green"
            } else {
                log "  Windows Sandbox: not enabled — using local run" "DarkYellow"
                log "  (Enable: optionalfeatures.exe -> Windows Sandbox)" "DarkYellow"
            }
        } else {
            log "  --Local: running sandbox-test.bat directly" "DarkYellow"
        }

        # --- WSB path ---
        if ($UseWsb) {
            $wsbLauncher = Join-Path $ScriptDir "launch-wsbtest.ps1"
            if (-not (Test-Path $wsbLauncher)) {
                log "[ERROR] launch-wsbtest.ps1 not found — falling back to local" "Red"
                $UseWsb = $false
            } else {
                log "  Launching WSB..." "Cyan"
                & $wsbLauncher
                $wsbResult = Join-Path $ResultsDir "result.txt"
                if (Test-Path $wsbResult) {
                    $content = Get-Content $wsbResult -Raw
                    if (-not $Quiet) { log $content }
                    if ($content -match "PASS=(\d+)")  { $SandboxPass  = [int]$Matches[1] }
                    if ($content -match "FAIL=(\d+)")  { $SandboxFail  = [int]$Matches[1] }
                    if ($content -match "TOTAL=(\d+)") { $SandboxTotal = [int]$Matches[1] }
                    $SandboxRan = $true
                } else {
                    log "  [WARN] WSB result file not received — did sandbox exit cleanly?" "DarkYellow"
                }
            }
        }

        # --- Local path ---
        if (-not $UseWsb) {
            # Resolve physical path (SUBST-aware)
            $physBase = $BaseDir
            $drive = ($BaseDir -replace '^([A-Za-z]):.*','$1').ToUpper()
            foreach ($line in (subst 2>&1)) {
                if ($line -match "^${drive}:\\\s+=>\s+(.+)$") {
                    $physRoot = $Matches[1].Trim().TrimEnd('\')
                    $physBase = $physRoot + $BaseDir.Substring(2)
                    break
                }
            }

            $localTR = Join-Path $ResultsDir "local_$Timestamp"
            $localTW = Join-Path $env:TEMP "PortaFlowTest_$PID"
            New-Item -ItemType Directory -Path $localTR -Force | Out-Null

            log "  Physical base: $physBase" "Gray"
            log "  Results dir  : $localTR" "Gray"
            log "  Running sandbox-test.bat with PD=$physBase ..." "Cyan"

            # sandbox-test.bat accepts %1 as PD override (added 2026-06-01)
            $proc = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c `"`"$sandboxBat`" `"$physBase`"`" > `"$localTR\result.txt`" 2>&1" `
                -Wait -PassThru -WindowStyle Hidden

            $localResult = Join-Path $localTR "result.txt"
            if (Test-Path $localResult) {
                $content = Get-Content $localResult -Raw
                if (-not $Quiet) { log $content }
                if ($content -match "PASS=(\d+)")  { $SandboxPass  = [int]$Matches[1] }
                if ($content -match "FAIL=(\d+)")  { $SandboxFail  = [int]$Matches[1] }
                if ($content -match "TOTAL=(\d+)") { $SandboxTotal = [int]$Matches[1] }
                $SandboxRan = $true
                # Copy to standard result.txt for easy access
                Copy-Item $localResult (Join-Path $ResultsDir "result.txt") -Force
            }

            # Cleanup temp workspace
            if (Test-Path $localTW) { Remove-Item $localTW -Recurse -Force -ErrorAction SilentlyContinue }
        }
    }
}

# ================================================================
# SUMMARY
# ================================================================
$grandPass  = 0
$grandFail  = 0
$grandTotal = 0
$overallOK  = $true

log ""
log "=============================================================" "Cyan"
log "  FULL TEST SUITE SUMMARY" "Cyan"
log "=============================================================" "Cyan"

if ($HostResult) {
    $grandPass  += $HostResult.Pass
    $grandFail  += $HostResult.Fail
    $grandTotal += $HostResult.Total
    if (-not $HostResult.OK) { $overallOK = $false }
    $hColor = if ($HostResult.Fail -eq 0) { "Green" } else { "Red" }
    log ("  Layer 1 (Host)    : PASS={0,3}  FAIL={1,3}  SKIP={2,3}  TOTAL={3,3}" -f `
        $HostResult.Pass, $HostResult.Fail, $HostResult.Skip, $HostResult.Total) $hColor
}

if ($SandboxRan) {
    $grandPass  += $SandboxPass
    $grandFail  += $SandboxFail
    $grandTotal += $SandboxTotal
    if ($SandboxFail -gt 0) { $overallOK = $false }
    $sColor = if ($SandboxFail -eq 0) { "Green" } else { "Red" }
    log ("  Layer 2 (Sandbox) : PASS={0,3}  FAIL={1,3}  TOTAL={2,3}" -f `
        $SandboxPass, $SandboxFail, $SandboxTotal) $sColor
}

log ""
$grandColor = if ($overallOK) { "Green" } else { "Red" }
log ("  GRAND TOTAL       : PASS={0,3}  FAIL={1,3}  TOTAL={2,3}" -f `
    $grandPass, $grandFail, $grandTotal) $grandColor

if ($overallOK) {
    log "  RESULT: *** ALL PASS ***" "Green"
} else {
    log "  RESULT: *** FAILED ($grandFail failures) ***" "Red"
}

log "=============================================================" "Cyan"
log "  Report saved: $ReportFile" "Gray"
log ""

# Symlink latest report
Copy-Item $ReportFile (Join-Path $ResultsDir "last-run.txt") -Force

exit $(if ($overallOK) { 0 } else { 1 })
