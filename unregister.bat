@echo off
cd /d "%~dp0"
call "_sys\core\dispatch.bat" unregister %*
