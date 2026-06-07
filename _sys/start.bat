@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: start.bat  -  Portable Sandbox Development Environment Launcher
::
:: Location : [PortableDev]\_sys\start.bat
::            -> SYS_DIR  = _sys\         (this folder)
::            -> BASE_DIR = PortableDev\  (parent, docs + workspace)
:: ================================================================

:: ----------------------------------------------------------------
:: 1. Physical base paths (before SUBST)
:: ----------------------------------------------------------------
set "SYS_DIR_PHYS=%~dp0"
if "%SYS_DIR_PHYS:~-1%"=="\" set "SYS_DIR_PHYS=%SYS_DIR_PHYS:~0,-1%"
for %%I in ("%SYS_DIR_PHYS%\..") do set "BASE_DIR_PHYS=%%~fI"

set "HOST_LOCALAPPDATA=%LOCALAPPDATA%"
set "HOST_PATH_BACKUP=%PATH%"

:: ----------------------------------------------------------------
:: [Per-PC config] Load local.config.bat
:: ----------------------------------------------------------------
if exist "%SYS_DIR_PHYS%\local.config.bat" call "%SYS_DIR_PHYS%\local.config.bat"

:: Re-derive physical paths (resilient to USB drive letter changes)
set "SYS_DIR_PHYS=%~dp0"
if "%SYS_DIR_PHYS:~-1%"=="\" set "SYS_DIR_PHYS=%SYS_DIR_PHYS:~0,-1%"
for %%I in ("%SYS_DIR_PHYS%\..") do set "BASE_DIR_PHYS=%%~fI"

:: ----------------------------------------------------------------
:: 2. SUBST restore + path derivation
:: ----------------------------------------------------------------
if defined SUBST_DRIVE_LETTER (
    if exist "%SUBST_DRIVE_LETTER%:\" (
        :: S-3: Verify this drive maps to OUR PortableDev instance, not another
        if not exist "%SUBST_DRIVE_LETTER%:\_sys\start.bat" (
            echo [Warning] Drive %SUBST_DRIVE_LETTER%: is mapped to a different path. Remapping...
            subst %SUBST_DRIVE_LETTER%: /D >nul 2>&1
            subst %SUBST_DRIVE_LETTER%: "%BASE_DIR_PHYS%"
            if errorlevel 1 (
                echo [Error] Drive %SUBST_DRIVE_LETTER%: is occupied.
                echo         Run register.bat to reassign.
                goto :ERROR_EXIT
            )
        )
    ) else (
        subst %SUBST_DRIVE_LETTER%: "%BASE_DIR_PHYS%"
        if errorlevel 1 (
            echo [Error] Drive %SUBST_DRIVE_LETTER%: is occupied.
            echo         Run register.bat to reassign.
            goto :ERROR_EXIT
        )
        echo [Info] Waiting for drive %SUBST_DRIVE_LETTER%: to stabilize...
        for /L %%I in (1,1,10) do (
            if exist "%SUBST_DRIVE_LETTER%:\" (
                timeout /t 2 > nul
                goto :DRIVE_READY
            )
            timeout /t 1 > nul
            <nul set /p=.
        )
        echo [Timeout] Drive mapping taking too long.
        goto :DRIVE_READY

        :DRIVE_READY
        echo  [Ready]
    )
    set "BASE_DIR=%SUBST_DRIVE_LETTER%:"
    set "SYS_DIR=%SUBST_DRIVE_LETTER%:\_sys"
) else (
    echo [Warning] Not registered. Run register.bat for full portability.
    :: S-2: Detect non-ASCII (Korean) path and auto-assign a temporary SUBST drive
    powershell -NoProfile -Command "exit ([int]($env:BASE_DIR_PHYS -match '[^\x00-\x7F]'))" >nul 2>&1
    if errorlevel 1 (
        echo [Info] Korean path detected. Assigning temporary SUBST drive for this session...
        set "TEMP_DRIVEOK=0"
        for %%D in (Z Y X W V U T S R Q P O N M L K J I H G F E) do (
            if "!TEMP_DRIVEOK!"=="0" (
                if not exist "%%D:\" (
                    subst %%D: "%BASE_DIR_PHYS%" >nul 2>&1
                    if not errorlevel 1 set "TEMP_DRIVEOK=%%D"
                )
            )
        )
        if not "!TEMP_DRIVEOK!"=="0" (
            echo [Info] Temporary drive !TEMP_DRIVEOK!: assigned. Node.js tools are now available.
            set "BASE_DIR=!TEMP_DRIVEOK!:"
            set "SYS_DIR=!TEMP_DRIVEOK!:\_sys"
        ) else (
            echo [Warning] All drive letters occupied. Node.js tools may fail with Korean path.
            set "BASE_DIR=%BASE_DIR_PHYS%"
            set "SYS_DIR=%SYS_DIR_PHYS%"
        )
    ) else (
        set "BASE_DIR=%BASE_DIR_PHYS%"
        set "SYS_DIR=%SYS_DIR_PHYS%"
    )
)

