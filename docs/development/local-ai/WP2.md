# WP2 local Python inventory

The first public WP2 commands reuse the WP1 registry and physical system root. Run `engram python list [--json]` to read the legacy binding, registry revision and active builds by series. Run `engram python where [3.MINOR] [--json]` to resolve an existing executable. With no series, where selects the legacy venv. A selected series resolves only its registered active build. A missing executable, invalid registry or unregistered series returns exit 1. Usage errors return 2. Successful JSON responses return 0.

The commands require the installed Engram dispatcher. Static help is available before setup. Both commands are offline, acquire no mutation lock, and perform no automatic installation or host Python fallback. List reports registry records even if a recorded executable later disappears. Where verifies file presence; it does not execute or qualify the interpreter.

RED observed five CLI failures on the WP1 parent and three accelerator inventory failures before implementation. The Windows bootstrap gate invokes both public commands and checks the physical venv and lifecycle state file bytes. T61 installation, T62 managed isolated environments, T63 child execution and selection, and full T65/T66 host and dependency gates remain open.

The first Windows run observed one Microsoft Hyper-V Video controller and kept inference and available memory unverified. Its parser/help comparison failed because the new command was missing from the table of public parser entry points. Adding the real Python parser to that table retains the exact-option equality check for every verb. [Initial Windows run](https://github.com/greatgc-flow/Engram/actions/runs/46090570703).

## Explicit interpreter execution

`engram python run [3.MINOR] -- PYTHON_ARGS` resolves the active build of the selected minor. With no selector it resolves the existing default venv. It starts an absolute executable with an argument list, the caller's working directory, and inherited standard streams. The selected interpreter directory leads the child's PATH. Engram runtime roots and the inherited active venv and Conda roots are excluded from the remaining PATH. Python, pip, uv and npm configuration overrides are scrubbed from the child environment. Python user-site imports are disabled by default. Use `-m pip` when addressing the selected interpreter's pip. The parent environment stays available to its original shell.

A missing or unregistered interpreter returns exit 1. Invalid syntax returns 2. The existing lifecycle lock and journal are checked before launch. A held lock or pending recovery returns 14. A started child returns its own result, including 75, which remains reserved for runner handoff on Engram maintenance verbs. Local execution uses the permissions of the caller.

The Windows shell matrix checks CMD, PowerShell and Git Bash with the bootstrapped legacy venv. A disposable working directory and child arguments exercise spaces, Korean and a literal `--help` passed to the script. Local synthetic tests exercise explicit registered-build selection, the cleaned child environment, an unregistered series, argument boundaries and exit status. Project pins, child shell activation, installer apply and managed dependency creation remain separate WP2 gates.

## Selective installation

`engram python install 3.14 3.13 --dry-run --json` returns the proposed series, exact version, published SHA-256, and archive filename. Online mode selects stable supported series whose source version and verified Windows x64 publisher inventory agree. Preview may fetch public metadata and leaves the installation and archive cache untouched. A preview's READY status means the candidate can proceed to full verification on apply. It carries no runtime test result. `--all-supported` selects the eligible series in the queried provider scope. Existing active builds are reported as INSTALLED. A recorded build with a missing executable stops the selected batch. Install never changes an installed series to a different patch.

`--offline --cache-dir DIR` uses the checked-in reviewed pins and files in DIR. The default directory is `_sys/data/setup-files/python-archives`. Copy the exact files from the pinned [Python Build Standalone release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261124) or a previously verified cache. `_sys/defaults/python-offline-artifacts.json` identifies the pinned builds and their publisher digests. Its support cutoff is the last complete month before the published CPython EOL month. Offline mode checks this bound and can use older patches. Use current publisher discovery to assess patch freshness. [CPython lifecycle schedule](https://devguide.python.org/versions/).

Use `--yes` for explicit noninteractive approval. Otherwise installation previews the exact artifact and prompts on a terminal. EOF and negative responses stop before staging. Offline missing-cache and unavailable-selection outcomes keep the entire batch unapplied. Exit codes follow the shipped help and registry journal results.

Each new archive is privately copied and checked against the approved length, digest, platform and layout before extraction. The installed executable must create a temporary venv whose interpreter, CPython patch, AMD64 platform, ABI, pip path, OpenSSL, SQLite and ctypes match. An offline pip check completes the probe. Staging uses unique managed directories and leaves the existing default binding, environment and launcher paths available. Ordinary staging failure removes only the builds it created. After publication begins, staged paths are kept available for registry recovery. A crash before publication or a concurrent CAS refusal can leave an unregistered build directory. WP3 will reconcile such directories after ownership and reference checks. The active registry never advertises an unstaged build.

The offline native gate tests dry-run, missing archive, selected single install, a mixed installed/new batch, duplicate application as a no-op, and actual execution of both registered versions and parallel creation of two independent project venvs. The install-time smoke venvs are temporary. To create a project environment from a verified extra interpreter, use `engram python run 3.14 -- -m venv .venv`. Managing consumer dependency locks and rebinding app environments have their own gates.

Example offline preview and apply from the same cache:

```text
engram python install 3.13 3.14 --offline --cache-dir D:\python-cache --dry-run --json
engram python install 3.13 3.14 --offline --cache-dir D:\python-cache --yes
engram python run 3.13 -- --version
engram python run 3.14 -- --version
```

## Project pins and online install proof

`engram python pin 3.14` records the selected build ID, series, artifact digest and Engram installation identity in `.engram-python.json`. The pin lives at the closest Git root, including a worktree with a `.git` file. Outside Git, it applies to the current directory. Invoking the command from a nested Git directory targets that repository's root. Repeating an identical pin is idempotent. An explicit `unpin` is required before changing it. The Engram lock serializes pin mutations from the same installation.

`where` and `run` use the pinned build, even when a newer patch becomes active in the same series. Supplying that same series still selects the exact pinned build. A different explicit series, a malformed pin, a foreign installation, a missing executable or a mismatched digest stops the command. Unpin accepts a valid Engram pin owned by the current installation even if the pinned build is unavailable. The operation preserves other tool files such as `.python-version` and project dependency metadata. Engram does not interpret external tool pins or package constraints in this increment.

Pins identify local installations. Restore and move must preserve installation identity and the referenced build to keep a pin usable. WP3 retirement must account for project-held references before removing a retained build, including pins outside the portable root.

The disposable Windows test invokes pin, where, run and unpin from a nested Korean project path against the installed 3.13.18 fixture. It also exercises a fresh 3.12 online install with public source and provider metadata, downloads the exact approved archive, and runs the selected build. CI records the actual observed version. Online preview remains distinct from a successful installation.
