@echo off
echo ========================================================
echo [WSB] Portable Dev MECE Testing Environment Started
echo ========================================================

:: %SYSTEMDRIVE%\PortableDev is Read-Only host mount.
:: %SYSTEMDRIVE%\TestResults is Writable host mount.
set "SRC=%SYSTEMDRIVE%\PortableDev"
set "TGT=%SYSTEMDRIVE%\TargetEnv"
set "RES=%SYSTEMDRIVE%\TestResults"

echo [WSB] 1. Cloning SCRIPTS ONLY...
:: Exclude binaries to test a fresh install
robocopy "%SRC%" "%TGT%" /MIR /XD env tools .git _archive workspace node_modules pip-cache npm-cache > "%RES%\robocopy_log.txt"

echo [WSB] 2. Bootstrapping Environment via install.bat...
set "CI=1"
cd /d "%TGT%"
:: Execute install and redirect output simply
call install.bat --skip-vscode --skip-claude > "%RES%\install_log.txt" 2>&1

if errorlevel 1 (
    echo [WSB] Setup/Bootstrap FAILED. >> "%RES%\summary.txt"
    goto :done
)
echo [WSB] Setup/Bootstrap PASSED. >> "%RES%\summary.txt"

echo [WSB] 2b. Unblocking downloaded binaries (Device Guard workaround)...
powershell -NoProfile -Command "Get-ChildItem '%TGT%\_sys\env' -Recurse | Unblock-File -ErrorAction SilentlyContinue" >> "%RES%\install_log.txt" 2>&1
echo [WSB] Unblock complete. >> "%RES%\summary.txt"

echo [WSB] 3. Running Core pytest Suite...
set "PYTHONUTF8=1"
set "VENV_PY=%TGT%\_sys\env\venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [WSB] Pytest SKIPPED - venv not found. >> "%RES%\summary.txt"
    goto :lifecycle
)
"%VENV_PY%" -m pytest "%TGT%\_sys\tests\unit" -v > "%RES%\pytest_report.txt" 2>&1
if errorlevel 1 (
    echo [WSB] Pytest FAILED. >> "%RES%\summary.txt"
) else (
    echo [WSB] Pytest PASSED. >> "%RES%\summary.txt"
)

:lifecycle
echo [WSB] 4. Running Lifecycle/ZeroBase MECE Tests...
set "LOCAL_PY=%TGT%\_sys\env\python\python.exe"
if not exist "%LOCAL_PY%" (
    echo [WSB] Lifecycle SKIPPED - Python not found. >> "%RES%\summary.txt"
    goto :done
)
"%LOCAL_PY%" "%TGT%\_sys\tests\lifecycle_tester.py" "%TGT%" > "%RES%\lifecycle_report.txt" 2>&1
if errorlevel 1 (
    echo [WSB] Lifecycle Tests FAILED. >> "%RES%\summary.txt"
) else (
    echo [WSB] Lifecycle Tests PASSED. >> "%RES%\summary.txt"
)

:done
echo [WSB] Testing Complete. Sending result signal.
echo WSB_DONE > "%RES%\result.txt"
:: Wait a few seconds to let file write finish
timeout /t 5 > nul
shutdown /s /t 5
