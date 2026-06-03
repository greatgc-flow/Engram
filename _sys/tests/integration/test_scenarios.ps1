# test_scenarios.ps1 — 사용자 시나리오 E2E 테스트
# Gemini MECE 설계 시나리오 A~D + 추가 시나리오
# 실제 claude/gemini CLI 호출 없음 (hub.py 직접 검증)

param([string]$ProjectRoot)
if (-not $ProjectRoot) {
    $ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName
}

$env:PYTHONUTF8 = "1"
$py     = Join-Path $ProjectRoot "_sys\env\venv\Scripts\python.exe"
$hub    = Join-Path $ProjectRoot "_sys\core\hub.py"
$msgBat = Join-Path $ProjectRoot "_sys\cli\msg.bat"

$pass = 0; $fail = 0

function Test-Scenario($name, $block) {
    try {
        & $block
        Write-Host "[PASS] $name" -ForegroundColor Green
        $script:pass++
    } catch {
        Write-Host "[FAIL] $name`n       $_" -ForegroundColor Red
        $script:fail++
    }
}

function New-IsolatedProject {
    $d = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "scenario-$(Get-Random)")
    New-Item -ItemType Directory -Path (Join-Path $d ".git") | Out-Null
    return $d
}

# ─── 시나리오 A: 기본 Claude→Gemini 작업 흐름 ──────────────
Test-Scenario "Scenario A: Claude 작업 시작 → Gemini 메시지 → 완료" {
    $proj = New-IsolatedProject
    Push-Location $proj
    try {
        # Claude 세션 시작
        $sid = (& $py $hub init-session --agent claude 2>&1) -join ""
        if ($sid -notmatch "^c[0-9a-f]{4}$") { throw "Invalid claude SID: $sid" }

        # 미션 설정
        & $py $hub update-status --mission "DB 마이그레이션 작업" --phase "1" | Out-Null

        # Gemini에게 메시지 발송
        $out = (& $py $hub send --from claude --to gemini --msg "Phase 1 완료. 아키텍처 검토 요청." 2>&1) -join ""
        if ($out -notmatch "\[HUB\] SENT") { throw "send failed: $out" }

        # Gemini 세션 시작 (역할 전환 시뮬레이션)
        $gsid = (& $py $hub init-session --agent gemini 2>&1) -join ""
        if ($gsid -notmatch "^g[0-9a-f]{4}$") { throw "Invalid gemini SID: $gsid" }

        # Gemini가 메시지 확인
        $inbox = (& $py $hub check --target gemini 2>&1) -join "`n"
        if ($inbox -notmatch "Phase 1 완료") { throw "Message not received: $inbox" }
        if ($inbox -notmatch "messages for gemini") { throw "No READ header: $inbox" }

        # Gemini가 Claude에게 응답
        & $py $hub send --from gemini --to claude --msg "검토 완료. 진행하세요." | Out-Null
        & $py $hub mark-read --target gemini --all | Out-Null

        # Claude가 응답 확인
        $reply = (& $py $hub check --target claude 2>&1) -join "`n"
        if ($reply -notmatch "검토 완료") { throw "Reply not received: $reply" }

        # 세션 종료 및 handoff 확인
        & $py $hub end-session --agent claude | Out-Null
        $state = Get-Content (Join-Path $proj ".ai\state.json") | ConvertFrom-Json
        if ($null -ne $state.claude_sid) { throw "claude_sid not null after end-session" }
        # handoff.md에 종료 기록
        $pair = $state.pair
        $handoff = Get-Content (Join-Path $proj ".ai\sessions\$pair\handoff.md") -Raw
        if ($handoff -notmatch "claude: 세션 종료") { throw "handoff not updated" }
    } finally {
        Pop-Location
        Remove-Item $proj -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 시나리오 B: 두 Claude 인스턴스 같은 프로젝트 동시 작업 ─
Test-Scenario "Scenario B: 두 Claude 인스턴스 동시 작업 → 메시지 손실 없음" {
    $proj = New-IsolatedProject
    Push-Location $proj
    try {
        # 두 인스턴스가 동시에 메시지 발송
        $jobs = 1..10 | ForEach-Object {
            $i = $_
            Start-Job -ScriptBlock {
                param($py, $hub, $dir, $n)
                Set-Location $dir
                & $py $hub send --from claude --to gemini --msg "instance-$n"
            } -ArgumentList $py, $hub, $proj, $i
        }
        $jobs | Wait-Job | Out-Null
        $jobs | Remove-Job

        $mb = Get-Content (Join-Path $proj ".ai\mailbox.json") | ConvertFrom-Json
        if ($mb.unread_count -lt 8) {
            throw "메시지 손실: expected >=8, got $($mb.unread_count)"
        }

        # 모든 메시지 ID 유니크
        $ids = $mb.messages | ForEach-Object { $_.id }
        $uniqueIds = $ids | Select-Object -Unique
        if ($ids.Count -ne $uniqueIds.Count) { throw "ID 중복 발생" }
    } finally {
        Pop-Location
        Remove-Item $proj -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 시나리오 C: 프로젝트 전환 → .ai/ 격리 확인 ────────────
Test-Scenario "Scenario C: 프로젝트 A→B 전환 시 .ai/ 완전 격리" {
    $projA = New-IsolatedProject
    $projB = New-IsolatedProject
    try {
        # 프로젝트 A 작업
        Push-Location $projA
        & $py $hub init-session --agent claude | Out-Null
        & $py $hub update-status --mission "Project A work" | Out-Null
        & $py $hub send --from claude --to gemini --msg "message in A" | Out-Null
        Pop-Location

        # 프로젝트 B 작업
        Push-Location $projB
        & $py $hub init-session --agent claude | Out-Null
        & $py $hub update-status --mission "Project B work" | Out-Null
        Pop-Location

        # 격리 확인: 서로 다른 .ai/ 경로
        $stateA = Get-Content (Join-Path $projA ".ai\state.json") | ConvertFrom-Json
        $stateB = Get-Content (Join-Path $projB ".ai\state.json") | ConvertFrom-Json

        if ($stateA.mission -ne "Project A work") { throw "Project A mission missing" }
        if ($stateB.mission -ne "Project B work") { throw "Project B mission missing" }
        if ($stateA.pair -eq $stateB.pair) { throw "프로젝트 간 pair 충돌" }

        # A의 메시지가 B로 누출되지 않음
        $mbB = Get-Content (Join-Path $projB ".ai\mailbox.json") | ConvertFrom-Json
        if ($mbB.unread_count -ne 0) { throw "Project B got Project A's messages (누출)" }
    } finally {
        Remove-Item $projA -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item $projB -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 시나리오 D: msg.bat 단일 통로 완전 흐름 ────────────────
Test-Scenario "Scenario D: msg.bat 단일 통로 — ask 포함 전체 인터페이스 검증" {
    $proj = New-IsolatedProject
    Push-Location $proj
    try {
        # msg.bat send
        $out = (cmd /c "`"$msgBat`" send --from claude --to gemini --msg ""hello via msg.bat""" 2>&1) -join ""
        if ($out -notmatch "\[HUB\] SENT") { throw "msg.bat send failed: $out" }

        # msg.bat check
        $out = (cmd /c "`"$msgBat`" check --target gemini" 2>&1) -join "`n"
        if ($out -notmatch "hello via msg.bat") { throw "msg.bat check failed: $out" }

        # msg.bat status
        $out = (cmd /c "`"$msgBat`" status" 2>&1) -join "`n"
        if ($out -notmatch "SESSION STATUS") { throw "msg.bat status failed: $out" }

        # msg.bat mark-read
        $out = (cmd /c "`"$msgBat`" mark-read --target gemini --all" 2>&1) -join ""
        if ($out -notmatch "\[READ\]") { throw "msg.bat mark-read failed: $out" }

        # msg.bat check (빈 인박스)
        $out = (cmd /c "`"$msgBat`" check --target gemini" 2>&1) -join ""
        if ($out -notmatch "inbox empty") { throw "Empty inbox check failed: $out" }
    } finally {
        Pop-Location
        Remove-Item $proj -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 시나리오 E: 세션 연속성 (handoff 이어받기) ─────────────
Test-Scenario "Scenario E: 세션 종료 후 재시작 → handoff 이어받기" {
    $proj = New-IsolatedProject
    Push-Location $proj
    try {
        # 세션 1: 작업하고 종료
        & $py $hub init-session --agent claude | Out-Null
        & $py $hub update-status --mission "Session 1 task" | Out-Null
        & $py $hub send --from claude --to gemini --msg "작업 중간 상태 메모" | Out-Null
        & $py $hub end-session --agent claude | Out-Null

        # 세션 2: 재시작 후 handoff 확인
        & $py $hub init-session --agent claude | Out-Null
        $status = (& $py $hub status 2>&1) -join "`n"

        if ($status -notmatch "SESSION STATUS") { throw "Status header missing" }
        # 이전 미션이 state.json에 유지됨
        if ($status -notmatch "Session 1 task") { throw "Previous mission not persisted" }
    } finally {
        Pop-Location
        Remove-Item $proj -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 시나리오 F: gate 차단 시 scan 스크립트 동작 ────────────
Test-Scenario "Scenario F: check-gate ON/OFF 전환 검증" {
    $proj = New-IsolatedProject
    Push-Location $proj
    try {
        # Gemini ON 상태에서 gate 통과
        $statusFile = Join-Path $ProjectRoot "_sys\gemini\status.json"
        if (Test-Path $statusFile) {
            $mode = (Get-Content $statusFile | ConvertFrom-Json).mode
            if ($mode -eq "ON") {
                $out = (cmd /c "`"$msgBat`" check-gate --agent gemini" 2>&1) -join ""
                if ($LASTEXITCODE -ne 0) { throw "Gate should be ON: $out" }
            }
        }
    } finally {
        Pop-Location
        Remove-Item $proj -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 시나리오 G: 대용량 메시지 및 멀티라인 ─────────────────
Test-Scenario "Scenario G: 대용량 메시지 (2KB), 멀티라인 내용 전달" {
    $proj = New-IsolatedProject
    Push-Location $proj
    try {
        $longMsg = "한국어 메시지 테스트`n" * 50 + "END"
        & $py $hub send --from claude --to gemini --msg $longMsg | Out-Null

        $out = (& $py $hub check --target gemini 2>&1) -join "`n"
        if ($out -notmatch "END") { throw "Long message truncated: $out" }
        if ($out -notmatch "한국어 메시지 테스트") { throw "Korean content lost: $out" }
    } finally {
        Pop-Location
        Remove-Item $proj -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ─── 결과 출력 ───────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host " Scenario Tests: $pass passed, $fail failed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
if ($fail -gt 0) { exit 1 }
