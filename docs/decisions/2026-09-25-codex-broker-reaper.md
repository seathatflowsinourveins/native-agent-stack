# Decision: guarded reaper for orphaned openai-codex plugin brokers (2026-09-25)

**Scope:** stopping leaked `app-server-broker.mjs` processes the openai-codex
Claude Code plugin (installed under `~/.claude/plugins/cache/openai-codex/`)
leaves running after a crashed session or an abandoned workflow-child
worktree, without touching any broker a live session still owns. The tool is
[`../../adoption/tools/codex-broker-reaper`](../../adoption/tools/codex-broker-reaper),
its tests are
[`../../tests/test_codex_broker_reaper.py`](../../tests/test_codex_broker_reaper.py),
and the (drafted, not installed) systemd templates are under
[`../../adoption/templates/systemd/`](../../adoption/templates/systemd/). No
host deployment is part of this decision: the coordinator installs the
systemd unit and runs `--apply` for real after review.

## Context

**As given by this rollout's task brief (2026-09-25), not independently
re-fetched from GitHub in this session:** upstream
(`openai/codex-plugin-cc`) tracks this gap in issues #543, #605, #380, #767,
and #743 (pid reuse making a stale broker record point at the wrong live
process), and in open, unmerged PRs #680 (idle timeout) and #660 (reap
leaked sessions), plus #490; nothing has merged, and upstream `main` has had
0 commits since the installed v1.0.6. Separately, on this rollout's host, 13
leaked brokers were observed holding roughly 23 GiB before being stopped by
hand over the `broker/shutdown` RPC, which worked cleanly.

**Verified directly in this session, from the installed plugin's own source
(openai-codex 1.0.6) and this host's real plugin data directory:**

- `scripts/lib/broker-lifecycle.mjs` (`spawnBrokerProcess`) starts one
  detached `app-server-broker.mjs serve --endpoint unix:<sock>` per
  workspace, with the broker's OS working directory set to that workspace
  root. Only `scripts/session-lifecycle-hook.mjs`'s `SessionEnd` handler
  ever sends it `broker/shutdown` (newline-delimited JSON-RPC
  `{"id":1,"method":"broker/shutdown","params":{}}`) — a crashed session, or
  any worktree whose session never reaches a normal `SessionEnd`, leaves the
  broker (and the `codex app-server` child it owns) running indefinitely.
- The plugin's own job-status vocabulary
  (`scripts/lib/tracked-jobs.mjs`, `scripts/lib/job-control.mjs`,
  `scripts/session-lifecycle-hook.mjs`) is exactly `{queued, running}`
  (non-terminal) and `{completed, failed, cancelled}` (terminal); nothing
  else appears in the source.
- `broker.json` (per workspace, under
  `~/.claude/plugins/data/<plugin-data-dir>/state/<workspace-slug>-<hash>/`)
  holds `endpoint`, `pidFile`, `logFile`, `sessionDir`, `pid` — no
  `workspaceRoot`. `state.json` holds `jobs[]`, and a job that recorded one
  carries `workspaceRoot`, but a broker that started and never ran a job has
  an empty `jobs[]` and so no recorded workspace root anywhere in
  `state.json`. This is why the tool reads the broker's own live
  `/proc/<pid>/cwd` for guard (c) instead of `state.json`.
- On this host, `~/.claude/plugins/data/codex-openai-codex/state/` (the
  installed plugin's own data-directory naming; `*codex*` matches it)
  currently holds 17 `broker.json` files. Every one of their recorded pids
  was already dead (no live process at that pid at all) at review time,
  which is why `--list` against this host's real state (read-only; see
  `adoption/tools/README.md`) reports 0 eligible: guard (a) alone already
  refuses all 17, before guards (b)–(d) are even evaluated.
- A live `claude`/`codex` process is detected by `comm` (both are native
  binaries on this host, not wrapper scripts, so `comm` is their own name),
  with cmdline `argv[0]`'s basename as a second signal. This was checked by
  hand: `~/.local/bin/claude` is an ELF binary (`comm` = `claude`), and a
  Python script executed directly does **not** get its own name as `comm`
  (the kernel sets `comm` from the interpreter it re-execs via the shebang,
  confirmed by spawning a script literally named `claude` and reading
  `/proc/<pid>/comm`, which read back `python3`) — which is why the test
  suite's live-session stand-in sets `comm` directly with
  `prctl(PR_SET_NAME)` instead of relying on a script's filename.

## Decision