set "ENV_DIR=%SYS_DIR%\env"
set "TOOLS_DIR=%SYS_DIR%\tools"
set "CLAUDE_DIR=%SYS_DIR%\claude"
set "DATA_DIR=%SYS_DIR%\data"

:: ----------------------------------------------------------------
:: 3. Log file init
:: ----------------------------------------------------------------
set "LOG_DIR=%BASE_DIR%\_archive\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "SESSION_DIR=%BASE_DIR%\_archive\sessions"
if not exist "%SESSION_DIR%" mkdir "%SESSION_DIR%"

for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "_DT=%%I"
set "LOG_FILE=%LOG_DIR%\start_%_DT:~0,8%_%_DT:~8,6%.log"

>> "%LOG_FILE%" echo Started : %DATE% %TIME%
>> "%LOG_FILE%" echo BASE    : %BASE_DIR%

:: ----------------------------------------------------------------
:: 4. Environment Variables
:: ----------------------------------------------------------------
set "SANDBOX_TEMP=%DATA_DIR%\temp"
if not exist "%SANDBOX_TEMP%" mkdir "%SANDBOX_TEMP%"
set "TEMP=%SANDBOX_TEMP%"
set "TMP=%SANDBOX_TEMP%"

set "NPM_CONFIG_PREFIX=%ENV_DIR%\nodejs\npm-global"
set "NPM_CONFIG_CACHE=%ENV_DIR%\nodejs\npm-cache"
set "PIP_CACHE_DIR=%ENV_DIR%\python\pip-cache"
set "PYTHONUSERBASE=%ENV_DIR%\python\userbase"
set "CLAUDE_CONFIG_DIR=%CLAUDE_DIR%\config"
set "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"

:: Sync statusline script to host Claude config (ensures statusline works on any PC)
if exist "%CLAUDE_DIR%\config\statusline-command.sh" (
    if not exist "%USERPROFILE%\.claude" mkdir "%USERPROFILE%\.claude"
    copy /Y "%CLAUDE_DIR%\config\statusline-command.sh" "%USERPROFILE%\.claude\statusline-command.sh" >nul 2>&1
)
set "GEMINI_DIR=%SYS_DIR%\gemini"

if exist "%GEMINI_DIR%\gemini-status.bat" call "%GEMINI_DIR%\gemini-status.bat"
if not exist "%GEMINI_DIR%\gemini-status.bat" set "GEMINI_MODE=OFF"

:: ----------------------------------------------------------------
:: 5. PATH integration
:: ----------------------------------------------------------------
set "PATH=%ENV_DIR%\nodejs\npm-global;%ENV_DIR%\venv\Scripts;%ENV_DIR%\python;%ENV_DIR%\python\Scripts;%ENV_DIR%\nodejs;%ENV_DIR%\ffmpeg\bin;%PATH%"

if exist "%ENV_DIR%\pwsh" set "PATH=%ENV_DIR%\pwsh;%PATH%"
if exist "%SYS_DIR%\cli" set "PATH=%SYS_DIR%\cli;%PATH%"
if exist "%SYS_DIR%\hooks" set "PATH=%SYS_DIR%\hooks;%PATH%"
if exist "%SYS_DIR%\checks" set "PATH=%SYS_DIR%\checks;%PATH%"
if exist "%TOOLS_DIR%\ripgrep" set "PATH=%TOOLS_DIR%\ripgrep;%PATH%"
if exist "%TOOLS_DIR%\fd" set "PATH=%TOOLS_DIR%\fd;%PATH%"
if exist "%TOOLS_DIR%\jq" set "PATH=%TOOLS_DIR%\jq;%PATH%"
if exist "%TOOLS_DIR%\bat" set "PATH=%TOOLS_DIR%\bat;%PATH%"
if exist "%TOOLS_DIR%\delta" set "PATH=%TOOLS_DIR%\delta;%PATH%"
if exist "%TOOLS_DIR%\fzf" set "PATH=%TOOLS_DIR%\fzf;%PATH%"
if exist "%TOOLS_DIR%\oh-my-posh" set "PATH=%TOOLS_DIR%\oh-my-posh;%PATH%"
if exist "%TOOLS_DIR%\sqlite" set "PATH=%TOOLS_DIR%\sqlite;%PATH%"
if exist "%TOOLS_DIR%\gh" set "PATH=%TOOLS_DIR%\gh;%PATH%"

