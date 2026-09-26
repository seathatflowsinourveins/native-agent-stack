# Token-efficiency coverage on the workstation (2026-09-26)

Host: `nativestack-5975wx-20260925`, the WSL2 workstation (Ubuntu 24.04.5, x86_64).
These files retain the host results that
[the Codex MCP scope decision](../../../docs/decisions/2026-09-25-codex-mcp-scope.md) cites, as the
2026-09-26 cross-family review asked. The earlier narrative in that record kept no output.

## Files

| File | What ran | When (UTC) | Exit |
| --- | --- | --- | --- |
| [`coverage-20260926T000437Z.json`](coverage-20260926T000437Z.json) | The coordinator's coverage check | 00:04:37Z, kept only in the file name | not retained |
| [`coverage-20260926T023952Z.json`](coverage-20260926T023952Z.json) | The same check, rerun with the first version of this repair's `scripts/adoption_status.py` | 02:39:52Z, kept only in the file name | not retained |
| [`codex_readback.py`](codex_readback.py), [`codex-readback.json`](codex-readback.json) | Codex's own read-back of the `headroom` and `context-mode` registrations | started 02:24:15Z | not retained; each of its three commands exited 0 |
| [`pinned-versions-regression-tests.txt`](pinned-versions-regression-tests.txt) | The repair's five new `--pinned-versions` tests, run against the pre-repair script, then the repaired one | 02:43:53Z to 02:44:47Z | 1, then 0 |
| [`signal_disposition_control.py`](signal_disposition_control.py), [`signal-disposition-regression-tests.txt`](signal-disposition-regression-tests.txt) | The independent review's signal-disposition fix: a bash reference, then the signal tests against the first repair's script and the fixed one, and from runners that inherit a signal ignored | 04:45:51Z to 04:46:46Z | runs A to G: 1, 0, 0, 0, 1, 1, 0 (the driver's own exit was not retained) |
| [`coverage_run.py`](coverage_run.py), [`coverage-20260926T044740Z.json`](coverage-20260926T044740Z.json), [`coverage-20260926T044740Z.provenance.txt`](coverage-20260926T044740Z.provenance.txt) | The same check, run on `5c1961e4` with the script as it stood before the interrupt-window fixes, by a driver that retains how it ran | 04:47:40Z to 04:47:42Z | 0 |
| [`interrupt_window_control.py`](interrupt_window_control.py), [`interrupt-window-regression-tests.txt`](interrupt-window-regression-tests.txt) | The cross-family verification's interrupt-window fix: the signal tests against the script before it and the first fix | 06:40:45Z to 06:41:53Z | runs A to D: 1, 0, 0, 0 |
| [`wiring_control.py`](wiring_control.py), [`coverage-20260926T064250Z-codex-home-empty.json`](coverage-20260926T064250Z-codex-home-empty.json), [`coverage-20260926T064252Z.json`](coverage-20260926T064252Z.json), [`wiring-control-20260926T064250Z.provenance.txt`](wiring-control-20260926T064250Z.provenance.txt) | The coverage check's discriminating control: once with an empty Codex home, then as the host runs it | 06:42:50Z to 06:42:56Z | 0, then 0 |
| [`interrupt-window-every-line-regression-tests.txt`](interrupt-window-every-line-regression-tests.txt) | The same interrupt-window driver, against the first fix and the final script, with a test that interrupts a probe run at every line | 10:21:30Z to 10:22:09Z | runs A to D: 1, 0, 0, 0 |

### `coverage-20260926T000437Z.json`

The coordinator's invocation line was not retained. The report's own fields give its flags and inputs:

```sh
python scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json
```

- **Profile and flags:** the report lists only the `token-efficiency` profile and carries both
  `client_wiring` and `pinned_versions`, as JSON.
- **Interpreter:** Python 3.13.15 (`platform.python`).
- **Checkout:** `564a16a3` (`git.current_commit`), whose `scripts/adoption_status.py` predates this
  repair: it did not yet require a probe's exit status 0, and it killed only the probe's own process
  on timeout. `project.codex_mcp_servers_present` is false for all three servers, so the checkout's
  project `.codex/config.toml`, if it had one, registered none of them. That value is the same whether
  the file is absent or lists none of the three, and the run's working directory was not retained, so
  whether that checkout had a project Codex config is not known.
- **Time:** 00:04:37Z, which the session that copied the report gave as the modification time of the
  file the coordinator's check wrote, is kept only in this copy's name. That the copy is byte-identical
  to that file was not retained either.

### `coverage-20260926T023952Z.json`

The invocation line was not retained either; the report's fields give the same profile and flags:

```sh
python scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json
```

- **Interpreter:** Python 3.13.15 (`platform.python`).
- **Working directory:** a detached worktree at `a74dd1b6` (`git.current_commit`) with this repair's
  first, uncommitted `scripts/adoption_status.py`. The session that ran it gave that script's sha256 as
  `6ad15fb0d3889265c82669bac565e623dba449eae14ce29846cab158912ac3a6` and reported that the worktree had
  no project `.codex/config.toml`. Neither is in a retained output, and the report itself cannot show
  the second (see above).
- **Not retained:** the end time, the exit status and stderr.

### `coverage-20260926T044740Z.json`

```sh
python coverage_run.py --checkout <this repository> --out-dir .
```

`coverage_run.py` first checks whether the checkout has a project `.codex/config.toml`. It then runs
`python scripts/adoption_status.py --profile token-efficiency --client-wiring --pinned-versions --json` in
the checkout with its own interpreter, writes that stdout byte for byte to this file, and prints how the
run went. That output is retained in
[`coverage-20260926T044740Z.provenance.txt`](coverage-20260926T044740Z.provenance.txt):

- **Result:** exit 0 and an empty stderr. The checkout had no project `.codex/config.toml` just before
  the run.
- **Interpreter:** Python 3.13.15. Whether it ran in a virtual environment was not recorded.
- **Working directory:** a worktree of `5c1961e4` (`git.current_commit`) with 27 paths changed from
  `HEAD`, including `scripts/adoption_status.py` as it stood before the interrupt-window fixes below
  (sha256 `3f530026ca977b1effe9f0cf0dc3e4c94ec12caf5b5d0b53b6802d2286e7c74d`), which already left an
  ignored signal ignored.
- **Output:** apart from `git` and the limitation text, the report is identical to the 02:39:52Z one.

### `codex-readback.json`

```sh
python3 codex_readback.py > codex-readback.json
```

The script runs `codex --version`, `codex mcp get headroom --json` and
`codex mcp get context-mode --json`. It records each exit code and the sha256 of each raw stdout. From
the output it keeps only facts: environment variable names, argument basenames, and whether the server
has a working directory and whether that directory is a plugin install path. Run from an empty
directory, it sees what a fresh worktree sees: the user scope plus plugins. The session that ran it
reported doing so from an empty directory outside any checkout; the output records neither the
directory nor the interpreter, only its start time (`observed_at_utc`) and Codex's version.

### `pinned-versions-regression-tests.txt`

This is the discriminating control for the `--pinned-versions` repair. The file's header gives the
command, both trees, the script and test hashes, the times and the exit codes. It ran the first
repair's test file (sha256 `97200634…`); the fix below later changed that file's interruption test.

Both runs use this repair's test file, so the only difference is the script under test. Against the
pre-repair script from `a74dd1b6`, all five tests fail, with 8 failures counting subtests:

- a probe that exits 42 with the pin in its message is reported as a match (2 subtests);
- a stdout without a final newline runs into stderr, so the version is not found;
- on timeout, the probe's child keeps running;
- once the probe exits, its child keeps running. The check also waits out the bound for that child,
  which holds the output open, and then reports the probe unchecked;
- after SIGINT, SIGTERM or SIGHUP (3 subtests), the probe's child keeps running.

Against the repaired script, all five pass.

### `signal-disposition-regression-tests.txt`

The independent review of this repair found that the first repair's check replaced a signal disposition
it inherited as ignored. Under `nohup`, a SIGHUP ended the check with status 129 and no report, although
`adoption/bootstrap-linux.sh`, which traps only `EXIT`, keeps running then. The fix changes SIGTERM and
SIGHUP only while they are at their default action, as CPython does for SIGINT. The driver
`signal_disposition_control.py` prints its own command lines, hashes, UTC times and exit codes:

```sh
python signal_disposition_control.py --checkout <this repository> \
  --first-repair-script <the first repair's scripts/adoption_status.py> \
  --first-repair-tests <the first repair's tests/test_adoption_status.py>
```

- **Bash reference.** A bash script with an `EXIT` trap, sent SIGTERM or SIGHUP at the default action,
  runs the trap and dies by the signal. Sent the same signal after starting with it ignored, it runs to
  the end.
- **Run A**, the first repair's script with this repair's tests: 4 failures. SIGTERM or SIGHUP ignored on
  entry still ends the check (143, 129), and the in-process tests see an ignored signal and another
  handler replaced. The SIGINT subtest passes: CPython already leaves an ignored SIGINT ignored.
- **Run B**, the fixed script: all pass.
- **Runs C and D**, the fixed script's tests from a runner under `nohup` (SIGHUP ignored) and from a
  background job of a non-interactive shell (SIGINT ignored): all pass, because the process-level tests
  now start each check with exactly the dispositions they need.
- **Runs E and F**, the first repair's interruption test from the same two runners: it errors after 20 s
  in each, because the check it starts inherits the ignored signal and keeps running.
- **Run G**, the first repair's script and test under `nohup`: it passes, but only because that script
  replaced the ignored SIGHUP.

### `interrupt-window-regression-tests.txt`

The cross-family verification of this repair found that `run_version_probe` armed the group kill only
once `subprocess.Popen` had returned the probe's process. A SIGTERM that arrived after the fork but
before that return ended the check with status 143 and left the probe running. The first fix holds an
interruption back while the process is created and while its group is killed and reaped
(`held_interrupts`), and raises it once that step is done. SIGINT, while at its default action, now goes
through the same handler and still raises `KeyboardInterrupt`, so it can be held back too.

```sh
python interrupt_window_control.py --checkout <this repository> \
  --pre-fix-script <scripts/adoption_status.py before the fix>
```

The driver copies the two scripts into two scratch trees with the same tests and runs the two signal test
classes; it prints its hashes, commands, UTC times and exit codes. The new process-level tests raise the
signal on the check itself at the point they test (`INTERRUPT_INSIDE_A_PROBE`): after the probe's fork,
once its background child runs, but before `subprocess.Popen` returns, or as the KILL to the group
begins, after a first SIGTERM.

- **Run A**, the script before the fix (sha256 `3f530026…`): 8 failures and 1 error. The probe's child
  outlives SIGINT, SIGTERM or SIGHUP delivered while its process is created (3 subtests) and a second
  signal as the kill begins (3 subtests); `signals_interrupt_probes` leaves SIGINT's disposition as it
  found it (2 subtests); and `held_interrupts` does not exist yet (the error).
- **Run B**, the first fix (sha256 `cd1229719768632b045e53e5dc7ee0d4c24ea2c36084589d28f8886329c349a6`):
  all 9 tests pass.
- **Runs C and D**, the first fix from a runner under `nohup` and from a background job: all pass.

### `interrupt-window-every-line-regression-tests.txt`

A closer look at the first fix found the same kind of window at the other end of the probe. After the
wait, the kill began its hold only through `if process is not None:` and `with held_interrupts():` in
the `finally` block, so an interruption that landed on those lines, or on `held_interrupts`'s own lines
before its hold was on, stopped the kill and left the group running. The final script holds
interruptions from before the process is created until its group has been killed and reaped, and lets
them through only while it waits for the probe, inside the block whose cleanup kills the group
(`interrupts_released`).

The new in-process test `test_an_interrupt_at_the_start_of_any_line_of_a_probe_run_still_kills_its_group`
calls the SIGTERM handler the check installs, as CPython calls it for a signal that has arrived, at the
start of the first line that `run_version_probe` and its helpers execute, then the second, and so on, one
line per run, until the KILL to the probe's group has been sent. It skips lines that begin with a NOP (a
`try` statement's own line): CPython never runs a signal handler there, and no exception handler covers
some of them. The probe and its background child ignore SIGTERM, so only that KILL ends them. The test
covers a probe that exits at once and one that outlives its bound.

This output comes from the same driver, unchanged (sha256 `cbffdad3…`), run with the first fix as
`--pre-fix-script`. In it, "the pre-fix script" is therefore the first fix (sha256 `cd122971…`) and "the
fixed script" the final one (sha256 `2b372896fb827871660789b99ab4553ec5d72bbc21c3b3a23a634950013a5d6b`).

- **Run A**, the first fix: 3 failures. The every-line test fails for both probes: the child outlives
  an interrupt at the start of four lines, the two `finally` lines above and two lines of
  `held_interrupts` before its hold is on. The four warnings that a subprocess "is still running" are
  the probes that outlived their bound at those lines, left running themselves. The new test of
  `interrupts_released` fails too: the first fix has no such function, and the interrupt held at the
  end of the test's hold replaces that error, so the test sees its block stop early. The other 9 tests
  pass.
- **Runs B to D**, the final script, from a runner with the default dispositions, under `nohup` and as a
  background job: all 11 tests pass.

`tests/test_adoption_status.py` now has 72 tests.

### Wiring control (`wiring-control-20260926T064250Z.provenance.txt`)

```sh
python wiring_control.py --checkout <this repository> --out-dir .
```

The driver runs the coverage check twice in the checkout: first with `CODEX_HOME` set to a new empty
directory, so the check finds no Codex user scope (the condition absent), then with the environment it
was started with. It prints what each run did and no path, file text or environment value:

- **Control, 06:42:50Z to 06:42:52Z** (`coverage-20260926T064250Z-codex-home-empty.json`): exit 0,
  empty stderr. `client_wiring.complete` is false, and `codex.mcp_servers_present` is false for serena,
  socraticode and ai-memory. The other Codex checks read the same empty home: `rtk_instructions` and
  `context_mode_plugin_enabled` are false and `ai_memory_hook_events` is 0, while `hooks_feature_enabled`
  stays true, as the check reports it when no config turns the feature off.
- **Host environment, 06:42:52Z to 06:42:56Z** (`coverage-20260926T064252Z.json`): exit 0, empty
  stderr. `complete` is true, with the three Codex servers present and
  `project.codex_mcp_servers_present` false for all three. The report is byte-identical to the
  04:47:40Z one (sha256 `494f9cf9…`).
- **Both:** no project `.codex/config.toml` just before the run; Python 3.13.15, not in a virtual
  environment; a worktree of `5c1961e4` with 33 paths changed from `HEAD`, with
  `scripts/adoption_status.py` at the first interrupt-window fix (sha256 `cd122971…`).

## What they show

- **Worktree wiring.** The four runs in the host's environment (00:04:37Z, 02:39:52Z, 04:47:40Z and
  06:42:52Z) report `client_wiring.complete: true` with `project.codex_mcp_servers_present` false for
  serena, socraticode and ai-memory. Each checkout's project Codex config, if any, therefore registered
  none of the three, and the wired Codex servers came from the user scope. Before the 04:47:40Z and
  06:42:52Z runs, the drivers found no project `.codex/config.toml`, so those checkouts had no project
  Codex config at all. The control at 06:42:50Z, with an empty Codex home in place of the user scope,
  reports `complete: false`: the check fails when the user-scope registrations are absent.
