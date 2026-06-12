@echo off
setlocal enabledelayedexpansion

:: Minimal Bootstrap environment
set "SYS_DIR=%~dp0.."
set "PY=%SYS_DIR%\env\python\python.exe"

:: If Python is missing, only allow 'install'
if not exist "%PY%" (
    if /i "%~1"=="install" (
        echo [i] Bootstrapping environment...
        :: INSTALL.bat logic will be triggered if we just call it
        :: but we want to avoid infinite loops.
        :: For now, we'll let the root INSTALL.bat handle the initial bootstrap.
        exit /b 0
    )
    echo [Error] Portable environment not initialized.
    echo Please run INSTALL.bat first.
    pause
    exit /b 1
)

:: Execute via dispatcher.py
set "PYTHONUTF8=1"
"%PY%" "%SYS_DIR%\core\dispatcher.py" %*
exit /b %errorlevel%
