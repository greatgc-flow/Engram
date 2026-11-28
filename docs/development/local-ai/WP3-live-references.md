# WP3 live interpreter references

`engram python doctor [3.MINOR] --scan-processes --json` opts into a local
process snapshot through Engram's existing psutil dependency. An observed
exact registered interpreter or app venv launcher adds `LIVE_PROCESS` and
protects the build, including a retained patch whose old project pin has
been removed. Matching uses normalized executable paths and includes
managed windowed launchers. Results contain the build reference and
coverage; process IDs, executable paths and command lines stay out of the
report. The ordinary doctor avoids process enumeration.

A sample has partial coverage. Processes can race the snapshot, access can
be denied and aliases or unmanaged environments can evade matching. A
missing observation leaves retirement unverified. This evidence covers
observed live processes in T72. External project and backup reference
coverage, quiescence at removal and the destructive removal workflow remain
open.

The [Windows patch job](https://github.com/greatgc-flow/Engram/actions/runs/46143470926/job/140974316170)
passed with an actual retained 3.14.8 Python child and an active 3.14.10
series. The build was PROTECTED while the process was observed and
UNVERIFIED after it exited. The job passed 2,626 tests and 154 subtests.

## Explicit backup references

`engram python doctor --backup PATH.zip --json` checks the reference metadata
of a named runtime recovery ZIP with the same installation identity. Pass
`--backup` up to 16 times. Relative paths use the caller's directory. A
registered build matching a saved ID or artifact identity receives
`BACKUP_REFERENCE`. An unavailable archive is reported by input number
without printing its filesystem path.

This step reads bounded archive metadata, including the registry and its
locks. It does not read artifact payloads or prove a restore would succeed.
Coverage is partial when at least one input validates. No result establishes
that all backup copies or externally managed projects are known.

The [combined Windows job](https://github.com/greatgc-flow/Engram/actions/runs/46151235477/job/140998113997)
passed at `e2c5b35e7e1bd875eb282e5c2ff99c5cc813b902`. A retained CPython
3.14.8 build became unverified after its process exited, then gained
BACKUP_REFERENCE protection when the original runtime ZIP was supplied.
The same run verified the full offline pack and passed 2,645 tests and
154 subtests.
