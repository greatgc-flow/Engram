# ================================================================
# cleanup.ps1  -  Portable Dev Environment Space Optimizer
#
# Location : [PortableDev]\_sys\cleanup.ps1
#
# 기본 정리 (Default): 임시파일, 캐시, 오래된 로그만 삭제
#   → 프로그램/환경은 그대로 유지
#
# 하드 클린 (-Hard): 기본 정리 + 설치 아카이브, venv 삭제
#   → 재설치 필요: setup.ps1 -Force, start.bat 재실행
#
# 모든 항목은 재생성/재설치 가능 (데이터 손실 없음)
#
# 사용:
#   .\cleanup.ps1              기본 정리 (대화형)
#   .\cleanup.ps1 -All         기본 정리 전체 (확인 없이)
#   .\cleanup.ps1 -Hard        하드 클린 (대화형)
#   .\cleanup.ps1 -Hard -All   하드 클린 전체 (확인 없이)
#   .\cleanup.ps1 -WhatIf      미리보기만 (삭제 안 함)
# ================================================================

param(
    [switch]$Hard,           # Tier 2: 기본 정리 + 설치 아카이브 + venv
    [switch]$Reset,          # Tier 3: Tier 2 + 모든 런타임(_sys\env) 및 도구(_sys\tools)
    [switch]$ZeroBase,       # Tier 4: Tier 3 + workspace + _archive + 문서 (완전 초기화)
    [switch]$All,            # 모든 항목 확인 없이 실행 (ZeroBase 제외)
    [switch]$WhatIf,         # 미리보기 모드
    [int]$KeepLogs = 5,      # 보존할 최근 로그 수
    [int]$KeepWorkspace = 2  # 보존할 최근 _workspace_* 백업 수
)

$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SYS_DIR   = $PSScriptRoot
$BASE_DIR  = (Get-Item (Join-Path $SYS_DIR "..")).FullName
$ENV_DIR   = "$SYS_DIR\env"
$DATA_DIR  = "$SYS_DIR\data"
$TOOLS_DIR = "$SYS_DIR\tools"
$totalFreed = 0

# ── Helpers ────────────────────────────────────────────────────
function Get-DirSize($path) {
    if (-not (Test-Path -LiteralPath $path)) { return 0 }
    $size = 0
    Get-ChildItem -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue | 
        ForEach-Object { if ($_.Length) { $size += $_.Length } }
    return $size
}

function Format-Size($bytes) {
    if ($null -eq $bytes -or $bytes -eq 0) { return "0 B" }
    if ($bytes -ge 1GB) { return "{0:N2} GB" -f ($bytes / 1GB) }
    if ($bytes -ge 1MB) { return "{0:N2} MB" -f ($bytes / 1MB) }
    if ($bytes -ge 1KB) { return "{0:N2} KB" -f ($bytes / 1KB) }
    return "$bytes B"
}

function Confirm-Step($label, $hint, $isDestructive = $false) {
    if ($All -and -not $isDestructive) { return $true }
    $color = if ($isDestructive) { "Red" } else { "Cyan" }
    Write-Host "`n  [?] $label ($hint)" -ForegroundColor $color
    $ans = Read-Host "      계속할까요? [y/N]"
    return ($ans -match "^[Yy]")
}

function Remove-PathSafe($path, $label) {
    if (-not (Test-Path -LiteralPath $path)) { return 0 }
    $size = Get-DirSize $path
    if ($WhatIf) {
        Write-Host "  [Wait] $label — $(Format-Size $size) 삭제 예정" -ForegroundColor Yellow
        return $size
    }
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] $label — $(Format-Size $size) 삭제됨" -ForegroundColor Green
    return $size
}

# ── Header ─────────────────────────────────────────────────────
$modeName = "Light (기본)"
$modeColor = "Cyan"
if ($ZeroBase) { $modeName = "ZeroBase (완전 초기화)"; $modeColor = "Red" }
elseif ($Reset) { $modeName = "Reset (환경 초기화)"; $modeColor = "Magenta" }
elseif ($Hard) { $modeName = "Hard (공간 최적화)"; $modeColor = "Yellow" }

Write-Host "`n=====================================================" -ForegroundColor $modeColor
Write-Host "  Portable Dev Cleanup — $modeName" -ForegroundColor $modeColor
if ($WhatIf) { Write-Host "  ※ 미리보기 모드 — 실제 삭제 안 함" -ForegroundColor Gray }
Write-Host "=====================================================" -ForegroundColor $modeColor

# ── Tier 1: Light Cleanup (Default) ───────────────────────────
Write-Host "`n[Tier 1] 가벼운 정리 (안전)" -ForegroundColor Cyan

# 1. Temp Files
$totalFreed += Remove-PathSafe "$DATA_DIR\temp" "임시 파일 (_sys\data\temp)"

# 2. Caches
$totalFreed += Remove-PathSafe "$ENV_DIR\python\pip-cache" "pip 캐시"
$totalFreed += Remove-PathSafe "$ENV_DIR\nodejs\npm-cache" "npm 캐시"

