@echo off
setlocal
:: msg.bat -- Single IPC channel for AI hub (sync + async)
::
:: Sync (immediate response):
::   msg ask --to gc --query "question"
::   msg ask --to cc --query "question"
::
:: Async (mailbox):
::   msg send --from cc --to gc --msg "note"
::   msg check --target gc
::   msg mark-read --target gc --all
::
:: Status:
::   msg status
::   msg update-status --mission "task" --phase "2"
for %%I in ("%~dp0..\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PATH=%PORTABLE_ROOT%\_sys\env\venv\Scripts;%PORTABLE_ROOT%\_sys\env\nodejs\npm-global;%PATH%"
"%PORTABLE_ROOT%\_sys\env\venv\Scripts\python.exe" "%~dp0..\core\hub.py" %*
