@echo off
setlocal
set "ROOT=%~dp0"

echo === Dry-run preview ===
"%ROOT%_sys\env\python\python.exe" "%ROOT%_sys\core\tidy_temp.py"
echo.

choice /M "Apply the cleanup above now"
if errorlevel 2 goto :end

"%ROOT%_sys\env\python\python.exe" "%ROOT%_sys\core\tidy_temp.py" --apply

:end
pause