- **Which pins.** The check compares each component with its entry in the checkout's
  `adoption/pins-linux-x86_64.json`, which each report repeats as `pinned_version`. It does not compare
  with the landscape winner pins, and for six of the 12 components with an `exec` probe the winner pin in
  `catalogs/landscape/foundation.json` at `5c1961e4` differs: claude-code 2.1.278, rtk 0.49.0,
  markitdown 0.1.7, ai-memory 2.3.2, mcporter 0.13.13, and serena, whose winner pin adds a commit
  (`2.0.0.dev0 @ c6fbd1c5…`). A match here says nothing about those winner pins.
- **Versions at 00:04:37Z.** 10 components match their pins. ai-memory (pinned 2.3.2) and mcporter
  (pinned 0.13.13) do not. The report gives no observed versions, but the cutover records put the host
  on mcporter 0.14.1 from about 2026-09-25T20:12Z
  ([`mcporter/cutover.json`](../sota-refresh-20260925/mcporter/cutover.json)) and on ai-memory 2.4.0
  from 20:44:37Z ([`ai-memory/cutover.json`](../sota-refresh-20260925/ai-memory/cutover.json)); the
  2.4.1 cutover began at 00:14:12Z, after this run
  ([`ai-memory-241/cutover.json`](../sota-refresh-20260925/ai-memory-241/cutover.json)). context-mode
  and socraticode are unchecked: both declare `npm-metadata` probes, which this check never runs.
