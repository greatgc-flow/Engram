@echo off
cd /d "%~dp0"
setlocal DisableDelayedExpansion
set "PY_EXE=_sys\env\python\python.exe"
if not exist "%PY_EXE%" (
    echo [Error] Python runtime not found at _sys\env\python\python.exe.
    echo Please run INSTALL.bat first to bootstrap the environment.
    exit /b 1
)
call "_sys\core\dispatch.bat" status %*
exit /b %errorlevel%