# 3. Logs (Keep N)
$logPath = "$DATA_DIR\logs"
if (Test-Path $logPath) {
    $logs = Get-ChildItem $logPath -File | Sort-Object LastWriteTime -Descending
    $toDel = $logs | Select-Object -Skip $KeepLogs
    if ($toDel) {
        $delSz = ($toDel | Measure-Object -Property Length -Sum).Sum
        if (-not $WhatIf) { $toDel | Remove-Item -Force }
        Write-Host "  [OK] 오래된 로그 — $($toDel.Count)개 삭제 ($(Format-Size $delSz))" -ForegroundColor Green
        $totalFreed += $delSz
    }
}

# 4. Workspace Backups (Keep N)
$wsBacks = Get-ChildItem $BASE_DIR -Directory | Where-Object { $_.Name -match '^_workspace_\d{8}_\d{6}$' } | Sort-Object Name -Descending
$wsToDel = $wsBacks | Select-Object -Skip $KeepWorkspace
foreach ($ws in $wsToDel) {
    $totalFreed += Remove-PathSafe $ws.FullName "이전 워크스페이스 백업 ($($ws.Name))"
}

# ── Tier 2: Hard Cleanup (Archives & Venv) ────────────────────
if ($Hard -or $Reset -or $ZeroBase) {
    Write-Host "`n[Tier 2] 환경 정리 (재설치 필요 항목)" -ForegroundColor Yellow
    $totalFreed += Remove-PathSafe "$DATA_DIR\setup-files" "설치 아카이브 (zip/exe)"
    $totalFreed += Remove-PathSafe "$ENV_DIR\venv" "Python 가상환경 (venv)"
}

# ── Tier 3: Reset (Runtimes & Config) ─────────────────────────
if ($Reset -or $ZeroBase) {
    if (Confirm-Step "환경 리셋" "런타임(Python, Node 등) 및 설정 삭제" ($Reset -and -not $ZeroBase)) {
        Write-Host "`n[Tier 3] 런타임 리셋 (전체 재설치 필요)" -ForegroundColor Magenta
        $totalFreed += Remove-PathSafe "$ENV_DIR" "Portable Runtimes (_sys\env)"
        $totalFreed += Remove-PathSafe "$TOOLS_DIR" "Portable Tools (_sys\tools)"
        $totalFreed += Remove-PathSafe "$SYS_DIR\claude" "Claude Config (_sys\claude)"
        $totalFreed += Remove-PathSafe "$SYS_DIR\gemini\config" "Gemini Config (_sys\gemini\config)"
        if (Test-Path "$SYS_DIR\gemini\status.json") { Remove-Item "$SYS_DIR\gemini\status.json" -Force }
    }
}

# ── Tier 4: ZeroBase (Total Wipe) ──────────────────────────────
if ($ZeroBase) {
    Write-Host "`n[Tier 4] 제로베이스 초기화 (데이터 포함 전체 삭제)" -ForegroundColor Red
    if (Confirm-Step "최종 경고: ZeroBase" "워크스페이스 및 모든 데이터가 영구 삭제됩니다!" $true) {
        # Workspace
        $totalFreed += Remove-PathSafe "$BASE_DIR\workspace" "워크스페이스 데이터"
        $totalFreed += Remove-PathSafe "$BASE_DIR\_archive" "전체 아카이브/로그"
        
        # Root Documentation & Metadata
        Get-ChildItem $BASE_DIR -File | Where-Object { 
            $_.Name -match '\.md$' -or $_.Name -eq 'CONVENTION.md' -or $_.Name -eq 'PROGRESS.md'
        } | ForEach-Object {
            $totalFreed += $_.Length
            if (-not $WhatIf) { Remove-Item $_.FullName -Force }
            Write-Host "  [OK] 문서 삭제 — $($_.Name)" -ForegroundColor Green
        }

        # Orphaned config
        if (Test-Path "$SYS_DIR\local.config.bat") { Remove-Item "$SYS_DIR\local.config.bat" -Force }
    }
}

# ── Summary ────────────────────────────────────────────────────
Write-Host "`n=====================================================" -ForegroundColor $modeColor
if ($WhatIf) {
    Write-Host "  미리보기 결과: 총 $(Format-Size $totalFreed) 확보 예정" -ForegroundColor Yellow
} else {
    Write-Host "  정리 완료: 총 $(Format-Size $totalFreed) 확보됨" -ForegroundColor Green
    if ($Reset -or $ZeroBase) {
        Write-Host "  시스템이 초기화되었습니다. INSTALL.bat를 실행하여 재설정하세요." -ForegroundColor White
    }
}
Write-Host "=====================================================" -ForegroundColor $modeColor
Write-Host ""

if ($Host.Name -eq "ConsoleHost" -and -not $All) { Read-Host "종료하려면 Enter를 누르세요" }
