@echo off
:: cd to this script's own location FIRST, then use paths relative to it
:: everywhere below (never %~dp0-prefixed). This runs before Python/SUBST
:: exist, so it's the only portability net available yet -- and %~dp0 is an
:: absolute path that can contain cmd.exe metacharacters (e.g. "&", which a
:: real portable-root folder name hit 2026-09-04: "D:\Engram&Peerhub\...").
:: A plain quoted top-level command tolerates "&" fine (this cd included),
:: but re-embedding that absolute path inside a for /f ('command') or
:: backtick command-substitution below does not -- cmd.exe re-parses that
:: inner string as a fresh command line, where an unescaped "&" becomes a
:: command separator. Relative paths never contain "&" here, so they sidestep
:: the whole class of bug rather than requiring per-callsite escaping.
::
:: CRITICAL: "cd /d %~dp0" MUST happen BEFORE "setlocal enabledelayedexpansion"!
:: If delayed expansion is enabled first, any "!" (exclamation point) in the
:: folder path is stripped/corrupted during delayed expansion parsing, causing
:: "cd /d" to fail with "The system cannot find the path specified".
cd /d "%~dp0"
setlocal enabledelayedexpansion
:: ================================================================
:: INSTALL.bat  -  Portable Dev Environment Bootstrapper
::
:: Bootstraps minimal Python, then delegates to _sys\core\setup.py.
:: Runtime versions/URLs sourced from _sys\runtimes.json (no hardcoding).
:: ================================================================

:: ── Runtime config from _sys\runtimes.json (fallback if missing) ──
set "_RT=_sys\runtimes.json"
set "PY_VER=3.13.4"
set "PY_URL=https://www.python.org/ftp/python/3.13.4/python-3.13.4-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
if exist "!_RT!" (
    for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.version"`) do set "PY_VER=%%v"
    for /f "usebackq delims=" %%u in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.url"`) do set "PY_URL=%%u"
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.get_pip_url"`) do set "GET_PIP_URL=%%p"
)

set "PY_DIR=_sys\env\python"
set "PY_EXE=%PY_DIR%\python.exe"
set "_PY_BUMP=0"
set "_OLD_PY_VER=%PY_VER%"

:: An existing interpreter must match the declaration before discovery can run.
:: Safe in-place Python replacement is not implemented, so never rewrite the pin
:: while a different interpreter remains on disk.
if exist "%PY_EXE%" (
    set "_INSTALLED_PY_VER="
    for /f "tokens=2" %%v in ('"%PY_EXE%" --version 2^>^&1') do set "_INSTALLED_PY_VER=%%v"
    if "!_INSTALLED_PY_VER!"=="" (
        echo [Error] Could not read the installed Python version from _sys\env\python\python.exe.
        exit /b 1
    )
    if /i not "!_INSTALLED_PY_VER!"=="!PY_VER!" (
        echo [Error] Python consistency check failed.
        echo         Installed: !_INSTALLED_PY_VER!
        echo         Declared : !PY_VER!
        echo Close portable tools, remove _sys\env\python, then rerun INSTALL.bat.
        exit /b 1
    )
)

:: ── Auto-fetch latest stable Python (skip with --skip-update) ──
set "_SKIP_UPDATE=0"
for %%A in (%*) do if /i "%%A"=="--skip-update" set "_SKIP_UPDATE=1"

