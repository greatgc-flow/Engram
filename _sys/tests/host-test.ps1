# host-test.ps1 — Engram Host-Side Integration Tests
# Tests Claude Code settings, statusline, VS Code integration, npm config.
# These tests are HOST-DEPENDENT and cannot run inside WSB.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File host-test.ps1
#   (Normally called by test-runner.ps1)

param(
    [string]$BaseDir = "P:",
    [switch]$Quiet
)

$script:Pass    = 0
$script:Fail    = 0
$script:Skip    = 0
$script:Results = [System.Collections.Generic.List[string]]::new()
$SysDir  = "$BaseDir\_sys"
$ClaudeHome = "$env:USERPROFILE\.claude"
$NpmGlobal  = "$SysDir\env\nodejs\npm-global"

function log { param([string]$msg) if (-not $Quiet) { Write-Host $msg } }

function T-Pass { param([string]$label)
    $script:Pass++
    $line = "  [PASS] $label"
    $script:Results.Add($line)
    log $line
}
function T-Fail { param([string]$label, [string]$detail = "")
    $script:Fail++
    $line = "  [FAIL] $label" + $(if ($detail) { " [$detail]" } else { "" })
    $script:Results.Add($line)
    log $line
}
function T-Skip { param([string]$label, [string]$reason)
    $script:Skip++
    $line = "  [SKIP] $label [$reason]"
    $script:Results.Add($line)
    log $line
}
function T-File { param([string]$label, [string]$path)
    if (Test-Path $path) { T-Pass $label } else { T-Fail $label "missing: $path" }
}
function T-Json { param([string]$label, [string]$path, [scriptblock]$check)
    if (-not (Test-Path $path)) { T-Fail $label "file missing: $path"; return }
    try {
        $j = Get-Content $path -Raw | ConvertFrom-Json
        if (& $check $j) { T-Pass $label } else { T-Fail $label "check failed" }
    } catch { T-Fail $label "invalid JSON: $_" }
}
function T-Content { param([string]$label, [string]$path, [string]$needle)
    if (-not (Test-Path $path)) { T-Fail $label "file missing: $path"; return }
    $txt = Get-Content $path -Raw
    if ($txt -match [regex]::Escape($needle)) { T-Pass $label }
    else { T-Fail $label "'$needle' not found" }
}

# ----------------------------------------------------------------
log ""
log "================================================================="
log "  Engram Host-Side Integration Tests"
log "  BaseDir: $BaseDir"
log "================================================================="

# ----------------------------------------------------------------
# GROUP H3: VS Code Integration (code.cmd)
# ----------------------------------------------------------------
log ""
log "[GROUP H3] VS Code Integration"

T-File "npm-global/code.cmd exists"  "$NpmGlobal\code.cmd"

if (Test-Path "$NpmGlobal\code.cmd") {
    $cmd = Get-Content "$NpmGlobal\code.cmd" -Raw
    if ($cmd -match "vscode" -and $cmd -match "Code\.exe") {
        T-Pass "code.cmd: references vscode/Code.exe"
    } else {
        T-Fail "code.cmd: references vscode/Code.exe" "Code.exe path not found in wrapper"
    }
} else {
    T-Skip "code.cmd: content check" "file missing"
}

$vscodePath = "$SysDir\env\vscode\Code.exe"
if (Test-Path $vscodePath) { T-Pass "VS Code portable: Code.exe exists" }
else { T-Skip "VS Code portable: Code.exe exists" "not installed on this machine (optional)" }

# code.cmd in PATH?
$codeInPath = (Get-Command "code" -ErrorAction SilentlyContinue)
if ($codeInPath -and $codeInPath.Source -like "*npm-global*") {
    T-Pass "code: found in PATH via npm-global"
} elseif ($codeInPath) {
    T-Fail "code: found in PATH via npm-global" "found at $($codeInPath.Source) instead"
} else {
    T-Skip "code: found in PATH via npm-global" "not in current PATH (run from start.bat session)"
}

# ----------------------------------------------------------------
# GROUP H4: npm / Node.js Portable Config
# ----------------------------------------------------------------
log ""
log "[GROUP H4] npm / Node.js Portable Config"

$npmPrefix = (npm config get prefix 2>$null)
if ($npmPrefix -and ($npmPrefix -like "*npm-global*" -or $npmPrefix -eq $NpmGlobal)) {
    T-Pass "npm config prefix: portable npm-global"
} else {
    T-Fail "npm config prefix: portable npm-global" "got: $npmPrefix"
}

T-File "npm-global: gemini.cmd installed" "$NpmGlobal\gemini.cmd"
T-File "npm-global: claude.cmd installed" "$NpmGlobal\claude.cmd"
T-File "Node.js portable: node.exe"       "$SysDir\env\nodejs\node.exe"

# ----------------------------------------------------------------
# GROUP H5: Portable Env Structure Verification
# ----------------------------------------------------------------
log ""
log "[GROUP H5] Portable Env Structure"

T-File "CONVENTION.md at root"           "$BaseDir\CONVENTION.md"
T-File "_archive dir exists"             "$BaseDir\_archive"
T-File "_sys/start.bat"                  "$SysDir\start.bat"
T-File "_sys/test/launch-wsbtest.ps1"    "$SysDir\test\launch-wsbtest.ps1"
T-File "_sys/test/host-test.ps1"         "$SysDir\test\host-test.ps1"

# CONVENTION.md has §9
T-Content "CONVENTION.md: §9 WSB policy"      "$BaseDir\CONVENTION.md" "§9"

# ----------------------------------------------------------------
# SUMMARY
# ----------------------------------------------------------------
log ""
log "================================================================="
$total = $script:Pass + $script:Fail + $script:Skip
log ("  HOST TEST RESULT: PASS={0}  FAIL={1}  SKIP={2}  TOTAL={3}" -f $script:Pass, $script:Fail, $script:Skip, $total)
log "================================================================="
log ""

if ($script:Fail -gt 0) {
    log "--- FAILURES ---"
    $script:Results | Where-Object { $_ -match "\[FAIL\]" } | ForEach-Object { log $_ }
    log ""
}

# Output structured result (captured by test-runner.ps1 via & operator)
[pscustomobject]@{
    Pass  = $script:Pass
    Fail  = $script:Fail
    Skip  = $script:Skip
    Total = $total
    Lines = $script:Results.ToArray()
    OK    = ($script:Fail -eq 0)
}

# Explicit exit code for standalone runs (does NOT affect & invocation in test-runner.ps1)
if ($MyInvocation.InvocationName -ne '.') {
    exit $(if ($script:Fail -eq 0) { 0 } else { 1 })
}
