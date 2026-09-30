# Decision: a daily timer writes the currency due-file, and one SessionStart line reads it (2026-09-30)

**Decided by:** coordinator session `native-agent-stack-c5`, unit A2 of the 2026-09-30 wave (branch
`claude/sota-defaults-a2-20260930`, base `origin/main@e45328d3`).

**Scope:** [`scripts/currency_due.py`](../../scripts/currency_due.py) and its tests
([`tests/test_currency_due.py`](../../tests/test_currency_due.py)), the drafted user units
[`adoption/templates/systemd/stack-currency.service`](../../adoption/templates/systemd/stack-currency.service) and
[`.timer`](../../adoption/templates/systemd/stack-currency.timer), their install paragraph in
[`adoption/lifecycle.md`](../../adoption/lifecycle.md#native-client-integration-and-process-lifecycle), and the
startup rule, item 4 of [`docs/token-practice.md`](../token-practice.md).

**Not in this change.** The SessionStart hook script ships in unit F2, and any amendment of `AGENTS.md:28` in unit F1;
both are frozen Gate A units. This record gives F2 the file contract and the acceptance gate below. No unit was
installed and no host file was written: the timer and the service are drafted templates.

## Context

- The currency checks already exist and are read-only. `scripts/adoption_status.py --pinned-versions` compares the
  installed tools with the platform pins, `scripts/receipt_staleness.py` finds host receipts that are old or at a
  retired pin, and `scripts/saturation_ledger.py --report` lists the landscape layers due for a sweep and their
  reopen triggers. Weekly workflows run the last two
  ([`receipt-staleness.yml`](../../.github/workflows/receipt-staleness.yml),
  [`saturation-tracking.yml`](../../.github/workflows/saturation-tracking.yml)) and publish an artifact and one
  issue. The pinned-version probes need the host's own installed tools, so no workflow can run them for a
  workstation. A session learns none of this unless someone runs the commands, which is instruction-only triage.
- A session may not run them at start. `AGENTS.md:28` says "Do not rerun the full audit or model trials at
  startup", and item 4 of `docs/token-practice.md` said "Do not add hooks or schedulers, override providers, or
  rerun model trials during ordinary startup".
- The coordinator's brief for this unit reports that on 2026-09-29 ten components behind upstream were found by
  hand. The repository carries such hand-written notes
  ([`docs/grand-catalog-handbook.md`](../grand-catalog-handbook.md) lines 1267, 1510, 1771 and 1892). The latest
  dated SOTA-convergence manifest, `catalogs/sota-convergence/manifest-20260929.json`, marks 51 rows (33 distinct
  component ids) `pin_behind_upstream: true`. That count was made for this record; the manifest has no summary
  figure for it.
- The state on the workstation at base `e45328d3` on 2026-09-30, from a dry run of the new script (a local integration
  check, not an upstream test): one component whose version probe did not report its pin (`codex`, pin 0.157.1),
  7 flagged receipt buckets (`pin_moved` 7, `no_bound_receipt` 4) and 12 layers with current reopen triggers (38
  `pin_moved` triggers). All 32 layers are not yet saturation candidates. Their last completed sweeps were on
  2026-09-26 (12 layers) and 2026-09-29 (20 layers).

## Alternatives

- **A UserPromptSubmit hook that prints the line.** Rejected. Claude Code adds that event's plain-text stdout as
  context on every prompt, so the line would cost tokens on every turn instead of once per session.
- **A SessionStart hook that runs the checks.** Rejected. A dry run of the three checks took 1.56 s on the
  workstation, about 30 times the 50 ms hook budget below, and they execute each pinned tool's version probe. Running them is the startup
  audit that `AGENTS.md:28` rules out. SessionStart also fires on `resume`, `clear`, `compact` and `fork`, so the
  cost would repeat within one session.
- **Weekly CI only.** Kept as the reviewed record, not replaced. The workflows cover what a host cannot, such as
  catalog freshness from GitHub. They cannot reach a session, and they cannot see a host's installed versions.
- **The raw saturation count as `due_layers`.** Rejected. The report calls every layer that is not a saturation
  candidate due, which is 32 of 32 today. The file would never be removed and the line would print in every
  session. The sweep recipe's own cadence is "Sweep only the due layers, at most monthly ..., or sooner when a
  reopen trigger fires", so `due_layers` follows the monthly cadence and `reopen_triggers` covers the "sooner".
  `--sweep-cadence-days 0` restores the raw count.
- **Counting the `pin_behind_upstream` rows of the latest dated manifest in `pins_behind`.** Not adopted. The
  manifest is a snapshot of its build date, so a pin bumped since then still reads as behind. The weekly
  catalog-freshness rebuild is a workflow artifact, not a file on the host. Running
  `tools/sota-convergence/github_freshness.py` over every catalog repository each day is out of proportion for a
  notice. `--network` runs the bounded runtime-worker skill check instead.
- **A monotonic timer (`OnUnitActiveSec=1d`), as the host-request poll uses.** Rejected. That poll needs no
  catch-up because every poll reads the full current state. A daily notice on a WSL distribution that is often
  stopped does need one, and `Persistent=` applies only to `OnCalendar=` timers.
- **Removing the earlier due-file when a run fails.** Rejected, because it would hide due items exactly when the
  checks break. A failed run leaves the state directory as it was, the unit shows in
  `systemctl --user --failed`, and the hook's 48-hour age limit below keeps an old line from lingering.
- **Counting an incomplete skill check as nothing due.** Rejected. The first draft did, and a `--network` run whose
  `gh api` calls failed, or whose skill pin did not verify, could delete the notice an earlier run had written (found by
  the cross-family review of that draft and reproduced by the failing-first tests below). The check's own report says
  "Incomplete fetches remain unknown" (`tools/adoption/runtime_skill_freshness.py:134`). Unknown is not nothing due,
  so an incomplete run never removes the file.
- **Exit 2 for an incomplete skill check.** Not adopted. No `gh` login and a rate limit are expected conditions, not
  internal errors: exit 2 would fail the unit every day and withhold the offline counts, which are known. The run
  exits 0, writes what it found or leaves the state directory as it was, and records the gap.
- **A details command that prints the saved file instead of running the checks again.** Not adopted. The command
  exists to confirm that what the notice names is still due, and a saved copy shows only what the timer saw. The
  command repeats the options that change what a run reports instead, so that it reproduces the notice.

## Decision

1. **The checks run in a daily timer, never at startup.**
   [`stack-currency.timer`](../../adoption/templates/systemd/stack-currency.timer) sets `OnCalendar=daily`,
   `Persistent=true` and `RandomizedDelaySec=15m`.
   [`stack-currency.service`](../../adoption/templates/systemd/stack-currency.service) is a `Type=oneshot` unit
   that runs `/usr/bin/python3 @REPOSITORY@/scripts/currency_due.py`. It sets `UMask=0077`,
   `NoNewPrivileges=true`, `Nice=10`, the best-effort I/O class, `TimeoutStartSec=900`,
   `PYTHONDONTWRITEBYTECODE=1` and an explicit `PATH` that holds the ecosystem bin directory. That `PATH` is
   load-bearing. The workstation's user manager uses
   `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin`, which finds
   none of the six exec probes of the default profile. A dry run with that `PATH` read `pins_behind` 0 with 7
   components unchecked, against 1 and 1 with the unit's `PATH`. The install recipe is in `adoption/lifecycle.md`.
2. **The writer.** `scripts/currency_due.py` runs the three checks as subprocesses of the same checkout, with the
   arguments the workflows use. As in `saturation-tracking.yml`, the receipt report reaches
   `saturation_ledger.py --staleness` as a file. It derives four counts:
   - `pins_behind`: the distinct `mismatched` ids across the selected profiles
     (`scripts/adoption_status.py:1266-1270`). With `--network` it adds the skill pins in `skill-drift`,
     `repository-drift` or `removed-at-head`, a skill pin in `invalid-pin` (the fetch succeeded and the manifest's
     recorded tree is not the tree at the pinned ref, so it is an answer, and a detail of its own kind) and a
     drifted skills CLI pin (`tools/adoption/runtime_skill_freshness.py:77-81,103,152`). A mismatch can also mean the
     installed version is ahead of the pin; the detail entry names the component and the pin.
   - `stale_receipts`: the report's `flagged` count (`scripts/receipt_staleness.py:162`).
   - `due_layers`: the layers the saturation report marks due whose last completed sweep is at least
     `--sweep-cadence-days` old (default 30), or that have no datable sweep. The default follows
     `recipes/saturation-sweep.md:20-21` and matches `receipt_staleness.py`'s 30-day `DEFAULT_MAX_AGE_DAYS`
     (`:60`). The raw count stays in the `coverage` detail as `due_layers_total`.
   - `reopen_triggers`: the number of layers in `current_reopen_triggers`
     (`scripts/saturation_ledger.py:999-1000`); the report's own summary counts layers too (`:1022`).

   The script writes `${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/currency-due.json` only when a count is
   nonzero, and removes the file otherwise, unless a `--network` skill check was incomplete: an error in its report,
   a skill left `unfetched` or in a state the script does not know, or a skills CLI release that was not fetched.
   That run writes the file when a count it did reach is nonzero, with the gap in the `coverage` detail
   (`skills_complete`, `skills_fetch_errors`, `skills_unresolved` and the first five error strings, which the
   check keeps value-free, `runtime_skill_freshness.py:46-47`), and otherwise leaves the state directory as it was.
   Its line says `nothing known due` and its journal entry says `kept` or `no due-file`. A relative
   `XDG_STATE_HOME` is ignored, as the XDG specification requires. The write goes through a mode-0600, fsynced
   temporary file in the same directory and `os.replace`, the pattern of `saturation_ledger.write_ledger`
   (`scripts/saturation_ledger.py:1159-1177`). The document's keys are `generated_at`, `root`, `due`, `summary_line` (at
   most 160 characters), `details_command` and `details`. The line ends with `python3 <checkout>/scripts/currency_due.py --dry-run`,
   the inspected checkout's own copy of the script by its absolute path (written as `~/...` under the home
   directory, which every shell expands), plus `--network` and a non-default
   `--sweep-cadence-days N` when the run used them, so that running the command reproduces the notice from any
   working directory: the user-scope SessionStart hook prints the line in whatever project a session starts in,
   where a cwd-relative command would run in the wrong checkout or none (GPT-6 review of #539). A checkout
   without the script is named by `--root`. When the absolute command would leave the counts fewer than 12
   characters, the line ends with `cat <due-file>` (`cat ~/.local/state/native-agent-stack/currency-due.json` by
   default), a short runnable command that prints the document, whose `details_command` field carries the full
   command and whose `root` field names the checkout; when even that does not fit (a state-directory path of more
   than about a hundred characters) the line ends with the constant `currency-due.json in the state directory`.
   The line never falls back to a cwd-relative command, and the writer refuses (exit 2) rather than write a line
   over 160 characters (GPT-6 review rounds 3 and 4). A `stack-currency` launcher on the
   ecosystem `PATH` would make the command short on every host; it is not part of this change because installing
   it is a host step of the full-profile bootstrap. The document's keys are now `generated_at`, `root`, `due`,
   `summary_line`, `details_command` and `details`. The option is bounded to 36500 to keep the line short. The unit passes neither, so its
   notice ends with the bare command, and a test compares the flags in the unit's `ExecStart` with the flags the
   command names. The script exits 0 whether or not anything is due, and 2 on an internal error, which leaves the
   state directory as it was. That includes a report field of the wrong type. It makes no network call unless
   `--network` is given, and the unit does not pass it. It refuses a state directory inside the checkout.
3. **The startup rule.** Item 4 of `docs/token-practice.md` now allows exactly one read-only SessionStart line from
   that file, printed fail-open; the checks never run at startup. `AGENTS.md:28` still reads "Do not rerun the full
   audit or model trials at startup", which this design keeps. Any change to that wording is unit F1's.
4. **The contract for the hook in unit F2, which this change does not contain:**
   - Read only that file and print its `summary_line` as plain stdout. Exit 0 in every case.
   - Print nothing when the file is missing, unreadable or not a JSON object, when `summary_line` is not one line
     of at most 160 characters, or when `generated_at` is more than 48 hours old, because a failing timer leaves
     the last file in place. The file was 7,175 bytes on the workstation on 2026-09-30.
   - Print only for the `startup` source, and for `clear` if the line is wanted after a context reset. Skip
     `resume`, `compact` and `fork`: Claude Code saves injected text in the session transcript.
   - The acceptance gate, which F2 measures and this change did not: `claude -p ok --output-format json` shows an
     input plus cache-creation token delta of 0 without the file and at most 60 tokens with it, and the hook
     finishes within 50 ms.
5. **Evidence on this branch.** None of it is an unchanged upstream test.
   - `tests/test_currency_due.py`, integration checks with synthetic fixtures: fake checks that print the four
     reports' shapes. They cover no file when nothing is due (an earlier file removed), an atomic 0600 write with a
     line of at most 160 characters, a failed rename that keeps the earlier file, exit 2 and no write for malformed
     output from each check and for a malformed ledger, dry runs that write nothing, the cadence boundary (30 days
     counts, 29 does not), network checks off by default, and the two units' settings. Seven patched mutants of the
     first draft (`8d371e9e`: no removal, a direct non-atomic write, no cadence gate, no truncation, network ignored,
     adoption exit 2 rejected, a relative `XDG_STATE_HOME` accepted) were each caught by the test named for them, in
     eight runs: the direct write was run against both the failed-rename test and the file-mode test. One test runs
     this checkout's real checks dry.
   - Repair of the cross-family review of `3d1cfada` (three findings, each checked against the source first). The
     tests were written first and run against the unrepaired script: 43 tests, 19 failures and 13 errors in 15 of
     them, among them seven `FileNotFoundError` (the earlier due-file deleted), `TypeError: 'bool' object is not
     iterable` at `currency_due.py:199` (and the same for an integer and for an unhashable id) and a notice command
     without `--network`. They pass on the repaired script (43 tests, OK). They cover: an incomplete skill check
     keeping an earlier file byte-identical and creating none, for six incomplete shapes; the control that a complete
     check with nothing due still removes it; an incomplete check that still writes what the other checks found; an
     invalid pin counted, replacing the earlier file; the command in the notice run in process for `--network`, for a
     non-default cadence and for both, each reporting the notice's counts again (for the first two, the bare
     command reports nothing due); the `ExecStart` flags of the unit equal to the flags the command names (a
     consistency check that also passes on the unrepaired script); the cadence bound; the
     next-step line; eight malformed `pinned_versions` shapes exiting 2; and a shape test that replaces each of
     2,277 nested report fields by wrong-typed values and requires a document or a `CheckError`. Thirteen patched
     mutants of the repaired script (removal for an incomplete check, an incomplete check read as complete, errors
     ignored, an invalid pin not counted, an unknown state read as current, an unknown release ignored, no write
     beside an incomplete check, the command without `--network` or without the cadence, the old `pinned_versions`
     read, "nothing due" for an incomplete run, no cadence bound, a next step that always names
     `adoption_status.py`) were each caught by a test written for them.
   - A dry run on the workstation at the first draft: exit 0 in 1.56 s, and 1.57 s under `/usr/bin/python3` 3.12.3
     with the unit's `PATH` and a cleared environment. After the repair: exit 0 in 1.59 s with `HOME` redirected to
     a scratch directory, because the version probes create files under `HOME` (`.codex/tmp` appeared there), and
     the same counts as the first draft: 1 pin behind, 7 stale receipts, 12 layers with reopen triggers.
   - `systemd-analyze --user verify` on both units rendered with the documented `sed` command: exit 0 with no
     warnings, before and after the repair (which changed a header comment only). A copy with an unparseable
     calendar and a missing interpreter failed the same check, exit 1, in both rounds.
     `systemd-analyze calendar daily` normalizes to `*-*-* 00:00:00`. These are synthetic checks; no unit was
     loaded or started.

