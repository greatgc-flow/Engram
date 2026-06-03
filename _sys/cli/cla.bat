@echo off
:: cla.bat — Claude 세션 진입점
:: init-session → SID 발급 (표시 생략), status → 현재 상태 pretty-print, claude 실행
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PATH%"
python "%~dp0..\core\hub.py" init-session --agent claude > nul
python "%~dp0..\core\hub.py" status
claude
