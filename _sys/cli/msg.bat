@echo off
:: msg.bat — AI 소통 단일 통로 (동기/비동기 모두)
::
:: 동기 (즉시 응답):
::   msg ask --to gemini --query "질문"
::   msg ask --to claude  --query "질문"
::
:: 비동기 (mailbox):
::   msg send --from claude --to gemini --msg "메모"
::   msg check --target gemini
::   msg mark-read --target gemini --all
::
:: 상태:
::   msg status
::   msg update-status --mission "작업명" --phase "2"
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PORTABLE_ROOT%\_sys\env\nodejs\npm-global;%PATH%"
python "%~dp0..\core\hub.py" %*
