# Master Refactor Plan V5: Zero-Code Composable MECE Architecture
> Target: Complete System Re-architecture for Extreme Decoupling, JSON-ification, and Lazy Loading.
> Status: PLANNING STAGE (Awaiting User Sign-off)

## 1. Architectural Vision & Core Principles
1. **Strict Separation of Concerns (MECE)**:
   - **Code (`_sys/core/`)**: Pure deterministic I/O, routing, error handling. NO business logic, NO prompt content, NO hardcoded paths.
   - **Configuration (`_sys/ai/config/`)**: All paths, ranges, limits, environment variables, and General-Specific bindings exist here as pure JSON.
   - **Instructions (`_sys/docs-v2/`)**: Semantic behavior and human/AI-readable directives.
2. **Zero-Code Orientation**: System behavior changes must occur via JSON edits or Markdown updates, not Python/Bash edits.
3. **Lazy Loading**: Strictly conserve tokens and memory by loading components and documents *only* precisely when required by the routing/binding JSON.

---

## 2. Global vs. Workspace Scoping
To satisfy the requirement for cross-workspace and workspace-local scopes:
- **`_shared/` (Global Common Space)**: Located at the portable drive root. Holds generic skills, tools, and configurations that apply to *all* workspaces.
- **`_sys/templates/workspace-base/` (Base Template)**: The canonical skeleton copied when a new workspace is initialized. Ensures standardized `.ai/` and `config/` subdirectories.
- **`{workspace_name}/.ai/local/` (Workspace Local Scope)**: Configurations, overrides, and specialized instructions used *only* within this specific workspace. Overrides `_shared/` via the JSON binding layer.

---

## 3. Configuration & Path Centralization (The JSON-ification)
Currently, paths like `%SYS_DIR%` are hardcoded in batch files, and Python logic combines paths. 
- **Action**: Create a universal environment.json in sys/config.
- **Structure**:
  ```json
  {
    "paths": {
      "base": "{ROOT_DRIVE}",
      "sys": "{base}/_sys",
      "shared": "{base}/_shared",
      "workspace_template": "{sys}/templates/workspace-base"
    },
    "env_vars": {
      "PYTHONUTF8": "1",
      "NPM_CONFIG_PREFIX": "{sys}/env/nodejs/npm-global"
    }
  }
  ```
- **Execution**: A single bootstrap script (`boot.py` or equivalent) reads this, resolves templates dynamically (no code-level concatenation), sets `os.environ`, and launches the bound interfaces.

---

## 4. General-Specific Interface Pattern & JSON Binding
To satisfy the requirement that all operations are performed through generic interfaces and specific traits are handled in lower layers:
- **Action**: Define `_sys/core/interfaces/` with purely abstract base classes (e.g., `BasePeerAdapter`, `BaseTool`).
- **JSON Binding**: Create bindings.json in sys/ai (or extend orchestration.json):
  ```json
  "interface_bindings": {
    "peer_execution": {
      "cc": { "adapter_class": "ClaudeAdapter", "pattern": "std_cli_stdio" },
      "ag": { "adapter_class": "AntiGravityAdapter", "pattern": "std_cli_pty" }
    }
  }
  ```
- **Refactoring Specifics**: Even if `cc` and `ag` have different internal CLI flags, their interaction pattern must be normalized to `std_cli`. Any unique quirks are defined as JSON parameters (e.g., `"requires_pty": true`), completely eliminating `if peer == 'ag':` hardcoding in Python.

---

## 5. Error Visibility & Traceability
To satisfy the requirement that users must clearly notice any abnormalities:
- **Action**: Implement a Global Exception Trap in the entry point.
- **Behavior**: Instead of silent failures or buried Python tracebacks, any unhandled exception triggers a `[SYSTEM_FATAL_ERROR]` block.
- **Output**: Dumps the Stack Trace + Environment State + 5-Whys Root Cause Analysis Template directly to the user's console (in Korean, per INV-19 console rules).

---

## 6. Implementation Roadmap (Strict TDD Execution)
We will execute this plan sequentially via strict **TDD (Test-Driven Development)**. No code will be written without a failing test first.

* **Phase 1: Configuration Harvesting**
  * *TDD Step*: Write `test_env_loader.py` asserting that generic paths resolve correctly from JSON.
  * Extract all magic numbers, hardcoded paths, and environment variables from `_sys/*.bat` and `_sys/core/*.py`.
  * Centralize into the planned environment.json file.
* **Phase 2: Base Templates & Scoping**
  * *TDD Step*: Write WSB (Windows Sandbox) tests to simulate a fresh workspace initialization.
  * Create `_shared/` and `_sys/templates/workspace-base/`.
  * Update `install.bat` and `hub.py` to recognize local vs. shared scoping via JSON precedence.
* **Phase 3: The Binding Layer**
  * *TDD Step*: Write mock tests for `BasePeerAdapter` to ensure JSON bindings produce the exact correct CLI strings before modifying `hub.py`.
  * Create the planned bindings.json file.
  * Strip `hub.py` of all peer-specific `if/else` logic. Refactor into pure polymorphic interfaces driven by JSON.
* **Phase 4: Error Visibility**
  * *TDD Step*: Write a test that intentionally throws an exception and asserts the output matches the `[SYSTEM_FATAL_ERROR]` 5-Whys format.
  * Inject the Global Exception Trap.
* **Phase 5: Lazy Optimization**
  * *TDD Step*: Write a token-counting test to ensure context load size remains below the threshold for specific tasks.
  * Audit token usage. Ensure context loading is fully lazy and bound to specific JSON-triggered events.

---

## 7. Edge Cases & Exceptions (Noise Log)
*Items that do not currently fit this MECE structure will be tracked here during implementation.*
- **Expected Edge Case**: The Windows `cmd.exe` bug with Korean characters (`chcp 65001`) cannot be fixed via JSON configuration. The workaround (relay batch files via English-only paths) must remain as explicit deterministic Code (plumbing), fully abstracted away from the logic layer.
