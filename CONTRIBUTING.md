# Contributing to Engram

Engram is a clean, portable Windows development environment bundler. Contributions are welcome! This document covers setting up a local development checkout, running the test suite, and adhering to the repository's branch, commit, and coding conventions.

---

## 1. Development Checkout Setup

### Prerequisites
- Windows 10 or 11
- Git for Windows

### Setup Steps
1. **Clone the repository:**
   ```bash
   git clone https://github.com/greatgc-flow/Engram.git
   cd Engram
   ```

2. **Bootstrap the portable environment:**
   Run `engram` (or `engram.cmd`) to download and initialize the pinned portable runtimes (Python, Node.js, Git, CLI tools):
   ```cmd
   engram
   ```

3. **Install dev/test dependencies:**
   Test dependencies (`pytest`, `hypothesis`, `pytest-timeout`) are kept separate from the distributed runtime. Install them into the portable venv:
   ```cmd
   _sys\env\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   ```

> [!WARNING]
> **Dev checkout vs. installed copy**: `engram` on your `PATH` executes the **installed** copy (typically `D:\PkgDev\_sys`), **not** your development checkout. When testing changes in a local dev checkout, call module code directly (e.g. `python -m <module>` or via `_sys\env\venv\Scripts\python.exe`).

---

## 2. Running Tests

Always verify your changes against the test suite before submitting:

- **Run all unit tests:**
  ```cmd
  python -m pytest _sys/tests/unit
  ```
  or via the batch runner:
  ```cmd
  _sys\tests\run-tests.bat --unit
  ```

- **Run a specific test file:**
  ```cmd
  python -m pytest _sys/tests/unit/test_doc_consistency.py -v
  ```

- **Run the full test suite directly (~9 min):**
  ```cmd
  python -m pytest -q _sys/tests -p no:cacheprovider
  ```
  or via the batch runner:
  ```cmd
  _sys\tests\run-tests.bat --all
  ```

- **Test execution permissions**: Pytest temp directories have owner-only ACLs, so peers / sandbox agents cannot run the test suite. Run tests directly from your own interactive maintainer session.

- **Known one-off flakes**: `test_upgrade_gate_offline` and `test_wave_c1` are known one-off flakes that pass on rerun.

- **Run pre-commit checks:**
  Static and hygiene checks live in `_sys/checks/` (e.g. `check_encoding.py`, `check_root_hygiene.py`, `check_unreferenced_functions.py`).

- **Release gate:** For canonical release verification procedures, clean-room gates, and publishing workflows, see [`docs/release_gate.md`](docs/release_gate.md).

---

## 3. Branching & Commit Conventions

### Branch Naming
Create branches from `main`. Use lowercase kebab-case prefixed by category and purpose or date:
- `fix/<short-description>-YYYY-MM-DD` (e.g. `fix/cli-help-and-vscode-update-mode-2026-09-23`)
- `feat/<feature-name>` (e.g. `feat/sys-restructure`)
- `docs/<topic>-YYYY-MM-DD` (e.g. `docs/feedback-loop-2026-09-23`)
- `test/<scope>`
- `chore/<topic>`

### Commit Messages
We follow **Conventional Commits** (`<type>(<scope>): <summary>`):
- **Types**: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`
- **Scopes**: component or subsystem, e.g. `cli`, `doctor`, `updater`, `provisioner`, `registrar`, `tests`, `lifecycle`
- **Format**: Imperative mood, lowercase, concise, in English:
  - `fix(cli): working --help everywhere + disable VS Code's own update checker (#2)`
  - `feat(updater): support agy self-update, runtime discovery providers, and safety guards (v3.3.6)`
  - `test(lifecycle): add end-to-end MECE state machine round-trip test`
  - `docs(audit): synchronize README, doctor remediation verbs, and unit tests`

---

## 4. Coding Standards

All code and documentation must strictly adhere to [`CONVENTION.md`](CONVENTION.md):

- **Language Policy (§1)**: English only for all source code, JSON artifacts, configuration files, comments, commit messages, and documentation.
- **Windows Batch Rules (§2)**:
  - All `.bat` files must be UTF-8 (No BOM) without Korean text or `chcp`.
  - Special character safety: Never re-embed absolute paths containing `&`, `%`, `^`, or `!` into command strings (use relative paths or direct binary resolution).
