# Fix-round preregistration (written before running fix-round commands)

Written from cwd <owned-worktree> (the owned worktree),
before executing any of the commands below, in response to independent Opus
review findings on the obs-compare receipt.

## c3 sandbox-runtime — egress-denial re-test
Opus review: sandbox-runtime was picked by the Codex lane to confine research
workers (deny broker execution authority / outbound network), not to wrap the
always-on collector. The row requirement text is "...retain scoped telemetry,
failed attempts and recoverable state without granting research workers
broker execution authority." The discriminating test for c3's actual selected
role is: does `srt` deny OUTBOUND (egress) network access from a sandboxed
worker process by default, and does the original inbound-unreachable result
instead confirm the network namespace isolation working as designed (not a
regression)?

Expectation: (a) `srt -c '<curl to an external https host>'` with default
settings (empty allowedHosts) will fail/timeout, since bwrap's --unshare-net
plus srt's own network-restriction (deny by default, no allowedHosts) should
block or intercept the sandboxed process's own outbound requests; (b) adding
that host to allowedHosts in an -s settings file will let the same curl
succeed, demonstrating srt's egress control is real and controllable, not an
accidental total network drop.
Pass criteria: (a) curl exits non-zero or hangs to timeout with no successful
HTTP response from inside the default sandbox; (b) with the host allow-listed,
curl exits 0 with a real HTTP response.
This will be run with cwd fixed to the owned worktree
(<owned-worktree>) to avoid the previous run's
deny-path enumeration touching the coordinator's main checkout
(<coordinator-checkout>).

## c8 restic — hot/live backup under concurrent writes
Opus review: the original restic test stopped Prometheus and Loki (clean
SIGTERM) before backing up, i.e. a cold backup of stopped stores, which does
not support the receipt's claim of closing the "live_databases 0" limitation.
Discriminating re-test: run `restic backup` against Prometheus's and Loki's
data directories WHILE both processes stay running and continue accepting
new writes throughout the backup (a genuine hot/live backup), then restore
into an empty target and compare parity against a live query on the
still-running originals.
Expectation: `restic backup` will either (a) succeed and later restore data
consistent with everything ingested up to some point at or before backup
completion (WAL/segment-boundary consistency, not necessarily including the
very last in-flight write), or (b) show visible inconsistency/corruption in
the restored data. This receipt will report whichever is observed rather
than assume a clean result.
Pass criteria: restic backup/check/restore exit codes and output quoted
verbatim; restored data is queried and compared against what was known to be
ingested before vs. during the backup window; any missing or corrupted
segment is reported, not hidden.
