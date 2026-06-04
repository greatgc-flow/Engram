@echo off
set "SYS_DIR=%~dp0.."
set "PYTHONUTF8=1"
"%SYS_DIR%\env\venv\Scripts\python.exe" "%~dp0collab_log.py" %*
