# test_tools_path.ps1 - venv Python + ripgrep/fd PATH 검증
param([string]$ProjectRoot)

# ProjectRoot 자동 탐지 (파라미터 미제공 시)
if (-not $ProjectRoot) {
    $ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName
}

$env:PYTHONUTF8 = "1"
$pass = 0; $fail = 0

function Test-Case($name, $block) {
    try { & $block; Write-Host "[PASS] $name" -ForegroundColor Green; $script:pass++ }
    catch { Write-Host "[FAIL] $name : $_" -ForegroundColor Red; $script:fail++ }
}

$venvPy = Join-Path $ProjectRoot "_sys\env\venv\Scripts\python.exe"
$hub    = Join-Path $ProjectRoot "_sys\core\hub.py"
$rg     = Join-Path $ProjectRoot "_sys\tools\ripgrep\rg.exe"
$fd     = Join-Path $ProjectRoot "_sys\tools\fd\fd.exe"
$claBat = Join-Path $ProjectRoot "_sys\cli\cla.bat"
$cliBat = Join-Path $ProjectRoot "_sys\cli"

Test-Case "venv python exists" {
    if (-not (Test-Path $venvPy)) { throw "Not found: $venvPy" }
}

Test-Case "filelock importable" {
    $out = & $venvPy -c "import filelock; print(filelock.__version__)" 2>&1
    if ($out -notmatch "\d+\.\d+") { throw "filelock not importable: $out" }
}

Test-Case "hub.py importable" {
    $tmpDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "hub-path-$(Get-Random)")
    Push-Location $tmpDir
    try {
        $out = & $venvPy $hub status 2>&1
        if ($LASTEXITCODE -gt 1) { throw "hub.py status failed: $out" }
    } finally {
        Pop-Location
        Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Test-Case "ripgrep exists" {
    if (-not (Test-Path $rg)) { throw "Not found: $rg" }
}

Test-Case "fd exists" {
    if (-not (Test-Path $fd)) { throw "Not found: $fd" }
}

Test-Case "PORTABLE_ROOT in cla.bat" {
    $content = Get-Content $claBat -Raw
    if ($content -notmatch 'PORTABLE_ROOT') { throw "PORTABLE_ROOT not in cla.bat" }
}

Test-Case "no hardcoded P:\\ in cli/*.bat" {
    Get-ChildItem (Join-Path $cliBat "*.bat") | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        $nonComment = ($content -split "`n" | Where-Object { $_ -notmatch "^::" }) -join "`n"
        if ($nonComment -match 'P:\\\\') { throw "Hardcoded P:\\ in $($_.Name)" }
    }
}

Test-Case "msg.bat basic call" {
    $tmpDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "msg-path-$(Get-Random)")
    Push-Location $tmpDir
    try {
        $msgBat = Join-Path $ProjectRoot "_sys\cli\msg.bat"
        $out = cmd /c "`"$msgBat`" status" 2>&1
        if ($LASTEXITCODE -gt 1) { throw "msg.bat exit $LASTEXITCODE : $out" }
    } finally {
        Pop-Location
        Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Results: $pass passed, $fail failed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
if ($fail -gt 0) { exit 1 }
