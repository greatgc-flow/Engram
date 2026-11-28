# WP2 local Python inventory

The first public WP2 commands reuse the WP1 registry and physical system root. Run `engram python list [--json]` to read the legacy binding, registry revision and active builds by series. Run `engram python where [3.MINOR] [--json]` to resolve an existing executable. With no series, where selects the legacy venv. A selected series resolves only its registered active build. A missing executable, invalid registry or unregistered series returns exit 1. Usage errors return 2. Successful JSON responses return 0.

The commands require the installed Engram dispatcher. Static help is available before setup. Both commands are offline, acquire no mutation lock, and perform no automatic installation or host Python fallback. List reports registry records even if a recorded executable later disappears. Where verifies file presence; it does not execute or qualify the interpreter.

RED observed five CLI failures on the WP1 parent and three accelerator inventory failures before implementation. The Windows bootstrap gate invokes both public commands and checks the physical venv and lifecycle state file bytes. T61 installation, T62 managed isolated environments, T63 child execution and selection, and full T65/T66 host and dependency gates remain open.

The first Windows run observed one Microsoft Hyper-V Video controller and kept inference and available memory unverified. Its parser/help comparison failed because the new command was missing from the table of public parser entry points. Adding the real Python parser to that table retains the exact-option equality check for every verb. [Initial Windows run](https://github.com/greatgc-flow/Engram/actions/runs/46090570703).

## Explicit interpreter execution

`engram python run [3.MINOR] -- PYTHON_ARGS` resolves the active build of the selected minor. With no selector it resolves the existing default venv. It starts an absolute executable with an argument list, the caller's working directory, and inherited standard streams. The selected interpreter directory leads the child's PATH. Engram runtime roots and the inherited active venv and Conda roots are excluded from the remaining PATH. Python, pip, uv and npm configuration overrides are scrubbed from the child environment. Python user-site imports are disabled by default. Use `-m pip` when addressing the selected interpreter's pip. The parent environment stays available to its original shell.

A missing or unregistered interpreter returns exit 1. Invalid syntax returns 2. The existing lifecycle lock and journal are checked before launch. A held lock or pending recovery returns 14. A started child returns its own result, including 75, which remains reserved for runner handoff on Engram maintenance verbs. Local execution uses the permissions of the caller.

The Windows shell matrix checks CMD, PowerShell and Git Bash with the bootstrapped legacy venv. A disposable working directory and child arguments exercise spaces, Korean and a literal `--help` passed to the script. Local synthetic tests exercise explicit registered-build selection, the cleaned child environment, an unregistered series, argument boundaries and exit status. Project pins, child shell activation, installer apply and managed dependency creation remain separate WP2 gates.
