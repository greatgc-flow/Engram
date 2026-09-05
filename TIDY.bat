@echo off
cd /d "%~dp0"
setlocal DisableDelayedExpansion

echo === Dry-run preview ===
"_sys\env\python\python.exe" "_sys\core\tidy_temp.py"
echo.

choice /M "Apply the cleanup above now"
if errorlevel 2 goto :end

"_sys\env\python\python.exe" "_sys\core\tidy_temp.py" --apply

:end
pause
