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
  hand: `~/.local/bin/claude` is an ELF binary (`comm` = `claude`). **Corrected
  (fix round, 2026-09-25):** this section previously claimed "the kernel sets
  `comm` from the interpreter it re-execs via the shebang" — checked directly
  on this host (Linux 6.18, WSL2) and that is not what happens. A script with
  a *direct* shebang (`#!/usr/bin/python3`), executed as its own file, gets
  `comm` set to the *script's own* basename (truncated to 15 chars), not the
  interpreter's; only an `env`-mediated shebang (`#!/usr/bin/env python3`) or
  an explicit `python3 script.py` invocation yields `comm` == `python3`,
  because in both of those cases `python3` is the binary actually `execve`d.
  The test suite's live-session stand-in is spawned the second way
  (`subprocess.Popen([sys.executable, script_path, ...])`), so its `comm`
  reads back as `python3` for that reason alone, unrelated to any shebang —
  which is why it sets `comm` directly with `prctl(PR_SET_NAME)` instead of
  relying on a script's filename.

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
   hourly via `OnCalendar=hourly` (plus `OnBootSec=10min` for an early run
   shortly after boot), `Persistent=true` so a missed run still happens once
   shortly after the next start -- effective only combined with
   `OnCalendar=`, since systemd applies `Persistent=` solely to
   `OnCalendar=` timers, never to monotonic `OnBootSec=`/`OnUnitActiveSec=`
   ones (fixed in the 2026-09-25 fix round below; the timer originally
   shipped with only the monotonic triggers, silently defeating
   `Persistent=true`) -- running `--apply --receipt
   %h/codex-ecosystem/state/codex-broker-reaper/last.json`.
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

## Known limitations

- **Guard (c), review-triggered brokers in a subdirectory:** a *review*
  command's broker is spawned with the raw command cwd
  (`codex-companion.mjs` `resolveCommandCwd`), which can be a subdirectory
  of the git checkout the live session that triggered it actually started
  from — only a *task*-run broker gets `resolveWorkspaceRoot`'s git-toplevel
  cwd (`executeTaskRun`, `codex-companion.mjs`). Mitigated (fix round,
  2026-09-25): guard (c) also checks the workspace root's nearest
  `.git`-bearing ancestor (walked with pure stdlib `os.path`, no `git`
  binary dependency) for a live session, which covers the case where that
  live session's own cwd is the checkout root. It does not cover every
  possible cwd a live session could have relative to the workspace (e.g. a
  session itself running from some other subdirectory of the same
  checkout); regression test:
  `LiveCwdGuardTests.test_review_broker_in_a_git_subdirectory_is_blocked_by_a_session_at_the_checkout_root`
  in `tests/test_codex_broker_reaper.py`.
- **Guard (b), crash-orphaned jobs:** a job's status only ever leaves
  `queued`/`running` via `cleanupSessionJobs` (`session-lifecycle-hook.mjs`),
  which runs solely from a normal `SessionEnd`. A session that crashes (or a
  workflow-child worktree whose session never reaches `SessionEnd`) with a
  job still `running`/`queued` leaves that status forever, and guard (b)
  then blocks its broker permanently — which is precisely the crash
  scenario this tool otherwise targets. This is disclosed, not fixed: guard
  (b) is implemented exactly as the brief specifies ("no job in its
  `state.json` has a non-terminal status"), and relaxing it based on the
  job's own recorded `pid` (which `cleanupSessionJobs` itself uses to
  `terminateProcessTree`, `session-lifecycle-hook.mjs:65`) not being alive
  would trade a disclosed, conservative safety margin for a materially
  different, unverified one — exactly the kind of guess this tool's own
  docstring says it never makes. Operators can see this in `--list`'s
  per-broker `reasons` (a guard (b) failure names the blocking job ids).

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

- `python3 -m unittest tests.test_codex_broker_reaper -v`: 20 tests, all
  passing, at the initial build — the "19" recorded here at the time of
  review was inaccurate (`grep -cE '^\s+def test_' tests/test_codex_broker_reaper.py`
  gives 20 at both HEAD and 8a86ba52, the commit that last changed the test
  file before this figure was written); 26 after the 2026-09-25 fix round
  added six regression tests (see "Fix round" below), all still passing.
  Every guard is exercised against a real spawned process, not a
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
  written to both stdout and `--receipt PATH` identically — including the
  `--list`-with-an-eligible-broker-still-exits-0 regression
  (`ReceiptShapeTests.test_list_mode_with_an_eligible_broker_still_exits_zero`),
  omitted from this coverage list at the time of review despite already
  existing in the suite.
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
loaded, or started anywhere (`@REPOSITORY@` is an unrendered placeholder —
though `systemd-analyze verify --user` now passes against both unit files
with it substituted, see "Fix round" below); behavior on a Windows/macOS
variant of the plugin (`pipe:` endpoints — the tool recognizes only `unix:`
and reports `unsupported_endpoint` otherwise); and any interaction with a
real, in-progress `codex` job (every "running job blocks eligibility" case
above is a synthetic `state.json`, not a real in-flight task).

## Fix round (2026-09-25)

A review of the initial commits (3ff02227, 8a86ba52, 07ca2da8, bd03b2a7) found
one blocking and two major findings, resolved here; see the tool's own
docstring and `tests/test_codex_broker_reaper.py` for the code-level detail
this section summarizes.