- **Versions at 02:39:52Z, 04:47:40Z, 06:42:50Z and 06:42:52Z,** after #307 pinned ai-memory 2.4.1 and
  mcporter 0.14.1. All 12 `exec` probes match their pins; context-mode and socraticode stay unchecked.
  Each of these reports states in its own limitations that only a probe that exits 0 is compared with its
  pin, so these runs also show that none of the 12 probes failed.
- **Registrations.**
  - Codex's `headroom` registration on this host sets `DO_NOT_TRACK` and `HEADROOM_OFFLINE` only. The
    template now adds `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE`, which have not yet been applied to
    this host.
  - The `context-mode` server that a fresh worktree gets is the plugin's own: `node ./start.mjs`, with
    `CONTEXT_MODE_PLATFORM` as its only variable. Its working directory is the plugin install directory
    (`plugins/cache/context-mode/context-mode/1.0.169`).

## What they do not show

- MCP server startup and tool calls. The 2026-09-25 tool counts through MCPorter, and ai-memory's
  `/healthz`, remain unretained host reports.
- The `codex mcp list` output from before the change (2026-09-25).
- Claude's user-scope `headroom` registration. It is not read here, because reading it goes through the
  Claude client's own account file.
- Which project directory a running context-mode server uses. The context-mode binding evidence covers that:
  [`../context-mode-codex-binding-20260926/`](../context-mode-codex-binding-20260926/README.md).
  `client_wiring` cannot show it either: it checks that the context-mode plugin is enabled, not where its
  server binds. Codex's read-back at 02:24:15Z found this host's server to be the plugin's
  (`codex-readback.json`), and the 02:39:52Z, 04:47:40Z and 06:42:52Z runs still reported
  `complete: true` after it. No read-back covers the 00:04:37Z run.
