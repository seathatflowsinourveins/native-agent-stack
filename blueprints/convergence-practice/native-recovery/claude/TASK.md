Perform this tiny owned recovery fixture using only Bash. Do not delegate, inspect
unrelated files, modify scripts, install tools, change settings, or use background
commands. First run exactly `python3 stage.py checkpoint` and wait for its result.
Then run exactly `python3 stage.py wait` with a 120000 ms Bash timeout and no
background option. The supervisor will deliberately interrupt that unfinished
command and end this CLI process. After the same native session is resumed, run
only `python3 stage.py finalize` and report its digest and execution count.
Never rerun checkpoint creation, and never run finalize before the resumed turn.
