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
- **Guard (c), a coordinator with no git relationship to the worktree at
  all:** found in review of this rollout's own "reaper" track (second fix
  round, 2026-09-25) — a coordinating session that dispatches into a
  worktree by prefixing every Bash command with `cd <worktree> &&`, rather
  than changing its own OS process cwd, is findable by guard (c)'s
  worktree-to-parent check (`read_worktree_parent_root`) only when it was
  itself launched from that worktree's own main checkout. Verified directly
  against this tool's own live process during this fix round: a coordinator
  launched from a *separate* driver repository (this rollout's own
  `agent-lab`, unrelated by git ancestry to the `codex-broker-reaper`
  worktree it was dispatching this very fix into) has no cwd-based signal
  under any of guard (c)'s checks at all. Mitigated, not fully closed, by
  guard (e) (below): a session that periodically runs *codex jobs* in that
  workspace keeps resetting the job-activity clock even though no live
  process's cwd is ever under the workspace itself. A worktree broker that
  has never yet run a single job (empty `jobs[]`, so guard (e) has no
  timestamp signal either) and whose only live coordinator is entirely
  git-unrelated to it is not reliably protected by any guard here beyond
  guard (d)'s plain process age — this is the same shape of gap as the
  subdirectory case above, disclosed rather than guessed at a further fix.
- **Guard (e), idle-since-last-job rather than idle-since-ever:** guard (e)
  only requires `--min-age` since the most *recent* job, not since the
  workspace was first used — a session that runs a codex job every 20
  minutes (below the 1800s default `--min-age`) keeps its broker ineligible
  indefinitely, which is the intended effect, not a bug, but is worth
  stating plainly: guard (e) is not a cap on how long a broker may live
  while genuinely in periodic use.

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
  gives 20 at bd03b2a7, the commit this sentence was written at, and
  likewise at 8a86ba52, the commit that last changed the test file before
  then — corrected in the second fix round below; this sentence previously
  said "HEAD" in place of "bd03b2a7", which is only accurate at the commit
  it was written at, not as a standing reference — at 7167a244 and after it
  no longer named that commit at all); 26 after the 2026-09-25 fix round
  added six regression tests (see "Fix round" below), all still passing; 40
  after the second fix round (see "Fix round (2026-09-25, second pass)"
  below), all still passing.
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

## Fix round (2026-09-25, second pass)

