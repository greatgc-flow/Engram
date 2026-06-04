@echo off
set "SYS_DIR=%~dp0.."
set "PYTHONUTF8=1"
"%SYS_DIR%\env\venv\Scripts\python.exe" "%~dp0check_versions.py" %*
