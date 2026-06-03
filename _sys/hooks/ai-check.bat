@echo off
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"
python "%~dp0..\core\hub.py" check-gate --agent gemini
if errorlevel 1 (echo [gate] Gemini unavailable & exit /b 1)
