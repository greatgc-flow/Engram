@echo off
:: ================================================================
:: INSTALL.bat  -  Portable Dev Environment First-Time Setup
::
:: Double-click this file to download and install everything:
::   Python, Node.js, FFmpeg, Git, VS Code, Claude Code CLI
::
:: Safe to run multiple times (already-installed items are skipped).
:: For full reinstall: run with -Force flag from PowerShell.
:: ================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_sys\setup.ps1"