- A coverage run of the final script. Its changes since the 06:42:52Z run affect only a probe that is
  interrupted, which the unit tests and the every-line control cover.
- The failing runs again, from this repository alone. The signal-disposition, interrupt-window and
  every-line controls ran earlier, uncommitted versions of this change's `scripts/adoption_status.py` and
  `tests/test_adoption_status.py`. Their outputs name each version by sha256, but only the final ones are
  committed. The pre-repair script of `pinned-versions-regression-tests.txt` is `a74dd1b6`'s.

## Sanitization

- `adoption_status.py` emits no path, credential or configuration value by design.
- `codex_readback.py` emits names, basenames, booleans and hashes. The raw `codex mcp get` output, which
  holds this host's absolute paths, is not published.
- `pinned-versions-regression-tests.txt` replaces its scratch paths with placeholders.
- `signal_disposition_control.py` and `interrupt_window_control.py` print their scratch trees, temporary
  directory and interpreter as placeholders and the home directory as `~`, and refuse to print output
  that still holds a UUID or a home path. `interrupt_window_control.py`'s temporary-directory placeholder
  also replaces `/tmp` inside other paths, so a probe path reads `<tmpdir><tmpdir>…`.
- `coverage_run.py` and `wiring_control.py` print no path, file text or environment value: commits,
  hashes, counts, booleans and times.
