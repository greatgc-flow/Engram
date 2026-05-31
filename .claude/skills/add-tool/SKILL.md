---
name: add-tool
description: "Integrate a new CLI tool into the Portable Dev Environment tools/ folder. Handles tool placement, start.bat PATH registration, environment variable setup, CLAUDE.md update. Use for: new tool addition, tool integration, tools/ folder setup."
---

# Add Tool — CLI Tool Integration Procedure

## When to Use
- Adding a new CLI tool to tools/ folder
- Integrating a portable executable into the dev environment
- Setting up PATH registration for a new tool

## Supported Tools (Standard 8)
ripgrep, fd, jq, bat, delta, fzf, sqlite, oh-my-posh

## Integration Steps

1. **Place tool files**
   - Single exe: `tools/{name}/{name}.exe`
   - Multi-file: `tools/{name}/` folder with all files
   - Example: `tools/jq/jq.exe`, `tools/ripgrep/rg.exe`

2. **Register PATH in start.bat**
   - Find "Optional single-exe tools" section
   - Add line: `if exist "%TOOLS_DIR%\{name}"     set "PATH=%TOOLS_DIR%\{name};%PATH%"`
   - One `if exist` line per tool (no for-loop — PATH expansion bug)

3. **Set environment variables (if needed)**
   - bat cache: `BAT_CACHE_PATH=%_BASE%\_sys\data\bat-cache`
   - Git pager: `GIT_PAGER=delta` (if delta installed)
   - Other tool-specific vars in start.bat env section

4. **Record in .setup-files/**
   - Add entry: `{name} {version} {download_url}`

5. **Update CLAUDE.md**
   - tools/ structure table: `[not installed]` -> `[installed]`
   - Add env vars to environment section if added

## Integration Log
Write `_workspace/02_tool_integration.md`:
```
# Tool Integration: {name}
Added: {date}
Path: tools/{name}/
PATH: %TOOLS_DIR%\{name}
Env vars: {list or none}
Download: {url}
Version: {version}
```

## Verification
After integration, ask portability-auditor to verify:
- PATH registration uses if exist (not for-loop)
- No hardcoded drive letters
- Tool dir is inside BASE_DIR