@echo off
setlocal
if "%~1"=="" (
    call "%~dp0peerhub.bat" status
    exit /b %ERRORLEVEL%
)

call "%~dp0peerhub.bat" %*
exit /b %ERRORLEVEL%
