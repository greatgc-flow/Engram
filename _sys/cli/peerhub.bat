@echo off
setlocal
set "PORTABLE_ROOT=%~dp0..\.."
if not exist "%PORTABLE_ROOT%\_sys\env\venv\Scripts\python.exe" (
    set "PORTABLE_ROOT=P:"
)
set "PYTHON_EXE=%PORTABLE_ROOT%\_sys\env\venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python.exe"
)

set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PORTABLE_ROOT%\_sys\env\nodejs;%PORTABLE_ROOT%\_sys\env\nodejs\npm-global;%PORTABLE_ROOT%\_sys\env\git\usr\bin;%PORTABLE_ROOT%\_sys\env\git\bin;%PATH%"

"%PYTHON_EXE%" -m peerhub.cli %*
exit /b %ERRORLEVEL%
