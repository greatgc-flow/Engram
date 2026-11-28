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