- **Blocking — no platform skip guard.** `tests/test_codex_broker_reaper.py`
  reads `/proc` directly and uses `prctl(PR_SET_NAME)`; without a skip guard
  the required `validate-macos` CI check (`.github/workflows/
  adoption-bootstrap.yml`, required by `.github/main-ruleset.json`, no
  `if:` of its own and no `paths:` filter on the triggering event) would run
  `python3 -m unittest -v` on macos-15 and fail every class in this module.
  Fixed: `LINUX_ONLY = unittest.skipUnless(sys.platform.startswith("linux"),
  ...)` applied to every test class (precedent:
  `tests/test_adoption_bootstrap.py`'s `LINUX_X86_64_ONLY`, applied
  per-method there since only some of that file is platform-specific;
  applied per-class here since this whole suite is).
- **Major — guard (c) counted the broker's own `codex app-server` child as a
  live session.** Every live broker owns exactly such a child for its whole
  lifetime (`app-server.mjs` `SpawnedCodexAppServerClient.initialize()`:
  `spawn("codex", ["app-server"], {cwd: this.cwd})`, not detached), and only
  the broker's own pid was excluded from the live-session scan — so a live
  orphan whose workspace directory still exists (the common retained-worktree
  case) could never become eligible. The prior synthetic fixture's fake
  broker never spawned a child at all, which is why the existing tests never
  caught this. Fixed: `evaluate_broker` now excludes the broker's full
  descendant set (new `collect_descendant_pids`), not just its own pid;
  regression test: `LiveCwdGuardTests.
  test_brokers_own_codex_app_server_child_does_not_block_its_own_eligibility`
  (also proves the fix does not over-exclude a genuine live session under
  the same workspace, or an unrelated one elsewhere).
- **Major — the systemd timer's `Persistent=true` had no effect.** It only
  had monotonic triggers (`OnBootSec=`, `OnUnitActiveSec=`); systemd applies
  `Persistent=` solely to `OnCalendar=` timers (`man systemd.timer`, checked
  on this host, systemd 255.4-1ubuntu8.17). Fixed: the timer now sets
  `OnCalendar=hourly` (keeping `OnBootSec=10min` for an early run after
  boot, dropping the now-redundant `OnUnitActiveSec=1h`); verified with
  `systemd-analyze verify --user` against both unit files with
  `@REPOSITORY@` substituted (exit 0, no warnings).
- **Disclosed, not code-fixed beyond a partial mitigation** — see "Known
  limitations" above: a review-triggered broker's OS cwd can be a
  subdirectory of the actual live session's own checkout root (guard (c)
  now also checks that checkout root); a job left `running`/`queued` by a
  crashed session permanently blocks guard (b) (unchanged — guard (b) is
  implemented exactly as the brief specifies).
- **Also fixed, both safety-adjacent rather than correctness bugs:** `run()`
  now re-checks every guard immediately before stopping each broker, not
  once for the whole batch, since an earlier broker's own stop can take long
  enough (up to 15s, 35s with `--escalate`) for a session to attach to a
  later one first (regression test: `ApplyAndEscalationTests.
  test_apply_rechecks_each_broker_immediately_before_stopping_it`);
  `--escalate` now refuses to send SIGTERM unless the broker is confirmed
  still its own process-group leader (`os.getpgid(pid) == pid`), rather than
  trusting the "detached brokers are always group leaders" premise
  unconditionally (regression test: `ApplyAndEscalationTests.
  test_escalation_is_skipped_when_broker_is_not_its_own_process_group_leader`);
  and `main()` now fails closed with an explicit error on a host with no
  `/proc` at all, rather than silently reporting every broker as "not
  running" (regression test: `PlatformGuardTests.
  test_main_refuses_to_run_without_proc`) — stated as Linux-only in
  `adoption/tools/README.md` too now.
- **Corrected:** the claim that "the kernel sets `comm` from the shebang
  interpreter" (previously in this doc's Context section and the tool's
  `is_claude_or_codex_process` docstring) does not hold for a *direct*
  shebang — checked directly on this host: a script with
  `#!/usr/bin/python3`, executed as its own file, reports the *script's*
  basename as `comm`, not the interpreter's. The test fixtures' `comm` reads
  back as `python3` simply because they invoke `python3 script.py`
  explicitly, independent of any shebang.
- **Not supported by the source, left unchanged:** a finding that guard
  (d)'s age is "overstated by the elapsed evaluation time" because `run()`
  passes one `now`, captured once, into both `process_start_epoch`'s
  `reference` and the external age subtrahend. Traced algebraically and
  confirmed with a new test (`MinAgeGuardTests.
  test_age_is_correct_even_with_an_artificially_stale_reference_time`, using
  a reference an hour stale): `age = now - started = now - ((now - uptime) +
  ticks/clk) = uptime - ticks/clk`, independent of `now`/`reference` — it is
  always the broker's true instantaneous age as of the live `/proc/uptime`
  read, not a value skewed by how stale the caller's `now` is.
- **Commit attribution:** this round's commits, like the four before them,
  carry `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` rather than
  the rollout brief's literal `Claude Opus 5.5 (1M context)` line. This
  reflects the model actually running the session (per its own system
  prompt) under the harness's current attribution instruction, which takes
  precedence for that session over a brief's embedded request; left as-is
  rather than "fixed" to match the brief, since doing so would mean acting
  against that current instruction.
- **Re-measured:** `python3 -m unittest tests.test_codex_broker_reaper -v`
  (26 tests, all passing); `python3 adoption/tools/codex-broker-reaper
  --list` against this host's real plugin state (still 17 found, 0
  eligible — unchanged, since all 17 are refused at guard (a) before guard
  (c) is reached, so this fix round's guard (c) change does not move this
  host's own number); `python3 scripts/validate.py` and `python3
  scripts/validate_foundation.py` (both still pass).