## Overturn condition

- F2's gate fails, meaning the line costs more than 60 tokens or the hook takes more than 50 ms: shorten the line,
  or move the notice to a channel that does not enter the model's context.
- Claude Code gains a native session-start notice outside the model's context: use it instead of a hook.
- A month of daily runs leaves the file present on most days without a resulting action, or the weekly workflows
  report a due item that the file misses: retune the counts or the cadence, which are the policy choices recorded
  above.
- The catalog-freshness result becomes a file on the host that is refreshed at least weekly: add its
  `pin_behind_upstream` rows to `pins_behind`.
- A check's JSON shape changes: update `aggregate()` in the script. Its tests quote the shapes it reads.

## Sources

Fetched on 2026-09-30.

- systemd.timer(5), <https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html>. `Persistent=`:
  "the service unit is triggered immediately if it would have been triggered at least once during the time when
  the timer was inactive. Such triggering is nonetheless subject to the delay imposed by RandomizedDelaySec=. This
  is useful to catch up on missed runs of the service when the system was powered down. Note that this setting only
  has an effect on timers configured with OnCalendar=." `RandomizedDelaySec=`: "Delay the timer by a randomly
  selected, evenly distributed amount of time between 0 and the specified time value ... useful to stretch
  dispatching of similarly configured timer events over a certain time interval, to prevent them from firing all
  at the same time". The workstation's `man systemd.timer` (systemd 255.4-1ubuntu8.17) has the same `Persistent=`
  text.
