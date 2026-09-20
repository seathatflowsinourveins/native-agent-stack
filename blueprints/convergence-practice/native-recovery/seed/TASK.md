# Native tool-turn recovery fixture

Use only the supplied `recovery_step` tool for this small synthetic task. Do not
delegate, inspect unrelated files, use a shell, install tools, or change settings.

Call `checkpoint` once to create the durable result. Then call `wait` once; the
coordinator deliberately leaves this native tool request unfinished and interrupts
the turn. After the coordinator reconnects this same thread, continue from the
existing checkpoint by calling `finalize`. Never repeat the checkpoint. Report
the returned digest and execution count concisely. This is a recovery check, not
a coding or token-savings comparison.