if "!_SKIP_UPDATE!"=="0" (
    echo ^>^>^> Checking for latest stable Python...
    for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command ^
        "try { $r=(Invoke-RestMethod 'https://endoflife.date/api/python.json' -TimeoutSec 8 -EA Stop); $v=($r | Where-Object { $_.eol -eq $false -or $_.eol -eq $null -or ([datetime]$_.eol -gt (Get-Date)) } | Select-Object -First 1).latest; if ($v -match '^\d+\.\d+\.\d+$') { $v } else { '' } } catch { '' }"`) do set "_LATEST_VER=%%L"

    if not "!_LATEST_VER!"=="" (
        if not "!_LATEST_VER!"=="!PY_VER!" (
            if exist "%PY_EXE%" (
                echo [i] Python !PY_VER! is installed; newer !_LATEST_VER! is available.
                echo [i] Not auto-applied: safe in-place Python replacement is not implemented.
                echo [i] To upgrade, close portable tools, remove _sys\env\python, then rerun INSTALL.bat.
            ) else (
                echo [i] New Python version available for first install: !_LATEST_VER! (pinned: !PY_VER!)
                set "_NEW_URL=https://www.python.org/ftp/python/!_LATEST_VER!/python-!_LATEST_VER!-embed-amd64.zip"
                if exist "!_RT!" (
                    set "_PY_BUMP=1"
                    set "_OLD_PY_VER=!PY_VER!"
                    set "PY_VER=!_LATEST_VER!"
                    set "PY_URL=!_NEW_URL!"
                ) else (
                    echo [Warning] runtimes.json is missing; keeping the built-in Python pin.
                )
            )
        ) else (
            echo [OK] Python !PY_VER! is already latest stable.
        )
    ) else (
        echo [!] Could not fetch latest version. Using pinned: !PY_VER!
    )
)

echo ^>^>^> Checking for Portable Python %PY_VER%...

if not exist "%PY_EXE%" (
    echo [i] Python not found. Bootstrapping Python !PY_VER!...
    if not exist "_sys\data\setup-files" mkdir "_sys\data\setup-files"

    set "ZIP_PATH=_sys\data\setup-files\python-bootstrap.zip"

    echo [i] Downloading Python embeddable zip...
    curl -L "!PY_URL!" -o "!ZIP_PATH!"
    if errorlevel 1 (
        echo [Error] Failed to download Python.
        if "%CI%"=="" pause
        exit /b 1
    )

    echo [i] Extracting Python...
    if not exist "%PY_DIR%" mkdir "%PY_DIR%"
    powershell -NoProfile -Command "Expand-Archive -Force -Path '!ZIP_PATH!' -DestinationPath '%PY_DIR%'"
    if errorlevel 1 (
        echo [Error] Failed to extract Python.
        if "%CI%"=="" pause
        exit /b 1
    )

    :: Enable pip (uncomment import site in ._pth)
    for %%f in ("%PY_DIR%\python*._pth") do (
        powershell -NoProfile -Command "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
    )

    :: Install pip
    echo [i] Installing pip from !GET_PIP_URL!...
    curl -L "!GET_PIP_URL!" -o "_sys\data\setup-files\get-pip.py"
    "%PY_EXE%" "_sys\data\setup-files\get-pip.py" --no-warn-script-location
)

:: Verify the bootstrap postcondition before the Python dispatcher is invoked.
set "_INSTALLED_PY_VER="
for /f "tokens=2" %%v in ('"%PY_EXE%" --version 2^>^&1') do set "_INSTALLED_PY_VER=%%v"
if /i not "!_INSTALLED_PY_VER!"=="!PY_VER!" (
    echo [Error] Python bootstrap postcondition failed.
    echo         Installed: !_INSTALLED_PY_VER!
    echo         Declared : !PY_VER!
    exit /b 1
)

:: Persist a discovered first-install bump only after the interpreter exists and
:: reports that exact version. If persistence fails, remove the new interpreter
:: so the old declaration and disk cannot silently diverge.
if "!_PY_BUMP!"=="1" (
    powershell -NoProfile -Command ^
        "$d=Get-Content '!_RT!' -Raw | ConvertFrom-Json; $d.runtimes.python.version='!PY_VER!'; $d.runtimes.python.url='!PY_URL!'; [System.IO.File]::WriteAllText('!_RT!', ($d | ConvertTo-Json -Depth 10), (New-Object System.Text.UTF8Encoding($false)))"
    if errorlevel 1 (
        echo [Error] Failed to persist Python !PY_VER! in runtimes.json; rolling back the bootstrap.
        rmdir /s /q "%PY_DIR%"
        if exist "%PY_EXE%" echo [Error] Python rollback was incomplete; remove _sys\env\python manually.
        exit /b 1
    )
    echo [OK] runtimes.json updated to Python !PY_VER!
    powershell -NoProfile -Command ^
        "$log='_sys\data\logs\runtimes_drift.jsonl'; $dir=Split-Path $log; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }; $line = @{ timestamp=(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); source='install_bat_python_bootstrap'; old_version='!_OLD_PY_VER!'; new_version='!PY_VER!' } | ConvertTo-Json -Compress; Add-Content -Path $log -Value $line"
)

echo [OK] Python is ready. Handing over to dispatcher...
call "_sys\core\dispatch.bat" install %* || (echo [FATAL] Setup failed. & pause & exit /b 1)

echo [OK] Setup completed successfully.
endlocal