- systemd.time(7), <https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html>:
  `daily → *-*-* 00:00:00`.
- Claude Code hooks, <https://code.claude.com/docs/en/hooks>: "For most events, Claude Code writes stdout to the
  debug log and doesn't show it in the transcript. The exceptions are `UserPromptSubmit`, `UserPromptExpansion`,
  `SessionStart`, and `PostModelSwitch`, where Claude Code adds plain-text stdout as context that Claude can see and
  act on." The SessionStart matcher values are `startup`, `resume`, `clear`, `compact` and `fork`, and "Claude Code
  saves the injected text in the session transcript".
- XDG Base Directory Specification, <https://specifications.freedesktop.org/basedir-spec/latest/>: "If
  $XDG_STATE_HOME is either not set or empty, a default equal to $HOME/.local/state should be used", and "If an
  implementation encounters a relative path in any of these variables it should consider the path invalid and
  ignore it."
- Python, <https://docs.python.org/3/library/os.html#os.replace>: "If successful, the renaming will be an atomic
  operation (this is a POSIX requirement)", and it "may fail if src and dst are on different filesystems", which is
  why the temporary file is created in the state directory.
  <https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp>: "The file is readable and writable only by
  the creating user ID."
- This repository: `recipes/saturation-sweep.md:20-21,36-37`, `recipes/sota-convergence-practice.md:9`,
  `scripts/receipt_staleness.py:60,156-164`, `scripts/adoption_status.py:1258-1263,1266-1270,1331,1400`,
  `scripts/saturation_ledger.py:966-1002,1022,1159-1177`,
  `tools/adoption/runtime_skill_freshness.py:46-47,77-81,100-103,115,134,152,154`,
  and the unit conventions of `adoption/templates/systemd/credential-boot-receipt.service` (the `@REPOSITORY@`
  render) and `host-requests-workstation.service:26-28` (an explicit `PATH`).
