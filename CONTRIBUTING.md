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

- **Run all tests (unit + lifecycle):**
  ```cmd
  _sys\tests\run-tests.bat --all
  ```

- **Run pre-commit checks:**
  Static and hygiene checks live in `_sys/checks/` (e.g. `check_encoding.py`, `check_root_hygiene.py`, `check_unreferenced_functions.py`).

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
- **Measured Claims**: Test real Windows behavior empirically rather than reasoning or guessing.

---

## 5. Submitting Changes

1. Ensure the entire unit test suite passes cleanly with zero failures.
2. Ensure new files and docs adhere to `CONVENTION.md` and pass consistency checks.
3. Open a Pull Request targeting the `main` branch with a clear summary of changes and testing evidence.
