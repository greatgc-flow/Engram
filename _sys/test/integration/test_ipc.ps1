# test_ipc.ps1 - msg.bat IPC 통합 테스트 (Raw Pretty-print 버전)

param([string]$ProjectRoot)
if (-not $ProjectRoot) {
    $ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName
}

$ErrorActionPreference = "Stop"
$pass = 0; $fail = 0

function Test-Case($name, $block) {
    try {
        & $block
        Write-Host "[PASS] $name" -ForegroundColor Green
        $script:pass++
    } catch {
        Write-Host "[FAIL] $name : $_" -ForegroundColor Red
        $script:fail++
    }
}

$env:PYTHONUTF8 = "1"
$venvPy = Join-Path $ProjectRoot "_sys\env\venv\Scripts\python.exe"
$hub    = Join-Path $ProjectRoot "_sys\core\hub.py"
$msgBat = Join-Path $ProjectRoot "_sys\cli\msg.bat"

$tmpDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "hub-test-$(Get-Random)")
New-Item -ItemType Directory -Path (Join-Path $tmpDir ".git") | Out-Null
$origLocation = Get-Location
Set-Location $tmpDir

try {
    & $venvPy $hub init-session --agent claude | Out-Null

    Test-Case "send message" {
        $out = (& $venvPy $hub send --from claude --to gemini --msg "integration test" 2>&1) -join " "
        if ($out -notmatch "\[SENT\]") { throw "Expected [SENT], got: $out" }
    }

    Test-Case "check — pretty-print 전문 출력" {
        $out = (& $venvPy $hub check --target gemini 2>&1) -join "`n"
        if ($out -notmatch "INBOX") { throw "Expected INBOX header, got: $out" }
        if ($out -notmatch "integration test") { throw "Expected message content, got: $out" }
    }

    Test-Case "mark-read all" {
        & $venvPy $hub mark-read --target gemini --all | Out-Null
        $out = (& $venvPy $hub check --target gemini 2>&1) -join " "
        if ($out -notmatch "새 메시지 없음") { throw "Expected empty inbox, got: $out" }
    }

    Test-Case "update-status + status pretty-print" {
        & $venvPy $hub update-status --mission "integration test running" --phase "8" | Out-Null
        $out = (& $venvPy $hub status 2>&1) -join "`n"
        if ($out -notmatch "SESSION STATUS") { throw "Expected SESSION STATUS header, got: $out" }
        if ($out -notmatch "integration test running") { throw "Mission not found in status, got: $out" }
    }

    Test-Case "end-session" {
        $out = (& $venvPy $hub end-session --agent claude 2>&1) -join " "
        if ($out -notmatch "\[END\]") { throw "Expected [END], got: $out" }
    }

    Test-Case "handoff.md exists after session" {
        $pair = (Get-Content (Join-Path $tmpDir ".ai\state.json") | ConvertFrom-Json).pair
        $handoff = Join-Path $tmpDir ".ai\sessions\$pair\handoff.md"
        if (-not (Test-Path $handoff)) { throw "handoff.md not found at $handoff" }
    }

    Test-Case "concurrent send (race condition)" {
        1..10 | ForEach-Object {
            Start-Job -ScriptBlock {
                param($py, $hub, $dir, $i)
                Set-Location $dir
                & $py $hub send --from claude --to gemini --msg "concurrent-$i"
            } -ArgumentList $venvPy, $hub, $tmpDir, $_ | Out-Null
        }
        Get-Job | Wait-Job | Out-Null
        Get-Job | Remove-Job
        $mb = Get-Content (Join-Path $tmpDir ".ai\mailbox.json") | ConvertFrom-Json
        if ($mb.unread_count -lt 8) { throw "Expected >=8 messages, got $($mb.unread_count)" }
    }

    Test-Case "msg.bat wrapper (send)" {
        $out = (cmd /c "`"$msgBat`" send --from gemini --to claude --msg ""hello from bat""" 2>&1) -join " "
        if ($out -notmatch "\[SENT\]") { throw "msg.bat failed: $out" }
    }

    Test-Case "msg.bat wrapper (status)" {
        $out = (cmd /c "`"$msgBat`" status" 2>&1) -join "`n"
        if ($out -notmatch "SESSION STATUS") { throw "msg.bat status failed: $out" }
    }

    Test-Case "venv python is used (not system python)" {
        $whichPy = (& $venvPy -c "import sys; print(sys.executable)" 2>&1) -join ""
        if ($whichPy -notmatch "venv") { throw "Expected venv python, got: $whichPy" }
    }

} finally {
    Set-Location $origLocation
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=============================" -ForegroundColor Cyan
Write-Host "Results: $pass passed, $fail failed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
if ($fail -gt 0) { exit 1 }
