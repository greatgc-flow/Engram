@echo off
set "_FAIL=0"
echo ========================================================
echo [WSB] Portable Dev MECE Testing Environment Started
echo ========================================================

:: %SYSTEMDRIVE%\PortableDev is Read-Only host mount.
:: %SYSTEMDRIVE%\TestResults is Writable host mount.
set "SRC=%SYSTEMDRIVE%\PortableDev"
set "TGT=%SYSTEMDRIVE%\TargetEnv"
set "RES=%SYSTEMDRIVE%\TestResults"

echo [WSB] 1. Cloning SCRIPTS ONLY...
:: Exclude installed binaries and mutable state to test a fresh install. Keep the
:: root tools/ source tree because package/manifest tests import its builders;
:: only _sys/tools contains installed runtime binaries.
robocopy "%SRC%" "%TGT%" /MIR /XD "%SRC%\_sys\env" "%SRC%\_sys\tools" "%SRC%\.git" "%SRC%\_archive" "%SRC%\workspace" node_modules pip-cache npm-cache > "%RES%\robocopy_log.txt"

echo [WSB] 2. Bootstrapping Environment via _sys\core\bootstrap.bat...
set "CI=1"
cd /d "%TGT%"
:: Execute install and redirect output simply
call _sys\core\bootstrap.bat --skip-vscode --skip-claude > "%RES%\install_log.txt" 2>&1

if errorlevel 1 (
    echo [WSB] Setup/Bootstrap FAILED. >> "%RES%\summary.txt"
    set "_FAIL=1"
    goto :done
)
echo [WSB] Setup/Bootstrap PASSED. >> "%RES%\summary.txt"

echo [WSB] 2b. Unblocking downloaded binaries (Device Guard workaround)...
powershell -NoProfile -Command "Get-ChildItem '%TGT%\_sys\env' -Recurse | Unblock-File -ErrorAction SilentlyContinue" >> "%RES%\install_log.txt" 2>&1
echo [WSB] Unblock complete. >> "%RES%\summary.txt"

echo [WSB] 3. Installing source-only test dependencies...
set "PYTHONUTF8=1"
set "VENV_PY=%TGT%\_sys\env\venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [WSB] Test setup FAILED - venv not found. >> "%RES%\summary.txt"
    set "_FAIL=1"
    goto :done
)
"%VENV_PY%" -m pip install -r "%TGT%\requirements-dev.txt" >> "%RES%\install_log.txt" 2>&1
if errorlevel 1 (
    echo [WSB] Test dependency install FAILED. >> "%RES%\summary.txt"
    set "_FAIL=1"
    goto :done
)

echo [WSB] 4. Running unit, lifecycle, and path suites...
"%VENV_PY%" -m pytest "%TGT%\_sys\tests\unit" -v > "%RES%\pytest_report.txt" 2>&1
if errorlevel 1 (
    echo [WSB] Pytest FAILED. >> "%RES%\summary.txt"
    set "_FAIL=1"
) else (
    echo [WSB] Pytest PASSED. >> "%RES%\summary.txt"
)

echo [WSB] 5. Running real installed-runtime health check...
call "%TGT%\engram.cmd" doctor --json > "%RES%\doctor_report.txt" 2>&1
if errorlevel 1 (
    echo [WSB] Doctor FAILED. >> "%RES%\summary.txt"
    set "_FAIL=1"
) else (
    echo [WSB] Doctor PASSED. >> "%RES%\summary.txt"
)

echo [WSB] 6. Running opt-in real network discovery check...
call "%TGT%\engram.cmd" update --check --refresh > "%RES%\update_check_report.txt" 2>&1
if errorlevel 1 (
    echo [WSB] Network update check reported one or more unavailable components. >> "%RES%\summary.txt"
    set "_FAIL=1"
) else (
    echo [WSB] Network update check PASSED. >> "%RES%\summary.txt"
)

:done
echo [WSB] Testing Complete. Sending result signal.
if "%_FAIL%"=="0" (
    echo PASS> "%RES%\result.txt"
) else (
    echo FAIL> "%RES%\result.txt"
)
:: Wait a few seconds to let file write finish
timeout /t 5 > nul
shutdown /s /t 5
