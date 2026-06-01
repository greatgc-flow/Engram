@echo off
setlocal

:: ================================================================
:: script-deps.bat  -  Map CALL/INVOKE relationships in _sys/ scripts
::
:: Usage: script-deps        (run from sandbox terminal)
::
:: Requires: gemini CLI (GEMINI_MODE=ON)
:: Output:   _archive\script-deps.json
::
:: Note: --include-files was removed in newer Gemini CLI builds.
::       Files are merged into a single temp file via PowerShell
::       and piped to gemini via stdin (type file | gemini -p ...).
:: ================================================================

:: --- Resolve BASE_DIR ---
if defined BASE_DIR (
    set "_BASE=%BASE_DIR%"
) else (
    for %%I in ("%~dp0..\..") do set "_BASE=%%~fI"
)

set "SYS_DIR=%_BASE%\_sys"
set "CTX_DIR=%SYS_DIR%\context"
set "GEM_DIR=%SYS_DIR%\gemini"
set "OUT_DIR=%_BASE%\_archive"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
set "OUT_FILE=%OUT_DIR%\script-deps.json"
set "TEMP_MERGED=%TEMP%\script_deps_merged_%RANDOM%.txt"

:: --- Timestamp ---
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"

:: --- Check Gemini mode ---
call "%~dp0gemini-mode-check.bat"
if not "%GEMINI_MODE%"=="ON" (
    echo [script-deps] ERROR: Gemini not available. Reason: %GEMINI_OFF_REASON%
    echo               Run start.bat first, or check _sys\gemini\status.json
    exit /b 1
)

:: --- Merge target scripts into single temp file ---
echo [script-deps] Merging script files for analysis...
powershell -NoProfile -Command ^
    "$base='%SYS_DIR:\=\\%'; $ctx='%CTX_DIR:\=\\%'; $gem='%GEM_DIR:\=\\%'; $root='%_BASE:\=\\%';" ^
    "$targets = @(" ^
    "  [pscustomobject]@{ path=Join-Path $root 'start.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $ctx 'ctx-save.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $ctx 'ctx-end.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $ctx 'version-check.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $ctx 'agent-audit.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $ctx 'script-deps.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $ctx 'git-draft.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $gem 'gemini-status.bat' }," ^
    "  [pscustomobject]@{ path=Join-Path $base 'manage.ps1' }," ^
    "  [pscustomobject]@{ path=Join-Path $base 'launch.ps1' }," ^
    "  [pscustomobject]@{ path=Join-Path $root 'setup.ps1' }," ^
    "  [pscustomobject]@{ path=Join-Path $root 'cleanup.ps1' }" ^
    ");" ^
    "$out='%TEMP_MERGED:\=\\%'; $count=0;" ^
    "$merged = foreach ($t in $targets) { if (Test-Path $t.path) { $count++; '=== ' + (Split-Path $t.path -Leaf) + ' ==='; Get-Content $t.path -Raw } };" ^
    "[System.IO.File]::WriteAllText($out, ($merged -join \"`n\"), (New-Object System.Text.UTF8Encoding($false)));" ^
    "Write-Host ('[script-deps] Merged ' + $count + ' script files.')"
if errorlevel 1 (
    echo [script-deps] ERROR: Failed to merge script files.
    exit /b 1
)

:: --- Run Gemini dependency analysis ---
echo [script-deps] Analyzing CALL/INVOKE relationships via Gemini...

type "%TEMP_MERGED%" | gemini -p "Analyze the provided scripts and map all CALL/INVOKE relationships. Return ONLY valid JSON: {\"scan_ts\":\"%_DT%\",\"nodes\":[{\"file\":\"\",\"type\":\"bat or ps1\"}],\"edges\":[{\"caller\":\"\",\"callee\":\"\",\"method\":\"call or invoke or start\"}]}" -o text -y > "%OUT_FILE%" 2>&1

if errorlevel 1 (
    echo [script-deps] ERROR: gemini returned non-zero. Check auth or network.
    del "%OUT_FILE%" > nul 2>&1
    del "%TEMP_MERGED%" > nul 2>&1
    call "%~dp0collab-log-append.bat" "Axis-F" "script-deps.bat" "FAIL" "Error: api_error"
    if defined GEMINI_DIR (
        powershell -NoProfile -Command "$f='%GEMINI_DIR%\status.json'; if (Test-Path $f) { $j=Get-Content $f -Raw | ConvertFrom-Json; $j.last_error='script_deps_failed_%_DT%'; $j.mode='OFF'; $j.reason='api_error'; [System.IO.File]::WriteAllText($f, ($j | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false))) }"
    )
    exit /b 1
)

:: Check for Gemini refusal in output
findstr /i "\[REFUSAL:" "%OUT_FILE%" > nul 2>&1
if not errorlevel 1 (
    call "%~dp0collab-log-append.bat" "Axis-F" "script-deps.bat" "REFUSED" "Gemini refused request"
    del "%OUT_FILE%" > nul 2>&1
    del "%TEMP_MERGED%" > nul 2>&1
    exit /b 1
)

call "%~dp0raw-log.bat" "Axis-F" "%OUT_FILE%" "%TEMP_MERGED%"
del "%TEMP_MERGED%" > nul 2>&1

echo [script-deps] Done: %OUT_FILE%
echo [script-deps] Review edges for unexpected or missing call chains.
call "%~dp0collab-log-append.bat" "Axis-F" "script-deps.bat" "OK" "Output: %OUT_FILE%"
endlocal
