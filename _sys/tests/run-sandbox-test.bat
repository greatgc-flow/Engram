@echo off
:: ================================================================
:: run-sandbox-test.bat  -  Launch Porta-Flow Windows Sandbox test
::
:: Generates a path-correct .wsb from the template, then launches
:: Windows Sandbox. Requires: Windows 11 Pro/Enterprise/Education,
:: Windows Sandbox feature enabled (optionalfeatures.exe).
::
:: Results: _archive\test-results\test_YYYYMMDD_HHMMSS.txt
:: ================================================================

:: --- Resolve physical base path (no SUBST) ---
set "SYS_PHYS=%~dp0"
if "%SYS_PHYS:~-1%"=="\" set "SYS_PHYS=%SYS_PHYS:~0,-1%"
for %%I in ("%SYS_PHYS%\..\..") do set "BASE_PHYS=%%~fI"

:: Windows Sandbox MappedFolders requires a real filesystem path, not a SUBST
:: virtual drive. Override with BASE_DIR_PHYS from local.config.bat if present.
if exist "%~dp0..\local.config.bat" (
    call "%~dp0..\local.config.bat"
    if defined BASE_DIR_PHYS set "BASE_PHYS=%BASE_DIR_PHYS%"
)

set "TEMPLATE=%~dp0sandbox-unit-test.wsb"
:: Use %SystemRoot%\Temp (always a real physical path) instead of %TEMP% which
:: may be redirected to a SUBST drive. Windows Sandbox cannot open files on
:: virtual drives when launching the sandbox process.
set "GENERATED=%SystemRoot%\Temp\porta_sandbox_test_%RANDOM%.wsb"
set "RESULTS_DIR=%BASE_PHYS%\_archive\test-results"

echo [sandbox-test] Physical base: %BASE_PHYS%
echo [sandbox-test] Results dir  : %RESULTS_DIR%

if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

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
