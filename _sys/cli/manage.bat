@echo on
setlocal
:: manage.bat - Wrapper for manage.py
:: Unified Sandbox Environment Manager

for %%I in ("%~dp0..\..") do set "BASE_DIR_PHYS=%%~fI"
set "PY=%BASE_DIR_PHYS%\_sys\env\python\python.exe"

if not exist "%PY%" echo [Error] Portable Python not found at: "%PY%" && exit /b 1

"%PY%" "%~dp0manage.py" %*
endlocal
