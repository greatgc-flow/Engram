@echo off
:: gem.bat — Gemini 세션 진입점
:: init-session → SID 캡처, status → 현재 상태 pretty-print, gemini --resume 실행
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\nodejs\npm-global;%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"
FOR /F "tokens=*" %%I IN ('python "%~dp0..\core\hub.py" init-session --agent gemini') DO SET "_SID=%%I"
python "%~dp0..\core\hub.py" status
gemini --resume %_SID%
