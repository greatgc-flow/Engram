@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
"%PORTABLE_ROOT%\_sys\env\venv\Scripts\python.exe" "%~dp0..\core\hub.py" append-log %*
