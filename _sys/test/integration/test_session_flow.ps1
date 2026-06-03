# test_session_flow.ps1 - session 연속성 통합 테스트 (Raw Pretty-print 버전)
param([string]$ProjectRoot)

if (-not $ProjectRoot) {
    $ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName
}

$env:PYTHONUTF8 = "1"
$env:DRY_RUN = "1"
$venvPy = Join-Path $ProjectRoot "_sys\env\venv\Scripts\python.exe"
$hub    = Join-Path $ProjectRoot "_sys\core\hub.py"

$pass = 0; $fail = 0

function Test-Case($name, $block) {
    try { & $block; Write-Host "[PASS] $name" -ForegroundColor Green; $script:pass++ }
    catch { Write-Host "[FAIL] $name : $_" -ForegroundColor Red; $script:fail++ }
}

$tmpDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "session-test-$(Get-Random)")
New-Item -ItemType Directory -Path (Join-Path $tmpDir ".git") | Out-Null
$origLocation = Get-Location
Set-Location $tmpDir

try {
    Test-Case "session init + update + end" {
        & $venvPy $hub init-session --agent claude | Out-Null
        & $venvPy $hub update-status --mission "Session 1 task" --phase "1" | Out-Null
        & $venvPy $hub end-session --agent claude | Out-Null
        $state = Get-Content (Join-Path $tmpDir ".ai\state.json") | ConvertFrom-Json
        if ($null -ne $state.claude_sid) { throw "claude_sid should be null after end-session" }
    }

    Test-Case "init-session outputs SID only (bat-capture compatible)" {
        $sid = (& $venvPy $hub init-session --agent claude 2>&1) -join ""
        # SID는 5자 (prefix + 4 hex)
        if ($sid.Length -ne 5) { throw "Expected 5-char SID, got '$sid' (len=$($sid.Length))" }
        if ($sid -notmatch "^c[0-9a-f]{4}$") { throw "SID format wrong: '$sid'" }
    }

    Test-Case "status shows session info and mission" {
        & $venvPy $hub update-status --mission "Persistent task" | Out-Null
        $out = (& $venvPy $hub status 2>&1) -join "`n"
        if ($out -notmatch "SESSION STATUS") { throw "Missing SESSION STATUS header, got: $out" }
        if ($out -notmatch "Persistent task") { throw "Mission not in status, got: $out" }
    }

    Test-Case "mission persists across sessions" {
        & $venvPy $hub end-session --agent claude | Out-Null
        & $venvPy $hub init-session --agent claude | Out-Null
        $out = (& $venvPy $hub status 2>&1) -join "`n"
        if ($out -notmatch "Persistent task") { throw "Mission not persisted: $out" }
    }

    Test-Case "cross-project isolation" {
        $otherDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "other-$(Get-Random)")
        New-Item -ItemType Directory -Path (Join-Path $otherDir ".git") | Out-Null
        Push-Location $otherDir
        try {
            & $venvPy $hub init-session --agent claude | Out-Null
            if (-not (Test-Path (Join-Path $otherDir ".ai"))) { throw ".ai/ not in other project" }
            $state1 = (Get-Content (Join-Path $tmpDir ".ai\state.json") | ConvertFrom-Json).pair
            $state2 = (Get-Content (Join-Path $otherDir ".ai\state.json") | ConvertFrom-Json).pair
            if ($state1 -eq $state2) { throw "Sessions should be isolated between projects" }
        } finally {
            Pop-Location
            Remove-Item $otherDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    Test-Case "check-gate passes when gemini ON" {
        $statusFile = Join-Path $ProjectRoot "_sys\gemini\status.json"
        if (Test-Path $statusFile) {
            $mode = (Get-Content $statusFile | ConvertFrom-Json).mode
            if ($mode -eq "ON") {
                $gateBat = Join-Path $ProjectRoot "_sys\hooks\check-gate.bat"
                Set-Location $tmpDir
                cmd /c "`"$gateBat`"" | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "check-gate returned $LASTEXITCODE (expected 0)" }
            }
        }
    }

} finally {
    Set-Location $origLocation
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Results: $pass passed, $fail failed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
if ($fail -gt 0) { exit 1 }
