# Repository Guidelines

## Project Structure & Module Organization

This repository is a portable Windows development and AI-collaboration environment. Root batch files are user entrypoints: `INSTALL.bat` rebuilds the environment, `register.bat` and `unregister.bat` manage host registration, and `CLEANUP.bat` handles space cleanup. System logic lives under `_sys/`: `core/` contains Python core modules such as hub, setup, relocation, and config logic; `cli/` contains command wrappers and launchers; `checks/` contains Axis validation scripts; `hooks/` contains lifecycle hooks; `tests/` contains unit, integration, and Windows Sandbox tests; `templates/`, `docs/`, and agent-specific folders hold reusable configuration and documentation. Keep generated state, logs, and local data out of source control.

## Build, Test, and Development Commands

- `INSTALL.bat`: rebuilds portable runtimes and tools from a minimal checkout.
- `register.bat`: registers the current folder on a PC, including SUBST and context menu setup.
- `unregister.bat`: removes registration and related host integration.
- `_sys\tests\run-tests.bat --all`: runs the full test suite.
- `_sys\tests\unit`: contains pytest tests; run from the configured portable environment when possible.
- `_sys\checks\check-health.bat`, `_sys\checks\check-deps.bat`, `_sys\checks\check-portability.bat`: run targeted validation after script or portability changes.

## Coding Style & Naming Conventions

Use English only in source, comments, documentation, JSON, agent definitions, and batch output. Batch files must be UTF-8 without BOM, avoid `chcp`, and use safe quoted variable assignments such as `set "VAR=value"`. Prefer relative paths derived from `%BASE_DIR%` or `%SYS_DIR%`; do not hardcode drive letters. Python files follow standard pytest-friendly module naming and should keep path handling portable. JSON files should remain machine-readable, stable, and minimally reformatted.

## Testing Guidelines

Unit tests use pytest with a 60-second timeout configured in `_sys\tests\unit\pytest.ini`. Name Python tests `test_*.py` and place focused unit coverage in `_sys\tests\unit\`. Use integration scripts in `_sys\tests\` for tool interaction and Windows Sandbox scripts for destructive lifecycle scenarios. Run the relevant targeted checks before broader `--all` test runs.

## Commit & Pull Request Guidelines

Recent history uses Conventional Commit prefixes such as `feat:`, `fix:`, `docs:`, `refactor:`, and `test:`. Keep commits scoped to one behavioral change or documentation update. Pull requests should summarize intent, list validation performed, link related issues or protocol decisions, and include screenshots only for UI or console-output changes.

## Security & Configuration Tips

Do not override `USERPROFILE`, `APPDATA`, or `LOCALAPPDATA`. Do not write directly to `.ai` state; use the provided hub and CLI paths. Never rename shared hook scripts in `_sys\hooks\` without updating every caller and rerunning dependency checks.

## AI Collaboration References

AI peer behavior is configured outside this contributor guide. Use `PROTOCOL.md` for collaboration rules, `_sys/ai/protocol.json` for machine-readable policy, `_sys/ai/orchestration.json` for node invocation (`cc`, `ca`, `gc`, `ag`, `cx`), and `_sys/docs/workspace-environment.md` for peer configuration, tools, skills, and plugin layout.
