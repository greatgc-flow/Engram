@echo off
:: ================================================================
:: run-sandbox-test.bat  -  Launch Engram Windows Sandbox test
::
:: Generates a path-correct .wsb from the template, then launches
:: Windows Sandbox. Requires: Windows 11 Pro/Enterprise/Education,
:: Windows Sandbox feature enabled (optionalfeatures.exe).
::
:: Results: _archive\test-results\test_YYYYMMDD_HHMMSS.txt
:: ================================================================

:: --- Resolve the repository root from this script's own location ---
set "SYS_PHYS=%~dp0"
if "%SYS_PHYS:~-1%"=="\" set "SYS_PHYS=%SYS_PHYS:~0,-1%"
for %%I in ("%SYS_PHYS%\..\..") do set "BASE_PHYS=%%~fI"

:: Allow a machine-local physical-path override for unusual mount layouts.
if exist "%~dp0..\local.config.bat" (
    call "%~dp0..\local.config.bat"
    if defined BASE_DIR_PHYS set "BASE_PHYS=%BASE_DIR_PHYS%"
)

set "TEMPLATE=%~dp0sandbox-unit-test.wsb"
:: Use %SystemRoot%\Temp so the generated configuration is host-local.
set "GENERATED=%SystemRoot%\Temp\porta_sandbox_test_%RANDOM%.wsb"
set "RESULTS_DIR=%BASE_PHYS%\_archive\test-results"
set "RESULT_FILE=%RESULTS_DIR%\result.txt"

echo [sandbox-test] Physical base: %BASE_PHYS%
echo [sandbox-test] Results dir  : %RESULTS_DIR%

if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"
for %%F in (result.txt summary.txt robocopy_log.txt install_log.txt pytest_report.txt doctor_report.txt update_check_report.txt) do (
    if exist "%RESULTS_DIR%\%%F" del "%RESULTS_DIR%\%%F"
)

:: --- Generate .wsb with real path ---
:: BASE_PHYS is used without \=\\ escaping so the XML contains valid single-backslash paths.
powershell -NoProfile -Command ^
    "$t = Get-Content '%TEMPLATE:\=\\%' -Raw;" ^
    "$t = $t.Replace('__PORTABLE_ROOT__', '%BASE_PHYS%');" ^
    "[System.IO.File]::WriteAllText('%GENERATED:\=\\%', $t, (New-Object System.Text.UTF8Encoding($false)));" ^
    "Write-Host '[sandbox-test] WSB generated: %GENERATED%'"

if errorlevel 1 (
    echo [sandbox-test] ERROR: Failed to generate .wsb file.
    exit /b 1
)

:: --- Check Windows Sandbox is available ---
where WindowsSandbox.exe > nul 2>&1
if errorlevel 1 (
    echo [sandbox-test] ERROR: Windows Sandbox not found.
    echo                Enable: optionalfeatures.exe ^> "Windows Sandbox"
    del "%GENERATED%" > nul 2>&1
    exit /b 1
)

echo [sandbox-test] Launching Windows Sandbox...
echo [sandbox-test] Watch for test results in: %RESULTS_DIR%
start "" "%GENERATED%"

:: Wait for Sandbox to open the WSB file before deleting it.
:: Use PowerShell sleep instead of timeout (timeout fails in some caller contexts).
powershell -NoProfile -Command "Start-Sleep 15"
del "%GENERATED%" > nul 2>&1

echo [sandbox-test] Waiting for completion (timeout: 30 minutes)...
for /l %%N in (1,1,360) do (
    if exist "%RESULT_FILE%" goto :result_ready
    ping 127.0.0.1 -n 6 > nul
)
echo [sandbox-test] ERROR: Timed out waiting for %RESULT_FILE%
exit /b 1

:result_ready
type "%RESULT_FILE%"
findstr /x /c:"PASS" "%RESULT_FILE%" > nul
if errorlevel 1 exit /b 1
exit /b 0