if exist "%ENV_DIR%\git\cmd\git.exe" (
    set "PATH=%ENV_DIR%\git\cmd;%ENV_DIR%\git\usr\bin;%PATH%"
    if exist "%SYS_DIR%\git-config\.gitconfig" set "GIT_CONFIG_GLOBAL=%SYS_DIR%\git-config\.gitconfig"
)

:: ----------------------------------------------------------------
:: 6. Python venv
:: ----------------------------------------------------------------
set "VENV_DIR=%ENV_DIR%\venv"
set "PY_DIR=%ENV_DIR%\python"
if not exist "%VENV_DIR%" (
    if exist "%PY_DIR%\python.exe" (
        call :LOG "[Info] Creating Python virtual environment..."
        "%PY_DIR%\python.exe" -m venv "%VENV_DIR%" >> "%LOG_FILE%" 2>&1
    )
)
:: Dynamically update pyvenv.cfg to match the current mapped drive/path
if exist "%VENV_DIR%\pyvenv.cfg" (
    "%PY_DIR%\python.exe" -c "import sys, re; p=sys.argv[1]; d=sys.argv[2]; txt=open(p, encoding='utf-8').read(); txt=re.sub(r'(?m)^(home\s*=\s*).*', r'\g<1>' + d.replace('\\', '\\\\'), txt); txt=re.sub(r'(?m)^(executable\s*=\s*).*', r'\g<1>' + d.replace('\\', '\\\\') + r'\\python.exe', txt); open(p, 'w', encoding='utf-8').write(txt)" "%VENV_DIR%\pyvenv.cfg" "%PY_DIR%"
)

if exist "%VENV_DIR%\Scripts" (
    set "VIRTUAL_ENV=%VENV_DIR%"
    set "PYTHONHOME="
    set "PATH=%VENV_DIR%\Scripts;%PATH%"
)

:: ----------------------------------------------------------------
:: 7. Target analysis
:: ----------------------------------------------------------------
set "TARGET=%~1"
if defined TARGET (
    for %%I in ("!TARGET!") do set "TARGET=%%~fI"
)
if defined SUBST_DRIVE_LETTER (
    set "TARGET=!TARGET:%BASE_DIR_PHYS%=%BASE_DIR%!"
)

:: A: no args -> open BASE_DIR as workspace
if "!TARGET!"=="" (
    set "TARGET_DIR=%BASE_DIR%"
    goto :RUN_DEV
)

:: validate path exists
if not exist "!TARGET!" if not exist "!TARGET!\" (
    echo [Error] Path not found: !TARGET!
    goto :ERROR_EXIT
)

:: B: folder -> open in VS Code
if exist "!TARGET!\" (
    set "TARGET_DIR=!TARGET!"
    goto :RUN_DEV
)

:: C: file -> run with portable tools
set "TARGET_EXT="
set "TARGET_DIR="
for %%I in ("!TARGET!") do (
    set "TARGET_DIR=%%~dpI"
    set "TARGET_EXT=%%~xI"
)
goto :RUN_APP

:RUN_DEV
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
cd /d "%TARGET_DIR%"
if exist "%ENV_DIR%\vscode\Code.exe" (
    call :LOG "[OK] Launching VS Code: %TARGET_DIR%"
    start "" "%ENV_DIR%\vscode\Code.exe" "."
) else (
    echo [Warning] VS Code not found at %ENV_DIR%\vscode\Code.exe
)
if not "%NO_DESKTOP%"=="1" (
    if exist "%HOST_LOCALAPPDATA%\Programs\Claude\Claude.exe" (
        start "" "%HOST_LOCALAPPDATA%\Programs\Claude\Claude.exe"
    )
)
goto :END

:RUN_APP
call :LOG "[OK] Running: %TARGET%"
cd /d "%TARGET_DIR%"
if /i "!TARGET_EXT!"==".py" (
    if exist "%VENV_DIR%\Scripts\python.exe" (
        "%VENV_DIR%\Scripts\python.exe" "%TARGET%"
    ) else if exist "%PY_DIR%\python.exe" (
        "%PY_DIR%\python.exe" "%TARGET%"
    ) else (
        echo [Error] Portable Python not found
        goto :ERROR_EXIT
    )
) else if /i "!TARGET_EXT!"==".bat" (
    cmd /c "%TARGET%"
) else (
    start "Sandboxed App" "%TARGET%"
)

:END
call :LOG "[Done] Finished"
if "%~1"=="" (
    echo [Sandbox] Environment ready at %BASE_DIR%
    cmd /k
)
endlocal
exit /b 0

:ERROR_EXIT
call :LOG "[Fatal] Terminated with errors."
pause
endlocal
exit /b 1

:LOG
echo %~1
>> "%LOG_FILE%" echo %~1
exit /b 0