1. Ship `adoption/tools/codex-broker-reaper` (Python 3 stdlib): `--list`
   (default, read-only) and `--apply` evaluate every broker under
   `~/.claude/plugins/data/*codex*/state` (or an explicit `--state-root`)
   against four guards, all required: (a) `/proc/<pid>/cmdline` still names
   `app-server-broker.mjs serve` with the exact recorded endpoint; (b) no
   job in `state.json` has a non-terminal status, and an unrecognized status
   blocks reaping rather than being assumed safe; (c) the workspace
   directory (from the broker's own live `/proc/<pid>/cwd`) no longer
   exists, or no live `claude`/`codex` process has a cwd equal to or under
   it; (d) the broker is older than `--min-age` (default 1800s), measured
   from `/proc/<pid>/stat`'s `starttime`. Action is the `broker/shutdown`
   RPC (5s), then up to 15s waiting for the broker and its OS children to
   exit; `--escalate` only adds a process-group `SIGTERM` after that wait
   fails and after re-checking guard (a) again (the pid could have been
   reused during the wait). The tool never sends SIGKILL. `--receipt PATH`
   writes the same JSON report to a file. Exit 0 normally, 2 if an eligible
   broker was not confirmed stopped.
2. Ship drafted, not-installed systemd user templates
   (`adoption/templates/systemd/codex-broker-reaper.{service,timer}`):
   hourly (`OnBootSec=10min` + `OnUnitActiveSec=1h`), `Persistent=true` so a
   missed run still happens once shortly after the next start, running
   `--apply --receipt %h/codex-ecosystem/state/codex-broker-reaper/last.json`.
3. Ship `tests/test_codex_broker_reaper.py` (synthetic fixtures throughout;
   see "Measured" below) and the `adoption/tools/README.md` section cross-
   referencing this decision.

## Alternatives rejected

- **Patch the plugin with upstream PR #680 (idle timeout) locally:**
  rejected as an unmerged third-party patch to a vendored plugin — it would
  have to be re-applied across every plugin update, and the review here has
  no visibility into whether that PR is even the direction upstream will
  actually take.
- **Manual cleanup** (what produced the 23 GiB, 13-broker observation
  above): rejected as recurring — it depends on someone noticing memory
  pressure and knowing the RPC shutdown sequence, on every affected host,
  indefinitely.
- **Trust `state.json`'s job-level `workspaceRoot` instead of
  `/proc/<pid>/cwd` for guard (c):** rejected because it is simply absent
  for a broker that started and never ran a job (empty `jobs[]`), which is a
  normal case, not an edge case, for a workflow-child worktree whose broker
  spun up but whose session ended before any codex call completed. The
  broker's own live cwd is available exactly whenever guard (a) already
  needed the pid to be alive, and is the OS's ground truth for where
  `spawnBrokerProcess` actually put it, rather than a value the plugin
  chose to persist.
- **SIGKILL as a default or non-opt-in path:** rejected; this tool only
  ever asks the broker to shut itself down cleanly (closing its `codex
  app-server` child through `CodexAppServerClient.close()`) or, opt-in,
  sends SIGTERM to a process group re-verified to still be that broker.
  Killing indiscriminately would risk an in-flight `codex app-server`
  operation the RPC path lets exit cleanly.

## Evidence that would overturn this decision

- Upstream releases an idle-timeout or leaked-session-reap fix (any of
  #680, #660, or a new mechanism) **and** a week of this tool's own
  `--list` reports on a real host shows no orphan older than `--min-age`:
  remove the reaper.
- A production `--apply` run is shown to have treated a broker of an
  actually-live session as eligible (a false negative in guard (c)'s live-
  process scan, or a `comm`/`argv[0]` detection gap for some future
  wrapped `claude`/`codex` invocation): tighten or disable guard (c)'s
  session detection pending a fix, and re-derive the `claude`/`codex`
  process-name check from whatever that host's actual invocation looks
  like, rather than only this host's ELF-binary observation.
- A real `--escalate` run against a genuinely stuck broker shows the
  process-group `SIGTERM` either failing to reach the `codex app-server`
  child or reaching an unrelated reused pid despite the guard-(a) recheck:
  revisit the recheck window or drop `--escalate` until fixed.

## Measured (evidence class: local integration, synthetic fixtures)

- `python3 -m unittest tests.test_codex_broker_reaper -v`: 19 tests, all
  passing. Every guard is exercised against a real spawned process, not a
  mock: a small Python stand-in plays the broker (a genuine unix-socket
  server started from a script file literally named `app-server-broker.mjs`
  so its real `/proc/<pid>/cmdline` matches guard (a), answering
  `broker/shutdown` like the plugin's own broker) with its OS cwd set to a
  synthetic workspace directory; a separate stand-in simulates a live
  `claude`/`codex` session by forcing its own `comm` via
  `prctl(PR_SET_NAME)`. Covered: guard (a) against a dead pid and against a
  live-but-unrelated pid (the pid-reuse case, using the test runner's own
  pid rather than racing real OS pid reuse); guard (b) with a `running` job
  blocking and a `completed` job allowing, plus an unrecognized status
  blocking; guard (c) with a live session under the workspace root (and
  under a *subdirectory* of it) blocking, an unrelated session elsewhere
  not blocking, and a deleted workspace directory allowing; guard (d) with
  a fresh process failing a large `--min-age` and passing `--min-age 0`,
  plus a direct check that `process_start_epoch` agrees with wall-clock
  time within a couple of seconds; `--apply` actually stopping a broker over
  the real RPC and observing its exit; `--escalate` sending SIGTERM only
  after the RPC wait fails; the escalation's guard-(a) recheck being
  skipped (via a monkeypatched cmdline reader, deterministic rather than
  racing real pid reuse) with the real process left untouched; a stuck
  broker with no `--escalate` given exiting 2 and remaining alive (proving
  no signal is sent without the opt-in); and the full receipt JSON shape,
  written to both stdout and `--receipt PATH` identically.
- `python3 adoption/tools/codex-broker-reaper --list` against this host's
  real `~/.claude/plugins/data/codex-openai-codex/state` (read-only): 17
  brokers found, 0 eligible, every one refused at guard (a) (dead pid).
  This is a one-host, one-time observation of a read-only run, not a
  standing measurement.
- `scripts/validate.py` and `scripts/validate_foundation.py` (this
  repository's own publication/manifest integrity checks) still pass with
  every file this decision adds present.

**Not tested:** `--apply` or `--escalate` against a real broker on any host
(only against synthetic ones); the systemd templates actually installed,
loaded, or started anywhere (`@REPOSITORY@` is an unrendered placeholder);
behavior on a Windows/macOS variant of the plugin (`pipe:` endpoints — the
tool recognizes only `unix:` and reports `unsupported_endpoint` otherwise);
and any interaction with a real, in-progress `codex` job (every "running
job blocks eligibility" case above is a synthetic `state.json`, not a real
in-flight task).