A review of 7167a244 (the first fix round's own HEAD) found one new major
finding and four new minor findings, resolved here, plus a scope-disclosure
gap in this same record; see the tool's own docstring and
`tests/test_codex_broker_reaper.py` for the code-level detail this section
summarizes.

- **Major — guard (c) cannot see a live in-process workflow child, the leak
  source the brief itself names.** Verified directly against this session's
  own live processes while investigating: a coordinator that dispatches
  into a worktree by prefixing every Bash command with `cd <worktree> &&`
  (this rollout's own pattern) never changes its own OS process cwd, so
  neither the workspace-root scan nor the git-toplevel scan could ever see
  it, and its transient per-command Bash shells (`comm` `bash`, not
  `claude`/`codex`) are gone again before the next scan. Once a broker
  passed `--min-age` this way it was reaped even while its owning session
  was still actively, if intermittently, using it — the exact case the
  brief's "Never touch brokers of live sessions" and this record's own
  Context section (guard (c) bullet) claimed was handled, without
  disclosing this gap. Two fixes, both applied (the finding offered either
  as sufficient; both were cheap and independently useful):
  - Guard (c) now also checks the *other* checkout a `git worktree`
    workspace belongs to (`read_worktree_parent_root`, parses the
    worktree's own `.git` `gitdir: .../.git/worktrees/<name>` pointer file,
    pure stdlib), for a live session there. This closes the gap exactly
    when the coordinator was launched from the worktree's own main
    checkout — verified against a hand-written `.git` pointer file in
    `LiveCwdGuardTests.test_a_live_session_at_the_worktrees_main_checkout_blocks_eligibility`
    (no real `git worktree` needed, same style as the existing
    subdirectory-broker test) — but not when the coordinator is a separate
    driver repository with no git relationship to the worktree at all
    (this rollout's own `agent-lab`, checked directly: still true after
    this fix).
  - New guard (e): the workspace's most recent recorded job activity
    (`state.json` jobs[]' `updatedAt`, set on every job write by the
    plugin's own `upsertJob` — verified directly in `scripts/lib/
    state.mjs`) must also be at least `--min-age` in the past, not just the
    broker *process's* own age (guard (d)). This does not depend on seeing
    any live process at all, so it also covers the `agent-lab`-style
    cross-repo coordinator case above — as long as that session's work in
    the workspace involves running codex jobs periodically, which resets
    the guard (e) clock each time. Regression tests: `JobIdleGuardTests`
    (three tests: recent activity blocks despite an old-looking broker
    process, old-enough activity allows, no activity timestamp at all falls
    back to guard (d) alone).
  - Residual, disclosed rather than further guessed at: a worktree broker
    that has never yet run a single job has no guard (e) signal either, so
    a cross-repo coordinator that has not yet run its first codex job in a
    given workspace is still only protected by guard (d)'s plain process
    age (see "Known limitations").
- **Minor — stopping a broker left `broker.json` pointing at the dead
  endpoint/pid.** `stop_broker()` confirmed the broker *process* exited but
  never touched its `broker.json`; a plugin code path that trusts
  `broker.json` without itself reconnecting first (traced to `codex.mjs`'s
  `getSessionRuntimeStatus` and `getCodexAuthStatus`'s
  `reuseExistingBroker` path) would misreport for that workspace until its
  own next `SessionEnd`. Fixed: `clear_broker_json_if_stopped()` removes
  `broker.json` once an exit is confirmed, but only after re-reading it and
  confirming it still names the exact pid/endpoint just stopped — guarding
  against a *new* broker having started (and written its own new
  `broker.json`) for the same workspace during the stop's own wait.
  Regression tests: `ApplyAndEscalationTests.
  test_apply_removes_broker_json_after_a_confirmed_stop` and `.
  test_apply_leaves_broker_json_when_it_now_names_a_different_broker` (the
  race case, via a direct `stop_broker()` call followed by a simulated
  concurrent broker.json rewrite).
- **Minor — exit code 2 was overloaded.** The README and rollout brief both
  document exit 2 as "an eligible broker was not confirmed stopped", but
  `main()` also used `parser.error()` (always exit 2) for a host with no
  `/proc` at all, and for ordinary argparse usage errors (bad flags,
  `--min-age` below 0). A monitor or systemd consumer following the
  documented contract could not tell a platform refusal from a real stop
  failure. Fixed: the `/proc`-missing refusal now prints directly to
  stderr and returns 3, rather than going through `parser.error()` — which
  also makes that path consistent with every other exit from `main()` (a
  plain `return`, wrapped in `SystemExit` only by the `if __name__ ==
  "__main__":` guard, not raised from inside `main()` itself). Ordinary
  argparse usage errors (bad `--min-age`, mutually exclusive flags, unknown
  options) keep exit code 2, matching the near-universal argparse
  convention — the finding's own ask was to give the `/proc` refusal a
  distinct code, not to also carve out usage errors. Regression tests:
  `PlatformGuardTests.test_main_refuses_to_run_without_proc` (updated for
  the new code and calling convention) and the new `.
  test_bad_usage_still_exits_2_via_argparse`.
- **Minor — `path_is_under()` was wrong for a filesystem-root workspace.**
  With root `"/"`, the old `root + os.sep` was `"//"`, which only the
  literal string `"/"` itself ever starts with, so `path_is_under(anything,
  "/")` returned False for every real absolute path — wrong in the unsafe
  direction for a live-session safety check (improbable in practice: a
  broker's workspace root or nearest `.git` ancestor resolving to `"/"`).
  Fixed: append the separator only when `root` does not already end with
  one. Regression tests: `PathIsUnderTests` (new class; also covers the
  ordinary case and a same-string-prefix sibling that must not match).
- **Minor — one broker's malformed state could abort the whole run.**
  `evaluate_broker()`'s `except (OSError, json.JSONDecodeError)` around
  `broker.json`/`state.json` reads did not catch `UnicodeDecodeError` (a
  `UnicodeError` -> `ValueError` subclass, not an `OSError` or
  `JSONDecodeError`) from a non-UTF-8 file, and a `broker.json` that parsed
  as valid JSON but was not an object (e.g. a bare list) crashed at the
  `broker.get(...)` call just below with an uncaught `AttributeError` —
  either crashed `run()`'s list comprehension over every broker, losing the
  whole hour's receipt and reaping, contrary to `evaluate_broker()`'s own
  "always returns a fully-shaped record" contract. Fixed two ways: (1) the
  two specific reads now catch `(OSError, ValueError)` (`ValueError` is the
  shared superclass of `json.JSONDecodeError` and `UnicodeDecodeError`) and
  a non-dict `broker.json` returns an ineligible record explicitly; (2) a
  new `safe_evaluate_broker()` wraps `evaluate_broker()` in a bare
  `except Exception` (not `BaseException`, so `KeyboardInterrupt`/
  `SystemExit` still propagate) as an outer safety net for anything neither
  fix (1) nor guard (a)/(b)'s own existing reads anticipate; `run()` now
  calls it instead of `evaluate_broker()` directly, for both the initial
  scan and the pre-stop re-check. Regression tests: `MalformedStateTests`
  (new class; non-object `broker.json`, non-UTF-8 `broker.json`, non-UTF-8
  `state.json`, and a monkeypatched-raise proving `run()`/`main()` still
  evaluates every other broker and exits 0).
- **Also fixed — this record's own inaccurate "HEAD" reference.** See
  "Measured" above: "gives 20 at both HEAD and 8a86ba52" was written once,
  at bd03b2a7, where it was correct — but was never revisited when the
  first fix round (5da77e6b) added six more tests, so "HEAD" silently kept
  meaning whatever commit a reader checked it against. By 7167a244 (this
  pass's own review base) `grep -cE '^\s+def test_' tests/test_codex_broker_reaper.py`
  gave 26 there (now 40), contradicting the sentence's own "20" figure.
  Corrected to name the specific commit (bd03b2a7) instead of "HEAD".
- **Scope disclosure — `manifests/evidence.json`.** Outside this track's
  allowed paths (`adoption/tools/codex-broker-reaper`,
  `adoption/tools/README.md`, the systemd templates,
  `tests/test_codex_broker_reaper.py`, this decision record), but touched
  in both this fix round and the first one (commits 7167a244 and, before
  it, the first round's own README update): `scripts/validate.py`'s
  `scan_publication` hash-pins `adoption/tools/README.md`'s exact
  `sha256`/`bytes` in `manifests/evidence.json`'s `files[]`, so every edit
  to that README requires a matching two-field re-pin there or
  `scripts/validate.py` (this track's own acceptance command) fails
  integrity. Mechanical, sha256/bytes-only, single-file diff each time,
  computed directly from the edited README's own bytes — never hand-picked
  or used to touch any other field. The first round's own commit message
  said as much but this record did not; disclosed here for both rounds,
  closing that gap.
- **Re-measured (second pass):** `python3 -m unittest
  tests.test_codex_broker_reaper -v` (40 tests, all passing); `python3
  adoption/tools/codex-broker-reaper --list` against this host's real
  plugin state (still 17 found, 0 eligible, all refused at guard (a) before
  guards (c)/(e) are reached — this pass's changes do not move this host's
  own number, same as the first pass); `python3 scripts/validate.py` and
  `python3 scripts/validate_foundation.py` (both still pass, after the
  `manifests/evidence.json` re-pin above); `python3 -m unittest discover -s
  tests` under `ecosystem-bounded-run` (this repository's full suite,
  4746 tests): 9 pre-existing failures, all `INT`-signal cases in
  `tests/test_adoption_bootstrap_macos.py` and
  `tests/test_adoption_launchd.py`, untouched by this track's diff (which
  only touches `adoption/tools/`, `docs/decisions/`,
  `tests/test_codex_broker_reaper.py`, `manifests/evidence.json`) and
  reproduced on an unrelated worker's checkout of the same base commit —
  not this track's regression.
