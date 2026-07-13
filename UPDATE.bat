@echo off
setlocal enabledelayedexpansion

:: ======================================================================
:: UPDATE.bat  -  Discover and apply tool/runtime updates
:: ======================================================================

set "PY_EXE=%~dp0_sys\env\python\python.exe"
if not exist "%PY_EXE%" (
    echo [Error] Python runtime not found at _sys\env\python\python.exe.
    echo Please run INSTALL.bat first to bootstrap the environment.
    exit /b 1
)

call "%~dp0_sys\core\dispatch.bat" update %*
exit /b %errorlevel%
