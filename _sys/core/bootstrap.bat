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
if not defined ENGRAM_SYS_DIR (
    for %%I in ("%~dp0..") do set "ENGRAM_SYS_DIR=%%~nxI"
)
cd /d "%~dp0..\.."
set "SYS_DIR=%ENGRAM_SYS_DIR%"
setlocal enabledelayedexpansion
:: ================================================================
:: %SYS_DIR%/core/bootstrap.bat  -  Portable Dev Environment Bootstrapper
::
:: Bootstraps minimal Python, then delegates to %SYS_DIR%\core\setup.py.
:: Runtime versions/URLs sourced from %SYS_DIR%\runtimes.json (no hardcoding).
:: ================================================================

:: -- Interrupted environment operation gate (design section 9) --
:: A non-terminal env-op journal means a Python swap was interrupted. Extracting a fresh Python now would
:: collide with the half-swapped tree, so refuse before anything is downloaded or created.
set "_JF=!SYS_DIR!\data\state\env-op.journal.jsonl"
if exist "!_JF!" (
    set "_LASTN="
    set "_TERMN="
    for /f "tokens=1 delims=:" %%N in ('findstr /n /l /c:"\"event\":\"PHASE\"" "!_JF!"') do set "_LASTN=%%N"
    if defined _LASTN (
        for /f "tokens=1 delims=:" %%N in ('findstr /n /l /c:"\"name\":\"COMMITTED\"" /c:"\"name\":\"ROLLED_BACK\"" "!_JF!"') do set "_TERMN=%%N"
        if not "!_LASTN!"=="!_TERMN!" (
            echo [Error] An environment operation was interrupted; its journal is still open.
            echo         Run: engram repair --resume   or   engram repair --rollback
            exit /b 14
        )
    )
)

:: -- Bootstrap default configuration --
if not exist "!SYS_DIR!\runtimes.json" copy /y "!SYS_DIR!\defaults\runtimes.json" "!SYS_DIR!\runtimes.json" >nul
if not exist "!SYS_DIR!\tool-catalog.v1.json" copy /y "!SYS_DIR!\defaults\tool-catalog.v1.json" "!SYS_DIR!\tool-catalog.v1.json" >nul

:: -- Runtime config from runtimes.json (fallback if missing) --
set "_RT=!SYS_DIR!\runtimes.json"
set "PY_VER=3.14.5"
set "PY_URL=https://www.python.org/ftp/python/3.14.5/python-3.14.5-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "PY_SHA256="
if exist "!_RT!" (
    for /f "usebackq delims=" %%s in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.sha256"`) do set "PY_SHA256=%%s"
    for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.version"`) do set "PY_VER=%%v"
    for /f "usebackq delims=" %%u in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.url"`) do set "PY_URL=%%u"
    for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "((Get-Content '!_RT!')|ConvertFrom-Json).runtimes.python.get_pip_url"`) do set "GET_PIP_URL=%%p"
)

set "PY_DIR=!SYS_DIR!\env\python"
set "PY_EXE=!PY_DIR!\python.exe"

:: An existing interpreter must match the validated declaration.
if exist "!PY_EXE!" (
    set "_INSTALLED_PY_VER="
    for /f "tokens=2" %%v in ('"!PY_EXE!" --version 2^>^&1') do set "_INSTALLED_PY_VER=%%v"
    if "!_INSTALLED_PY_VER!"=="" (
        echo [Error] Could not read the installed Python version from !SYS_DIR!\env\python\python.exe.
        exit /b 1
    )
    if /i not "!_INSTALLED_PY_VER!"=="!PY_VER!" (
        echo [Error] Python consistency check failed.
        echo         Installed: !_INSTALLED_PY_VER!
        echo         Declared : !PY_VER!
        echo Use engram update --only python for a managed update.
        exit /b 1
    )
)

:: Bootstrap always installs the validated pin. --skip-update skips only this notice check.
set "_SKIP_UPDATE=0"
set "_LATEST_VER="
for %%A in (%*) do if /i "%%A"=="--skip-update" set "_SKIP_UPDATE=1"
if "!_SKIP_UPDATE!"=="0" (
    echo ^>^>^> Checking for latest stable Python...
    for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command ^
        "try { $r=(Invoke-RestMethod 'https://endoflife.date/api/python.json' -TimeoutSec 8 -EA Stop); $v=($r | Where-Object { $_.eol -eq $false -or $_.eol -eq $null -or ([datetime]$_.eol -gt (Get-Date)) } | Sort-Object { [version]$_.latest } -Descending | Select-Object -First 1).latest; if ($v -match '^\d+\.\d+\.\d+$') { $v } else { '' } } catch { '' }"`) do set "_LATEST_VER=%%L"
    if defined _LATEST_VER (
        powershell -NoProfile -Command "if ([version]'!_LATEST_VER!' -gt [version]'!PY_VER!') { Write-Host '[i] Newer Python !_LATEST_VER! is available. Use engram update --check.' }"
    )
)

echo ^>^>^> Checking for Portable Python %PY_VER%...

