@echo off
setlocal
call "%~dp0peerhub.bat" diag %*
exit /b %ERRORLEVEL%