- **Environment Isolation (§4)**: Never override `USERPROFILE`, `APPDATA`, or `LOCALAPPDATA`. Route tool-specific data and caches into `%ENV_DIR%` or `%DATA_DIR%`.
- **CLI Help Contract**: All help files under `_sys/core/help/` must be pure ASCII and <=80 columns wide. Help files are embedded verbatim in [`docs/cli_reference.md`](docs/cli_reference.md) and enforced by [`_sys/tests/unit/test_cli_help_contract.py`](_sys/tests/unit/test_cli_help_contract.py).
- **Root Directory Hygiene**: Never create an `_archive` directory in the Engram root (it is a legacy-layout marker that breaks updater tests). Never create scratch or temporary files in the repository root (tests use `tmp_path`).
- **Measured Claims**: Test real Windows behavior empirically rather than reasoning or guessing.

---

## 5. Submitting Changes

1. Ensure the entire unit test suite passes cleanly with zero failures.
2. Ensure new files and docs adhere to `CONVENTION.md` and pass consistency checks.
3. Open a Pull Request targeting the `main` branch with a clear summary of changes and testing evidence.

Operational failures should include `engram doctor --json`, the command and exit
code, and the relevant file under `_sys/data/logs/` or
`_sys/data/state/update/`. Never attach `.engram/` wholesale: it may contain
credentials and session data. Use the bug-report template so a failure becomes a
reproducible test or a documented limitation instead of an untracked workaround.

---

## 6. Maintainer Notes

Set `ENGRAM_TEST_OOM_GUARD=1` to opt into the test memory guard; it is off by default.

### Operational Pitfalls & Environment Constraints

- **Installed Copy vs. Dev Checkout**: `engram` on PATH runs the INSTALLED copy (`D:\PkgDev\_sys`), not a dev checkout. Always call module code directly to test development changes.
- **Root Directory Marker**: Never create `_archive` in the Engram root; it is a legacy-layout marker that breaks updater tests.
- **Test Execution & ACLs**: Pytest temp directories have owner-only ACLs, so peers cannot run tests in their sandboxes. Run them yourself:
  ```cmd
  python -m pytest -q _sys/tests -p no:cacheprovider
  ```
  (~9 min). Run the full suite after every change wave and chain with `&&` so a failing suite never commits.
- **Known Flakes**: `test_upgrade_gate_offline` and `test_wave_c1` are known one-off flakes that pass cleanly on rerun.
- **Help Files Contract**: Help files must be ASCII and <=80 columns, and are embedded verbatim in [`docs/cli_reference.md`](docs/cli_reference.md) (`test_cli_help_contract`).
- **Claude Code Project Litter**: Claude Code creates a project folder per working directory; live tests executed with a temporary `cwd` litter `.engram/claude/projects`.
- **VDI Logoff**: The VDI may force-logoff sessions; commit and push in small steps.
- **PR Merge Permissions**: An automatic permission classifier may deny `gh pr merge` after chat approval; the maintainer merges or adds an allow rule (`Bash(gh pr merge:*)`).

### Architectural Decisions & Deferrals

- **Release Recipe**: Follow the canonical release procedure as actually performed for v3.9.0/v3.9.1 in [`docs/release_gate.md#maintainer-release-recipe-v390--v391`](docs/release_gate.md). Tag push fallback for Windows credential helper / headless shells:
  ```cmd
  git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin vX.Y.Z
  ```
- **Python Update Flow (v3.9.0/v3.9.1)**: `engram update -o python [--latest] -y`. Default updates to the latest patch in the installed minor. Minor jumps need `--latest` or `--to` and run a pre-flight check (embed zip + win_amd64 wheels for `pywinpty`, `pydantic-core`, `psutil`). Because no SHA-256 is pinned for Python upstream, a warning is printed. `_sys/core/bootstrap.bat` no longer auto-bumps Python. See [`docs/env_resilience_guide.md`](docs/env_resilience_guide.md).
- **Isolation Providers**: Providers for Windows Sandbox and WSL2 exist (`engram isolation check`, [`docs/isolation_guide.md`](docs/isolation_guide.md)). `isolation run` and an AI Skill are **DEFERRED** until: a tracked request + a concrete caller/command + why existing workflows fail + a supported host for live acceptance. Isolation is not wired into release gates.
- **Cross-AI Memory Scheme Rejected**: A shared cross-AI memory folder/junction/instruction approach was tried and **REJECTED** by the owner (no directory junctions or subst drives, no standing AI instructions); do not retry. See [`docs/engram-dotdir.md`](docs/engram-dotdir.md).

### Working with AI Peers (MECE)

Engram does not maintain multi-agent collaboration rules or peer tooling pitfalls: see the PeerHub repo CONTRIBUTING "Working with AI peers".
