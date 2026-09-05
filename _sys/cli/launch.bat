@echo off
cd /d "%~dp0"
call "..\start.bat" %* || (echo [FATAL] Session ended with errors. & pause & exit /b 1)
