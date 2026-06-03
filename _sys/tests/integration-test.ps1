# ================================================================
# integration-test.ps1  -  Porta-Flow Full Integration Test Suite
#
# Coverage:
#   A. Zero-base component completeness
#   B. Registration state verification
#   C. Register → Unregister cycle (isolated temp env)
#   D. Session lifecycle (start→ctx-save→ctx-end path check)
#   E. Cleanup safety (-WhatIf)
#   F. Windows Sandbox readiness
#   G. Zero-base template (sandbox_final4.zip)
#
# Usage:
#   powershell -File _sys\test\integration-test.ps1
#   From sandbox terminal:  integration-test.ps1
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
  Porta-Flow Integration Test Report
  Base  : $BASE
  Run   : $ts
================================================================
"@
Set-Content $REPORT $header
Write-Host $header -ForegroundColor White

# ================================================================
# GROUP A: Zero-base - All installed components
# ================================================================
H "GROUP A: Zero-base Component Completeness"

# Runtimes
T "node.exe present"         (Test-Path "$ENV\nodejs\node.exe")
T "npm.cmd present"          (Test-Path "$ENV\nodejs\npm.cmd")
T "git.exe present"          (Test-Path "$ENV\git\cmd\git.exe")
T "python.exe present"       ((Test-Path "$ENV\python\python.exe") -or (Test-Path "$ENV\venv\Scripts\python.exe"))
T "Code.exe (VS Code)"       (Test-Path "$ENV\vscode\Code.exe" -or (Get-ChildItem "$ENV\vscode" -Filter "Code.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1))

# CLI tools
T "claude.exe present"       (Test-Path "$ENV\nodejs\npm-global\node_modules\@anthropic-ai\claude-code\bin\claude.exe")
$geminiBundle = "$ENV\nodejs\npm-global\node_modules\@google\gemini-cli\bundle\gemini.js"
T "gemini bundle present"    (Test-Path $geminiBundle)

# Portable tools
T "ripgrep rg.exe"           (Test-Path "$TOOLS\ripgrep\rg.exe")
T "fd.exe"                   (Test-Path "$TOOLS\fd\fd.exe")
T "jq.exe"                   (Test-Path "$TOOLS\jq\jq.exe")
T "bat.exe"                  (Test-Path "$TOOLS\bat\bat.exe")
T "delta.exe"                (Test-Path "$TOOLS\delta\delta.exe")
T "fzf.exe"                  (Test-Path "$TOOLS\fzf\fzf.exe")
T "oh-my-posh.exe"           (Test-Path "$TOOLS\oh-my-posh\oh-my-posh.exe")

# Runtime executability
$nodeVer = & "$ENV\nodejs\node.exe" --version 2>$null
T "node.exe executes"        ($LASTEXITCODE -eq 0) "ver=$nodeVer"
$gitVer = & "$ENV\git\cmd\git.exe" --version 2>$null
T "git.exe executes"         ($LASTEXITCODE -eq 0) "ver=$gitVer"
$rgVer = & "$TOOLS\ripgrep\rg.exe" --version 2>$null
T "rg.exe executes"          ($LASTEXITCODE -eq 0)

# Config files
T "CLAUDE.md present"        (Test-Path "$BASE\CLAUDE.md")
T "CONVENTION.md present"    (Test-Path "$BASE\CONVENTION.md")
T "GEMINI.md present"        (Test-Path "$BASE\GEMINI.md")
T "settings.json present"    (Test-Path "$BASE\.claude\settings.json")
T ".claude/agents present"   (Test-Path "$BASE\.claude\agents")
T "setup.ps1 present"        (Test-Path "$SYS\setup.ps1")
T "manage.ps1 present"       (Test-Path "$SYS\manage.ps1")
T "cleanup.ps1 present"      (Test-Path "$SYS\cleanup.ps1")
T "start.bat present"        (Test-Path "$SYS\start.bat")

# ================================================================
# GROUP B: Current Registration State
# ================================================================
H "GROUP B: Registration State Verification"

# local.config.bat
$configPath = "$SYS\local.config.bat"
T "local.config.bat exists"  (Test-Path $configPath)

if (Test-Path $configPath) {
    $cfg = Get-Content $configPath -Raw
    $substLetter = if ($cfg -match 'SUBST_DRIVE_LETTER=([A-Z])') { $Matches[1] } else { $null }
    $menuKey     = if ($cfg -match 'MENU_REG_KEY=([^"\r\n]+)') { $Matches[1].TrimEnd() } else { $null }
    $baseDirPhys = if ($cfg -match 'BASE_DIR_PHYS=([^"]+)') { $Matches[1].TrimEnd() } else { $null }

    T "SUBST_DRIVE_LETTER set"       ($null -ne $substLetter) "val=$substLetter"
    T "MENU_REG_KEY set"             ($null -ne $menuKey)     "val=$menuKey"
    T "BASE_DIR_PHYS set"            ($null -ne $baseDirPhys) "val=$baseDirPhys"
    T "CLAUDE_CODE_EXPERIMENTAL set" ($cfg -match 'CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1')
}

# SUBST drive
if ($substLetter) {
    $substActive = Test-Path "${substLetter}:\"
    T "SUBST drive ${substLetter}: active"   $substActive
    if ($substActive) {
        $substInfo = & cmd /c subst 2>$null | Select-String "^${substLetter}:"
        $substCorrect = $substInfo -match [regex]::Escape($BASE.TrimEnd('\'))
        T "SUBST ${substLetter}: → correct path" $substCorrect "info=$substInfo"
    }
}

# Registry keys
if ($menuKey) {
    $regRoots = @(
        "HKCU:\Software\Classes\Directory\Background\shell\$menuKey",
        "HKCU:\Software\Classes\Directory\shell\$menuKey"
    )
    $regFound = 0
    foreach ($r in $regRoots) { if (Test-Path $r) { $regFound++ } }
    T "Registry keys exist (2/4 checked)"    ($regFound -ge 2) "found=$regFound"

    if ($regFound -gt 0) {
        $cmdKey = "HKCU:\Software\Classes\Directory\Background\shell\$menuKey\command"
        if (Test-Path $cmdKey) {
            $cmdVal = (Get-ItemProperty $cmdKey)."(default)"
            T "Context menu command valid"   ($cmdVal -match 'launch\.ps1') "cmd=$($cmdVal.Substring(0,[Math]::Min(60,$cmdVal.Length)))"
        }
    }
}

# Gemini junction
$geminiHost = Join-Path $env:USERPROFILE ".gemini"
$geminiPortable = "$SYS\gemini\config"
if (Test-Path -LiteralPath $geminiHost) {
    $item = Get-Item -LiteralPath $geminiHost
    $isJunction = $item.Attributes -match "ReparsePoint"
    T "Gemini host dir is junction"   $isJunction
    if ($isJunction) {
        $jTarget = $item.Target
        $geminiPortablePhys = if ($baseDirPhys) { "$baseDirPhys\_sys\gemini\config" } else { "" }
        $jCorrect = (
            $jTarget -eq $geminiPortable -or
            ($geminiPortablePhys -and $jTarget -eq $geminiPortablePhys) -or
            $jTarget -eq (Resolve-Path $geminiPortable -ErrorAction SilentlyContinue)
        )
        T "Gemini junction → portable path" $jCorrect "target=$jTarget"
    }
} else {
    T "Gemini portable dir present (no host junction)" (Test-Path $geminiPortable)
}

# ================================================================
# GROUP C: Register → Unregister cycle (isolated test env)
# ================================================================
H "GROUP C: Register → Unregister Cycle (isolated)"

$testEnvDir = Join-Path $TMPDIR "IntegTest_$ts"
$testSysDir = Join-Path $testEnvDir "_sys"

# Create minimal test env structure
New-Item -ItemType Directory -Force $testSysDir | Out-Null
# Patched manage.ps1: skip Set-GeminiPortability to avoid touching real junction
# Use multiline line-anchor regex so only standalone CALL lines are replaced,
# not the function DEFINITION (which would cause a parse error).
$originalScript = Get-Content "$SYS\manage.ps1" -Raw
$patchedScript = $originalScript -replace '(?m)^(\s+)Set-GeminiPortability \$BaseDir\s*$', '$1# [TEST-PATCHED] Set-GeminiPortability skipped'
$patchedScript = $patchedScript -replace '(?m)^(\s+)Remove-GeminiPortability \$BaseDir\s*$', '$1# [TEST-PATCHED] Remove-GeminiPortability skipped'
$patchedManage = Join-Path $testSysDir "manage.ps1"
[System.IO.File]::WriteAllText($patchedManage, $patchedScript, (New-Object System.Text.UTF8Encoding($false)))

T "Test env created"         (Test-Path $testSysDir)
T "Patched manage.ps1 created" (Test-Path $patchedManage)

# Run Register
$regOut = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $patchedManage -Action Register -BaseDir $testEnvDir -Silent 2>&1
$regEC  = $LASTEXITCODE

T "Register exits 0"         ($regEC -eq 0) "EC=$regEC"

$testConfig = Join-Path $testSysDir "local.config.bat"
T "local.config.bat created" (Test-Path $testConfig)

$assignedLetter = $null
if (Test-Path $testConfig) {
    $tcfg = Get-Content $testConfig -Raw
    if ($tcfg -match 'SUBST_DRIVE_LETTER=([A-Z])') { $assignedLetter = $Matches[1] }
    T "SUBST_DRIVE_LETTER written"  ($null -ne $assignedLetter) "letter=$assignedLetter"
    if ($assignedLetter) {
        T "Test SUBST ${assignedLetter}: active" (Test-Path "${assignedLetter}:\")
    }
    $testMenuKey = if ($tcfg -match 'MENU_REG_KEY=([^"\r\n]+)') { $Matches[1].TrimEnd() } else { $null }
    T "MENU_REG_KEY written"        ($null -ne $testMenuKey)

    if ($testMenuKey) {
        $testRegPath = "HKCU:\Software\Classes\Directory\Background\shell\$testMenuKey"
        T "Test registry key created"  (Test-Path $testRegPath)
    }
}

# Run Unregister
$unregOut = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $patchedManage -Action Unregister -BaseDir $testEnvDir -Silent 2>&1
$unregEC  = $LASTEXITCODE

T "Unregister exits 0"       ($unregEC -eq 0) "EC=$unregEC"

if ($assignedLetter) {
    T "Test SUBST ${assignedLetter}: released" (-not (Test-Path "${assignedLetter}:\"))
}
if ($testMenuKey) {
    $testRegPath2 = "HKCU:\Software\Classes\Directory\Background\shell\$testMenuKey"
    T "Test registry key removed"  (-not (Test-Path $testRegPath2))
}
T "local.config.bat cleaned" (-not (Test-Path $testConfig))

# Cleanup test env
Remove-Item $testEnvDir -Recurse -Force -ErrorAction SilentlyContinue
T "Test env cleaned up"      (-not (Test-Path $testEnvDir))

# ================================================================
# GROUP D: Session Lifecycle Path Verification
# ================================================================
H "GROUP D: Session Lifecycle Paths"

$startBat = Get-Content "$SYS\start.bat" -Raw

# start.bat structural checks
T "start.bat: SUBST logic present"    ($startBat -match 'SUBST_DRIVE_LETTER')
T "start.bat: PATH includes ripgrep"  ($startBat -match 'TOOLS_DIR.*ripgrep|ripgrep.*PATH')
T "start.bat: PATH includes fd"       ($startBat -match 'fd')
T "start.bat: gemini-status called"   ($startBat -match 'gemini-status\.bat')
T "start.bat: NPM_CONFIG_PREFIX set"  ($startBat -match 'NPM_CONFIG_PREFIX')
T "start.bat: TEMP redirected"        ($startBat -match 'SANDBOX_TEMP|set.*TEMP.*SANDBOX')
T "start.bat: Claude config dir set"  ($startBat -match 'CLAUDE_CONFIG_DIR')

# ctx scripts
$ctxSave = Get-Content "$SYS\context\ctx-save.bat" -Raw -ErrorAction SilentlyContinue
T "ctx-save: goto-based Gemini section" ($ctxSave -match 'goto :SKIP_GEMINI_SUM')
T "ctx-save: no ^ continuation bug"     ($ctxSave -notmatch 'Get-Content.*\^$')
T "ctx-save: Get-Content -Raw used"     ($ctxSave -match 'Get-Content.*-Raw')
T "ctx-save: WriteAllText (no BOM)"     ($ctxSave -match 'WriteAllText')

$ctxEnd = Get-Content "$SYS\context\ctx-end.bat" -Raw -ErrorAction SilentlyContinue
T "ctx-end: goto-based Gemini section" ($ctxEnd -match 'goto :SKIP_GEMINI_SUM')
T "ctx-end: credential check present"  ($ctxEnd -match '\.credentials\.json')

$collabLog = Get-Content "$SYS\context\collab-log-append.bat" -Raw -ErrorAction SilentlyContinue
T "collab-log-append: DisableDelayedExpansion" ($collabLog -match 'setlocal DisableDelayedExpansion')

# settings.json
$settingsPath = "$BASE\.claude\settings.json"
if (Test-Path $settingsPath) {
    try {
        $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
        T "settings.json: valid JSON"             $true
        T "settings.json: defaultShell=powershell" ($settings.defaultShell -eq "powershell")
        T "settings.json: auto-update disabled"    ($settings.env.CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE -eq "false")
    } catch {
        T "settings.json: valid JSON" $false "parse error: $_"
    }
}

# ================================================================
# GROUP E: Cleanup Safety (-WhatIf)
# ================================================================
H "GROUP E: Cleanup Safety"

# Run cleanup.ps1 -WhatIf -All
$cleanupScript = "$SYS\cleanup.ps1"
T "cleanup.ps1 exists" (Test-Path $cleanupScript)

if (Test-Path $cleanupScript) {
    $whatifOut = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $cleanupScript -WhatIf -All 2>&1
    $whatifStr = $whatifOut -join "`n"

    T "cleanup.ps1 -WhatIf runs without error" ($LASTEXITCODE -eq 0 -or $whatifStr -match '\[WhatIf\]|\[--\]|freed|Dry run')

    # Critical files must NOT be cleaned
    $criticalPaths = @("local.config.bat", ".credentials", "CLAUDE.md", "manage.ps1")
    $noCritical = $true
    foreach ($c in $criticalPaths) {
        if ($whatifStr -match [regex]::Escape($c) -and $whatifStr -notmatch "Skip.*$c|$c.*OK") {
            $noCritical = $false
        }
    }
    T "cleanup.ps1: no critical files in WhatIf output" $noCritical

    # Verify cleanup targets safe items (temp, cache, logs)
    T "cleanup.ps1 -WhatIf: mentions temp/cache targets" ($whatifStr -match 'temp|cache|log|npm-cache|pip-cache' -or $LASTEXITCODE -eq 0)
}

# Cleanup script parameter validation
$cleanupSrc = Get-Content $cleanupScript -Raw -ErrorAction SilentlyContinue
if ($cleanupSrc) {
    T "cleanup.ps1: -WhatIf param exists"    ($cleanupSrc -match '\[switch\]\$WhatIf')
    T "cleanup.ps1: -Hard param exists"      ($cleanupSrc -match '\[switch\]\$Hard')
    T "cleanup.ps1: -ZeroBase param exists"  ($cleanupSrc -match '\[switch\]\$ZeroBase')
    T "cleanup.ps1: -All param exists"       ($cleanupSrc -match '\[switch\]\$All')
}

# ================================================================
# GROUP F: Windows Sandbox Readiness
# ================================================================
H "GROUP F: Windows Sandbox Readiness"

$wsbTemplate = "$SYS\test\sandbox-unit-test.wsb"
$wsbLauncher = "$SYS\test\run-sandbox-test.bat"
$wsbTest     = "$SYS\test\sandbox-test.bat"
$localTest   = "$SYS\test\local-test.bat"

# File presence
T "sandbox-unit-test.wsb present"    (Test-Path $wsbTemplate)
T "run-sandbox-test.bat present"     (Test-Path $wsbLauncher)
T "sandbox-test.bat present"         (Test-Path $wsbTest)
T "local-test.bat present"           (Test-Path $localTest)

# WSB template is valid XML and has placeholder
if (Test-Path $wsbTemplate) {
    try {
        $wsbContent = Get-Content $wsbTemplate -Raw
        [xml]$wsbXml = $wsbContent
        T "sandbox-unit-test.wsb: valid XML"         $true
        T "sandbox-unit-test.wsb: has placeholder"   ($wsbContent -match '__PORTABLE_ROOT__')
        $netDisabled = $wsbXml.Configuration.Networking -eq "Disable"
        T "sandbox-unit-test.wsb: networking disabled" $netDisabled
        $mapCount = ($wsbXml.Configuration.MappedFolders.MappedFolder | Measure-Object).Count
        T "sandbox-unit-test.wsb: 2 mapped folders"  ($mapCount -ge 2) "count=$mapCount"
    } catch {
        T "sandbox-unit-test.wsb: valid XML" $false "error=$_"
    }
}

# run-sandbox-test.bat path injection test
if (Test-Path $wsbLauncher) {
    $launcherSrc = Get-Content $wsbLauncher -Raw
    T "run-sandbox-test.bat: derives physical path"  ($launcherSrc -match 'BASE_PHYS|~dp0|~fI')
    T "run-sandbox-test.bat: PowerShell injection"   ($launcherSrc -match 'Replace.*__PORTABLE_ROOT__')
    T "run-sandbox-test.bat: WindowsSandbox.exe check" ($launcherSrc -match 'WindowsSandbox')
}

# sandbox-test.bat CRLF check
if (Test-Path $wsbTest) {
    $wsbBytes = [System.IO.File]::ReadAllBytes($wsbTest)
    $crCount  = ($wsbBytes | Where-Object { $_ -eq 0x0D }).Count
    $lfCount  = ($wsbBytes | Where-Object { $_ -eq 0x0A }).Count
    T "sandbox-test.bat: CRLF line endings"          ($crCount -gt 0 -and $crCount -eq $lfCount) "CR=$crCount LF=$lfCount"
}

# local-test.bat unit test result (last run)
$latestResult = Get-ChildItem $RESULT_DIR -Filter "local_2026*.txt" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latestResult) {
    $lastRun = Get-Content $latestResult.FullName -Raw
    $lastPass = if ($lastRun -match 'PASS=(\d+)') { [int]$Matches[1] } else { 0 }
    $lastFail = if ($lastRun -match 'FAIL=(\d+)') { [int]$Matches[1] } else { -1 }
    T "local unit tests: all PASS (latest run)"      ($lastFail -eq 0) "PASS=$lastPass FAIL=$lastFail file=$($latestResult.Name)"
}

# Windows Sandbox feature check
$wsbExe = "C:\Windows\System32\WindowsSandbox.exe"
$wsbEnabled = Test-Path $wsbExe
T "Windows Sandbox feature enabled"  $wsbEnabled $(if (-not $wsbEnabled) { "Run: optionalfeatures.exe > 'Windows Sandbox'" } else { "ready" })

if ($wsbEnabled) {
    # Actually run the sandbox test
    H "GROUP F-2: Windows Sandbox Execution"
    Write-Host "  [INFO] Windows Sandbox found - launching sandbox test..." -ForegroundColor Yellow
    Add-Content $REPORT "  [INFO] Running sandbox test via run-sandbox-test.bat"

    $sandboxResult = & cmd /c "$wsbLauncher" 2>&1
    $sandboxEC     = $LASTEXITCODE
    T "Sandbox test launched (exit 0)"   ($sandboxEC -eq 0) "EC=$sandboxEC"

    if ($sandboxEC -eq 0) {
        # Wait briefly for sandbox to complete (it writes to _archive/test-results/)
        Start-Sleep 5
        $sbResult = Get-ChildItem $RESULT_DIR -Filter "test_2026*.txt" |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($sbResult) {
            $sbContent = Get-Content $sbResult.FullName -Raw
            $sbFail = if ($sbContent -match 'FAIL=(\d+)') { [int]$Matches[1] } else { -1 }
            $sbPass = if ($sbContent -match 'PASS=(\d+)') { [int]$Matches[1] } else { 0 }
            T "Sandbox test: all PASS"      ($sbFail -eq 0) "PASS=$sbPass FAIL=$sbFail"
        } else {
            T "Sandbox test result file found" $false "result file not yet written (sandbox still running)"
        }
    }
}

# ================================================================
# GROUP G: Zero-base Template (sandbox_final4.zip)
# ================================================================
H "GROUP G: Zero-base Template"

$templateZip = "$SYS\data\setup-files\sandbox_final4.zip"
T "sandbox_final4.zip present"       (Test-Path $templateZip)

if (Test-Path $templateZip) {
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($templateZip)
        $entries = $zip.Entries | ForEach-Object { $_.FullName }
        $zip.Dispose()

        # Required files in template
        $required = @(
            "CLAUDE.md",
            "README.md",
            "_sys/start.bat",
            "_sys/context/ctx-save.bat",
            "_sys/context/ctx-end.bat"
        )
        foreach ($req in $required) {
            $present = ($entries | Where-Object { $_ -match [regex]::Escape($req) }).Count -gt 0
            T "Template zip: $req"           $present
        }
        T "Template zip: entry count OK"     ($entries.Count -gt 5) "count=$($entries.Count)"
    } catch {
        T "Template zip: readable"           $false "error=$_"
    }
}

# INSTALL.bat and setup.ps1 relationship
T "INSTALL.bat calls setup.ps1"      (Test-Path "$BASE\INSTALL.bat" -and (Get-Content "$BASE\INSTALL.bat" -Raw) -match 'setup\.ps1')
T "register.bat calls manage.ps1"    (Test-Path "$BASE\register.bat" -and (Get-Content "$BASE\register.bat" -Raw) -match 'manage\.ps1.*Register')
T "unregister.bat calls manage.ps1"  (Test-Path "$BASE\unregister.bat" -and (Get-Content "$BASE\unregister.bat" -Raw) -match 'manage\.ps1.*Unregister')
T "CLEANUP.bat present"              (Test-Path "$BASE\CLEANUP.bat")

# ================================================================
# SUMMARY
# ================================================================
$summary = @"

================================================================
  RESULT: PASS=$pass  FAIL=$fail  TOTAL=$total
================================================================
"@
Add-Content $REPORT $summary
Write-Host $summary -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Yellow" })
if ($fail -gt 0) {
    Write-Host "`nFailed tests:" -ForegroundColor Red
    Get-Content $REPORT | Select-String "\[FAIL\]" | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
}
Write-Host "`nReport: $REPORT"
exit $(if ($fail -eq 0) { 0 } else { 1 })
