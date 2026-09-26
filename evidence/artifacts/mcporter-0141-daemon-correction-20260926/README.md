# mcporter 0.14.1: leftover 0.13.13 daemon found and retired (2026-09-26)

This corrects `evidence/artifacts/sota-refresh-20260925/mcporter/cutover.json`. Two of its
statements were wrong:

- The `precondition` step says "No mcporter daemon was running before the switch".
- The `post-switch use` step says "the next call started a 0.14.1 daemon".

The switch was recorded at "about 2026-09-25T20:12Z". On 2026-09-26 a read-only check found a
mcporter **0.13.13** daemon serving the production socket `~/.mcporter/daemon/user.sock`,
while `bin/mcporter` pointed at 0.14.1:

- PID `129979` started at `Fri Sep 25 16:09:42 2026` host local time (UTC-4), which is
  20:09:42Z.
- `mcporter daemon status --json` reported `startedAt` 1790366984036 ms (20:09:44Z).
- The socket's mtime is 2026-09-25 16:09:44 -0400.
- The process command line ran `tools/mcporter-0.13.13/.../cli.js daemon start --foreground`.
- Its two keep-alive servers were socraticode 1.14.0. Their `lastUsedAt` values were
  1790366984477 and 1790366985598 ms (20:09:44Z and 20:09:45Z), and `activeCalls` was 0.

## Cause (coordinator's session record, not retained here)

The coordinator's own session history shows the sequence:

1. At 20:09:11Z, `mcporter daemon status --json` ran as the precondition check.
2. At 20:09:43Z, a single command ran `echo "before:"`, then
   `mcporter --config <config> list socraticode --brief --no-oauth` through the still-linked
   0.13.13, then the relink.

That command was issued at 20:09:43.395Z. The daemon's own `startedAt` is 20:09:44.036Z,
0.6 s later. `ps` shows a start of 20:09:42, but that value has whole-second resolution and
is derived from boot time. The timing fits the daemon being started by that pre-relink
`list` call. The
precondition was therefore true when checked but stale at the switch, and the relink was at
about 20:09:4xZ, not 20:12Z. The claim that the post-switch call started a 0.14.1 daemon is
contradicted by the unchanged socket mtime and by the 0.13.13 daemon still holding it the next
day. The session record is private and not retained, so treat this cause as the coordinator's
account. The retained facts are the ones in `retire.txt`.

## Files

- `retire.txt` is the full output of the retirement run (2026-09-26 14:56:46Z–14:56:52Z UTC),
  with `$HOME` shown as `~`. In order, it records:
  1. the production `bin/mcporter` link and its version (0.14.1), and `command -v ps`
     (`/usr/bin/ps`);
  2. the daemon status before, the PID's command line and start time, its children, the
     socket mtime, and a count of held socraticode index/graph lock directories (0);
  3. two assertions: the PID is the 0.13.13 daemon, and `activeCalls` totals 0;
  4. the native `mcporter daemon stop` through 0.14.1 (exit 0, "Daemon stopped (if it was
     running).");
  5. that the PID, its children and the socket are gone;
  6. a production call, `mcporter --config <codex-ecosystem config/mcporter.json> call
     socraticode.codebase_health --no-oauth`, which exited 0 and printed "SocratiCode —
     Infrastructure Health Check:";
  7. the new daemon's status, PID `744797` running
     `tools/mcporter-0.14.1/.../cli.js daemon start --foreground`, as the single mcporter
     daemon process.
- `retire.sh` is the script that produced it. It differs from the executed copy only in the
  scratch path for the health-call output, now `${OUT:-/tmp}/mc-health.out`.

## Scope

- Only the Linux workstation `nativestack-5975wx-20260925` is covered.
- For about 18.8 h, 0.14.1 clients that went through the daemon reached a 0.13.13 daemon.
  Both versions speak daemon protocol 3, per the rollback text in `cutover.json`. This run
  did not measure whether any 0.14.1 call failed in that window. The two keep-alive servers'
  `lastUsedAt` values show no calls through them after 20:09:45Z.
- The receipt's limitation that a mixed-version daemon cutover was "not exercised" still
  holds. This run retired the old daemon; it is not a qualification of mixed-version
  operation.
- The new daemon inherited the launching shell's PATH, where `ps` is `/usr/bin/ps`, which the
  receipt's `limitations[0]` requires.