if not exist "!PY_EXE!" (
    echo [i] Python not found. Bootstrapping Python !PY_VER!...
    if not defined PY_SHA256 echo [Warning] downloaded over HTTPS from python.org; no pinned SHA-256
    if not exist "!SYS_DIR!\data\setup-files" mkdir "!SYS_DIR!\data\setup-files"

    REM The hash uses .NET directly - not Get-FileHash - when bootstrap is started from a
    REM PowerShell 7 session the inherited PSModulePath hides the 5.1 utility module.
    REM Versioned cache with a recorded sha256 per design P9, a cached zip is reused only
    REM when its recorded hash still matches, so an offline re-bootstrap works and an
    REM unverified or tampered file is never trusted.
    set "ZIP_PATH=!SYS_DIR!\data\setup-files\python-!PY_VER!-embed-amd64.zip"
    set "SHA_PATH=!ZIP_PATH!.sha256"
    REM PowerShell single-quote escaping for the hash commands - a quote in the path would end the string.
    set "_ZIP_PS=!ZIP_PATH:'=''!"
    set "_CACHE_OK=0"
    set "_CACHED_SHA="
    set "_ACTUAL_SHA="
    if exist "!ZIP_PATH!" if exist "!SHA_PATH!" (
        for /f "usebackq delims=" %%h in ("!SHA_PATH!") do if not defined _CACHED_SHA set "_CACHED_SHA=%%h"
        for /f "usebackq delims=" %%h in (`powershell -NoProfile -Command "([System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath '!_ZIP_PS!').ProviderPath))) -replace '-','').ToLower()"`) do set "_ACTUAL_SHA=%%h"
        if defined _ACTUAL_SHA if /i "!_CACHED_SHA!"=="!_ACTUAL_SHA!" set "_CACHE_OK=1"
        REM A hash declared in runtimes.json from PY_SHA256 gates the cache as well.
        if "!_CACHE_OK!"=="1" if defined PY_SHA256 if /i not "!PY_SHA256!"=="!_ACTUAL_SHA!" set "_CACHE_OK=0"
    )

    if "!_CACHE_OK!"=="1" (
        echo [OK] Using the verified cached Python zip.
    ) else (
        echo [i] Downloading Python embeddable zip...
        REM -f: an HTTP error such as 404, 503 or a captive portal must fail instead of being saved as the zip.
        curl -fL "!PY_URL!" -o "!ZIP_PATH!"
        if errorlevel 1 (
            echo [Error] Failed to download Python.
            del /q "!ZIP_PATH!" >nul 2>&1
            del /q "!SHA_PATH!" >nul 2>&1
            if "%CI%"=="" pause
            exit /b 1
        )
        set "_ACTUAL_SHA="
        for /f "usebackq delims=" %%h in (`powershell -NoProfile -Command "([System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath '!_ZIP_PS!').ProviderPath))) -replace '-','').ToLower()"`) do set "_ACTUAL_SHA=%%h"
        if "!_ACTUAL_SHA!"=="" (
            echo [Error] Could not compute the sha256 of the downloaded Python zip.
            del /q "!ZIP_PATH!" >nul 2>&1
            exit /b 1
        )
        if defined PY_SHA256 if /i not "!PY_SHA256!"=="!_ACTUAL_SHA!" (
            echo [Error] Python zip checksum mismatch.
            echo         Expected: !PY_SHA256!
            echo         Actual  : !_ACTUAL_SHA!
            del /q "!ZIP_PATH!" >nul 2>&1
            exit /b 1
        )
    )

    echo [i] Extracting Python...
    set "_PY_DIR_NEW=0"
    if not exist "!PY_DIR!" set "_PY_DIR_NEW=1"
    if not exist "!PY_DIR!" mkdir "!PY_DIR!"
    powershell -NoProfile -Command "Expand-Archive -Force -Path '!_ZIP_PS!' -DestinationPath '!PY_DIR!'"
    if errorlevel 1 (
        echo [Error] Failed to extract Python.
        REM Never leave a zip that cannot be extracted behind as a "verified" cache.
        del /q "!ZIP_PATH!" >nul 2>&1
        del /q "!SHA_PATH!" >nul 2>&1
        REM Remove a half-extracted tree only if this attempt created the directory.
        if "!_PY_DIR_NEW!"=="1" if exist "!PY_DIR!" rmdir /s /q "!PY_DIR!"
        if "%CI%"=="" pause
        exit /b 1
    )
    REM Record the hash only now that the zip is known to extract per design P9.
    if not "!_CACHE_OK!"=="1" >"!SHA_PATH!" echo !_ACTUAL_SHA!

    echo [i] Python archive SHA-256: !_ACTUAL_SHA!

    REM Enable pip by uncommenting import site in ._pth
    for %%f in ("!PY_DIR!\python3*._pth") do (
        powershell -NoProfile -Command "(Get-Content '%%f') -replace '#import site', 'import site' | Set-Content '%%f'"
    )

    REM Install pip
    echo [i] Installing pip from !GET_PIP_URL!...
    curl -L "!GET_PIP_URL!" -o "!SYS_DIR!\data\setup-files\get-pip.py"
    "!PY_EXE!" "!SYS_DIR!\data\setup-files\get-pip.py" --no-warn-script-location
)

:: Verify the bootstrap postcondition before the Python dispatcher is invoked.
set "_INSTALLED_PY_VER="
for /f "tokens=2" %%v in ('"!PY_EXE!" --version 2^>^&1') do set "_INSTALLED_PY_VER=%%v"
if /i not "!_INSTALLED_PY_VER!"=="!PY_VER!" (
    echo [Error] Python bootstrap postcondition failed.
    echo         Installed: !_INSTALLED_PY_VER!
    echo         Declared : !PY_VER!
    exit /b 1
)

echo [OK] Python is ready. Handing over to dispatcher...
call "!SYS_DIR!\core\dispatch.bat" install %* || (echo [FATAL] Setup failed. & pause & exit /b 1)

echo [OK] Setup completed successfully.
endlocal
