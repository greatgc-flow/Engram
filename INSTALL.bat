@echo off
setlocal enabledelayedexpansion
:: ================================================================
:: INSTALL.bat  -  Portable Dev Environment Bootstrapper
::
:: Bootstraps minimal Python, then delegates to _sys\core\setup.py.
:: Runtime versions/URLs sourced from _sys\runtimes.json (no hardcoding).
:: ================================================================

:: ── Runtime config from _sys\runtimes.json (fallback if missing) ──
set "_RT=%~dp0_sys\runtimes.json"
set "PY_VER=3.13.4"
set "PY_URL=https://www.python.org/ftp/python/3.13.4/python-3.13.4-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
if exist "!_RT!" (
    for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.version"`) do set "PY_VER=%%v"
    for /f "usebackq delims=" %%u in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.url"`) do set "PY_URL=%%u"
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.get_pip_url"`) do set "GET_PIP_URL=%%p"
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
            echo [i] New Python version available: !_LATEST_VER! (current: !PY_VER!)
            set "_NEW_URL=https://www.python.org/ftp/python/!_LATEST_VER!/python-!_LATEST_VER!-embed-amd64.zip"
            if exist "!_RT!" (
                powershell -NoProfile -Command ^
                    "$d=Get-Content '!_RT!' -Raw | ConvertFrom-Json; $d.runtimes.python.version='!_LATEST_VER!'; $d.runtimes.python.url='!_NEW_URL!'; [System.IO.File]::WriteAllText('!_RT!', ($d | ConvertTo-Json -Depth 10), (New-Object System.Text.UTF8Encoding($false)))"
                echo [OK] runtimes.json updated to Python !_LATEST_VER!
            )
            set "PY_VER=!_LATEST_VER!"
            set "PY_URL=!_NEW_URL!"
        ) else (
            echo [OK] Python !PY_VER! is already latest stable.
        )
    ) else (
        echo [!] Could not fetch latest version. Using pinned: !PY_VER!
    )
)

set "PY_DIR=%~dp0_sys\env\python"
set "PY_EXE=%PY_DIR%\python.exe"

echo ^>^>^> Checking for Portable Python %PY_VER%...

if not exist "%PY_EXE%" (
    echo [i] Python not found. Bootstrapping Python !PY_VER!...
    if not exist "%~dp0_sys\data\setup-files" mkdir "%~dp0_sys\data\setup-files"

    set "ZIP_PATH=%~dp0_sys\data\setup-files\python-bootstrap.zip"

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
    curl -L "!GET_PIP_URL!" -o "%~dp0_sys\data\setup-files\get-pip.py"
    "%PY_EXE%" "%~dp0_sys\data\setup-files\get-pip.py" --no-warn-script-location
)

echo [OK] Python is ready. Handing over to dispatcher...
call "%~dp0_sys\core\dispatch.bat" install %* || (echo [FATAL] Setup failed. & pause & exit /b 1)

echo [OK] Setup completed successfully.
endlocal
