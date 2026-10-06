# Organic-invocation E2E v1.1: the command center's decisions (2026-10-06)

- **Source:** command-center item `task-ns2604-coop-20261006T105529Z`, section "Organic E2E v1.1: the CC's decisions before the pilot", sent 2026-10-06 at 10:55Z. The decisions below keep that item's numbers.
- **Confirmations:** command-center item `task-ns2604-coop-20261006T114319Z`, sent at 11:43Z, settles the five points this file had marked for confirmation. Each is recorded below as "Confirmed (CC 11:43Z)", with its point number.
- **Rulings of 12:30Z:** command-center item `task-ns2604-coop-20261006T123036Z` confirms one interpretation and extends decision 1's timing record to every cell. Both are recorded below as "Confirmed (CC 12:30Z)".
- **Structural G13 of 13:29Z:** command-center item `task-ns2604-coop-20261006T132948Z` replaces decision 3's classifier-based invalidation with a structural G13: the answer sources are hidden from every trial's mount namespace, and the command classifier becomes a diagnostic tag. It is recorded first below, and it governs wherever earlier sections describe G13's invalidation.
- **Applies to:** PROTOCOL-v1.1.md (organic-e2e-v1.1-20261005), which stays verbatim, and PILOT-SPEC-v1.1.md. Where they differ from this file, this file governs from 2026-10-06 10:55Z.
- **Harness:** each decision's code is in `harness/`, in the commit that adds this file.
  - `CC_V11_DECISIONS` in `harness/common.py` names the item.
  - `prepare.py` writes this file's sha256 into run.json as `amendment_file_sha256`.
- **Status:** no pilot or smoke has run under these changes. The checks under Verification are synthetic or offline.

## Structural G13 (CC 13:29Z)

Item `task-ns2604-coop-20261006T132948Z` decided that a classifier of the commands a model typed cannot converge, because shell grammar always has another form: aliases, xargs, find actions, subshells, `python -c`, here-docs. So G13 is now structural. `harness/isolation.py` implements it.

1. **Every listed answer source is hidden from each trial's mount namespace.** Two components run each trial's client process tree under bubblewrap:
   - the launcher, for every CLI and SDK cell and for the prompted and gate-0 cells;
   - block.py, for CL7b, through the provider's `codex_path_override`, which points at a per-attempt wrapper.
   - **Empty tmpfs:**
     - the coordination state: every run root with its oracle runs, other trials' drafts, grades, run.json and gate0.json; the suite cards; the v1 captures;
     - the fixture cache: oracles.json, oracle-work, the templates and the tarballs.
   - **Empty tmpfs with the trial's own entries bound back:**
     - the fixtures folder `~/.cache/ws`: the trial's own fixture only;
     - the trial-files folder `~/.cache/wsr`: the trial's own prompt, settings, clone and -o file, and the run's neutral binaries;
     - the Claude projects folder: every project outside the experiment's roots, and the trial's own.
   - **A fresh per-trial folder over each per-session client store:**
     - the shared Codex sessions folder, which the clone's `sessions` alias points at;
     - Claude's file history;
     - context-mode's per-project session and content stores, for both clients (its root stays shared);
     - Claude's `/tmp/claude-<uid>` area.
     After the trial, its rollouts are published to the native sessions folder for collect.py. No isolated trial sees that folder. A failed move or publish is recorded in the exit row as `finish_error`: it costs the copy, never the trial's exit row.
   - **Unchanged:** the native home and the client configuration stay visible and writable, and the network and the environment are as before. The system runtime is read-only, as in the R2a replay's isolation.
   - **Nested sandboxes** (Codex's own, `unshare -rm`, a nested bwrap) run in a namespace below the trial's. The trial's mounts are locked there, so a nested process cannot unmount a hidden tmpfs.
   - **The wrapper:** bubblewrap 0.11.1 (`/usr/bin/bwrap`, Ubuntu 0.11.1-1ubuntu0.3, upstream containers/bubblewrap), unprivileged. Its options are read from a memfd (`--args`), so the namespace's PID 1 shows none of them.
     - Options relied on: `--args`, `--ro-bind`, `--bind`, `--bind-try`, `--dev-bind`, `--tmpfs`, `--proc`, `--unshare-pid`, `--die-with-parent`, `--chdir`, `--info-fd`.
     - Not `--new-session`: the launcher's TERM must reach the client for a graceful exit. So the launcher signals the tree below the wrapper, and kills the group only after 30 s.
   - **The item's fallback is not used.** That fallback is systemd's `InaccessiblePaths=` in a transient user unit (systemd 259, systemd.exec(5)). bwrap hosts every launch path, as the self-test's client checks show:
     - `claude --version` and `codex --version`;
     - Codex's own sandbox, nested in bwrap;
     - the CL6 and CL7 SDK imports;
     - `codex app-server --help` through the CL7b wrapper.
2. **G13 checks what was hidden** (`isolation.check`). The launched row's `isolation` receipt records:
   - the wrapper's argv, both as bwrap parses it and as a process listing shows it;
   - its mount operations;
   - the hidden list, with each path's sha256 and, for a file, its content's sha256.

   G13 passes when all of the following hold:
   - every location the item lists for the trial is in the hidden list and covered by its mount;
   - nothing is bound back into a hidden root but the trial's own entries, and nothing re-exposes a root after its tmpfs;
   - the client tree ran in a mount namespace of its own (bwrap's `--info-fd` record);
   - no process the launcher sampled in the tree was in the host's mount namespace (processes in a nested namespace are counted apart);
   - stage 1's wrapper-only self-test passed (`isolation-selftest.json`).

   Gate 0 requires that self-test and each stage-2 trial's receipt check, and a failed self-test refuses stage 1. A trial is valid only if its own check passes.
3. **Optional audit, never a gate.** A fanotify listener held by root on the hidden roots, filtered to the trial tree's pids, would corroborate the receipts.
   - An unprivileged listener (Linux 5.13 and later) may mark only inodes, not a mount or filesystem, and does not receive the pid that generated an event (fanotify_init(2), man-pages at man7.org). So the pid filter needs CAP_SYS_ADMIN.
   - The harness runs no sudo, so the audit stays a documented option.
4. **The command classifier is a diagnostic tag only.** `grade.reach` still records the categories and the answer-source reads it recognises. G13 reports them under `classifier_diagnostic`, and they never invalidate a trial.
   - **Superseded:** the two P2s of the GPT micro-check of 1f81d645 (`cc-reads-20261005/pr786/GPT-VERDICT-1f81d645f.md`, outside the repository).
     - F1: patterns and unrelated listings were taken for reads, and some content searches were missed.
     - F4: the trial's own clone's sessions alias was exempted before classification.
   - Both concern the classifier, which no longer decides validity, and the alias is now hidden structurally.
5. **The P3 of that micro-check is fixed.** The deadline and completion decisions read the launcher's unrounded offsets (`duration_exact_s`, `time_to_result_exact_s`, `common.decision_times`):
   - the hold;
   - the launcher's result-before-T rule and its censoring reason;
   - the grader's completion re-check (`effective_exit`) and its no-result list.

   The one-decimal fields are presentation only. So a result at 1799.96 s, in a session that ran 1800.02 s, is complete, not held.

**Limits:**
- Services reached over a socket run outside the namespace: the ai-memory server, MCP servers configured by URL, the OmniRoute gateway, and a user systemd or Docker daemon. A file such a service reads for a trial is not hidden by the mount namespace; R10's per-trial scoping of those stores still applies.
- `/tmp` and `/dev/shm` stay shared outside Claude's own area.
- A setuid helper (sudo) does not work inside the user namespace.

## Confirmed (CC 11:43Z)

Item `task-ns2604-coop-20261006T114319Z` confirms the five points, with three additions the harness now implements:

1. **The no-result hold applies to every Claude cell,** not only claude-env. One rule for all Claude cells keeps the arms symmetric.
   - The launcher's `holds_cell()` depends only on the client and the deadline evidence: the elapsed time and when the result arrived (see the 87f9f1d7 fixes below).
   - It never depends on the cell, arm, kind (CLI or SDK) or stage.
2. **gh counts as PATH-only.** It is also reported in its own "vendor-skill surface" stratum: a tool reached through a client vendor's official skills repository. `CLI_VENDOR_SKILL_SURFACES` holds gh through openai/skills@49f948fa (gh-fix-ci, gh-address-comments). Such trials stay out of OIR and are counted per item as `n_vendor_skill_surface` and `used_vendor_skill_surface`, with a use rate and its Wilson interval.
3. **The answer-source list stands as written.** Two classes are added, and the principle is set: reading a source is legitimate work; reading an oracle's output is not. A host checkout's copy of an oracle input stays a tag.
   - Grader expected-output files outside oracles.json:
     - everything under the coordination state directory (run roots with run.json's oracles_reproduce, grades and gate0.json; the suite cards; prompted and stage-0 outputs);
     - the whole fixture cache (oracle-work/ beside oracles.json);
     - any published file of this experiment other than its sources (the harness, the protocol, the pilot spec, these notes, a README), such as a later grade or receipt in the repository;
     - any path that `prepare.py --answer-source-path` declares.
   - Earlier smoke or pilot receipts holding graded outputs: the v1 and v1.1 smoke and pilot captures all sit under the coordination state directory (or, for the U1 probe, the fixture cache), so they are covered. A later published one is covered by the rule above.
   - Another trial of the same task now also matches by trial id, which covers its Claude transcript and its trial-root answer file as well as its fixture.
   - The 2026-10-04 foundation E2E receipts in the repository (`evidence/artifacts/ns2604-e2e-20261004/`) grade another E2E, and three suite tasks use their `slots.json` and `summary.json` as input, so reading them stays legitimate source work.
4. **The re-baseline cost holds** because the Codex trials in flight form one Codex cell, the arm's concurrency unit, while Claude adds one trial.
   - The pilot runs one Codex cell at a time; stage 2 and stage 3 cells, and stage 4's Codex blocks, run one after another.
   - `rebaseline_cost_ok()` checks the bound at every re-run, CL7b included: at most one Claude trial and one Codex cell. If the Codex re-runs ever spanned two cells, it falls back to one trial per arm. Past either bound, the run stops.
   - G4 reports the cost (`rebaseline_cost`).
5. **0.15 of a window per trial is the starting default.**
   - After the first stage-4 Claude block that yields an organic trial with two meter readings, `pilot.py` recalibrates it to the measured p90 per trial, per window (`meter_calibration()`: nearest rank, account-wide deltas, at least the meter's 0.01 resolution). It writes the result to `meter-calibration.json` in the run root, with the value it replaced.
   - Left out of the calibration:
     - a trial with fewer than two in-stream readings (its first reading is also its last, so its delta would be a false 0);
     - a window whose `resetsAt` differs between the two readings (it rolled over mid-trial).
   - The operator step is `grade.py meter-calibration --run-root <root> [--write]`.
   - The value each trial started with is recorded in its ledger rows (`expected_usage`, `meter_expected_usage`) and in the grade (`meter_expected_usage`, with the calibration and the current p90).
   - On smoke-20261006c's three organic Claude trials, the p90 would be 0.06 (five-hour) and 0.01 (seven-day).

## Confirmed (CC 12:30Z)

Item `task-ns2604-coop-20261006T123036Z`:

- **(a) The 2026-10-04 foundation E2E receipts stay sources.** Confirmed; no code change.
  - The files in `evidence/artifacts/ns2604-e2e-20261004/` grade another E2E, and three suite tasks read `slots.json` and `summary.json` as input.
  - A file there would become an answer source only if it held a graded output of this experiment's own trials. None does today.
- **(b) The final-turn time and the result-event time are recorded for every cell,** Codex included (CL3, CL4, CL7, CL7b and the prompted and gate-0 cells), so the comparison keeps one schema across arms. In a Codex cell the two normally coincide.
  - **Launcher Codex cells:** the final turn ends with the last `agent_message` that no tool item follows, and the result event is `turn.completed` (or `turn.failed`). Both are recorded in the exit row's `final_turn_end_s`, `final_turn_end_at`, `time_to_result_s` and `result_event` fields, as for Claude.
  - **CL7b and runs prepared earlier:** CL7b has no launcher. For it, and for runs prepared before this ruling, the grader reads both times from the main rollout's own timestamps (`codex_turn_times`: the last `AgentMessage` with no tool item after it, and `task_complete`).
  - **Grade report:** it lists both times for every launched trial (`completion_times`). It also checks that every Codex trial carries both (`timing_record`, which lists any Codex trial missing either).
  - **Smoke-20261006c:** all 11 Codex trials carry both times in the read-only re-grade. The two times sit 0.1 to 0.4 s apart in most, with a few seconds between them in two of the 11 (8.4 s and 3.4 s).

## Fixes from the GPT micro-check of 87f9f1d7 (2026-10-06)

That check requested changes for four P2s (`cc-reads-20261005/pr786/GPT-VERDICT-87f9f1d72.md`, outside the repository). Each is fixed.

Findings 1 and 4 tune the command classifier. The GPT micro-check of 1f81d645 found both still partial, and the structural G13 of 13:29Z supersedes them (see the first section): the classifier described here is now a diagnostic tag. Findings 2 and 3 stand.

1. **Filename-only operations invalidated trials.**
   - Access is now judged from each command's arguments and each tool's output mode.
   - **Content access:**
     - a program that prints content or runs code over it;
     - grep or rg printing matching lines;
     - find (every `-exec`, `-execdir`, `-ok` or `-okdir` action) or xargs running such a program, judged by that program's own arguments (`find ... -exec grep -l` and `xargs grep -l` return names only). xargs options are read as the installed GNU findutils xargs 4.10.0 `--help` lists them, so `-i`, `-l`, `-e` and `--replace` take no separate word;
     - git show, cat-file, blame, diff and grep, including after global options such as `git -C <dir>`;
     - tar or unzip to stdout;
     - an input redirection;
     - the Read tool, and the Grep tool in content mode.
   - **Names or metadata only, so a tag:** ls, find, stat, file, realpath, wc, git ls-files and status, rg --files, grep or rg with -l, -L, -c or -q, cp, mv and rsync, Glob, and the Grep tool's default `files_with_matches` and `count` modes.
   - **A filter fed by a pipe:** when it names no file (`ls <dir> | head -n 5`, `... | sort -r`, `... | grep x`), it reads the previous command's output, not a file, so it is no read.
   - Only successful content access that returned content can make an answer source invalidate a trial.
2. **CL7b repetitions shared one attempt.** Chosen: the smaller correct change, which is to reject a CL7b repeat above 1 until each repetition gets its own attempt.
   - `block.py` refuses such a block, and `prepare.py` refuses `--repeat-override` above 1 while `codex-app-server` is among the cells. Nothing is written in either case.
   - The pilot's CL7b repeat is 1, and a re-run is a new block, which gets a fresh attempt.
3. **The hold missed a timeout that needed SIGKILL.**
   - The hold now reads the evidence (`deadline_without_result`): the session ran to T or past it with no result event before T, however it ended. That includes the timeout's SIGKILL after its grace (rc 137, now censored as `timeout_killed`) and a launcher kill at or after T.
   - A session that fails or is killed before T is still `killed` and does not hold its cell.
   - The grade's `no_result_trials` uses the same rule.
4. **Same-task Codex transcripts stayed tags.**
   - The grader now maps each Codex trial to its thread ids (`codex_threads_by_trial`): the thread collect.py joined, plus every collected rollout, main and child, whose file name ends with its thread id.
   - A successful content read of a same-task trial's rollout is an answer source (`same-task transcript`), whichever copy it reads: the native original under `~/.codex/sessions`, a clone's alias of it, or a collected copy.
   - A glob or directory-wide read (`cat ~/.codex/sessions/.../*.jsonl`, `rg` over `~/.claude/projects`) names no id in its input. For such a successful content read, the content it returned is scanned for same-task trial and thread ids (`answer_source_evidence: returned content`).
   - The scan runs only when the read itself reaches a transcript, a store or another G13 location. That is judged from:
     - its operands;
     - the directory of an earlier `cd` in the same command;
     - for a read whose operand comes from another command (a loop variable, `{}`, a command substitution, xargs), every path the command names;
     - for an interpreter whose program comes from a heredoc (`python3 - <<'PY'`), the whole command text.
   - A listing beside an unrelated read (`ls ~/.codex/sessions/... && cat notes.md`) is therefore not scanned, and neither is a listing piped into a filter.
   - **Known limits:** a script file run by an interpreter (`python3 x.py`) and a `cd` from an earlier call are not followed. Their returned content is not scanned, though the reasons judged from the input still apply.
   - Other tasks' transcripts stay tags.

## Fixes from the GPT first-pass read of 5aa2bfdc (2026-10-06)

That read requested changes for seven P2 findings (`cc-reads-20261005/pr786/GPT-VERDICT-5aa2bfdc9.md`, outside the repository). Each is fixed in the harness:

1. **Clone hook-trust changes passed G4.**
   - A hook or project trust change in the trial's own clone (`CLONE_TRUST_KEYS`) is now persistent on its own (`s7_persistent_change` reports `clone_trust_changed`). The launcher stops the run for it, and no re-baseline absorbs it.
   - G4 fails on it for every launched trial (`clone_trust_changed_trials`), re-baselined ones included.
   - CL7b compares its clone's trust before and after each attempt (`clone_trust_view`) and stops the run on a change.
2. **Concurrent exits could stop an accepted re-baseline.**
   - `try_rebaseline` now judges the change again inside the lock, against the baseline in force at that moment. An exit whose change another exit already absorbed gets `absorbed` and is re-run without a STOP. The launcher then refreshes its S7 judgement against that baseline.
   - Only an additional change, a refused key or a new trust entry stops the run.
3. **A resume counted interrupted attempts as done.**
   - An attempt now counts toward its test's repeat only when its last exit is terminal and not carried forward, or while it is still running.
   - On resume, `reconcile_orphans()` gives an attempt that launched without an exit, and whose processes have ended, an `interrupted` exit, and carries it forward.
   - A launcher failure after the launch row writes `launcher_error_after_launch`, also carried forward.
   - Launch rows are never removed, so the Claude session cap still counts every actual launch.
4. **CL7b rate limits were consumed.**
   - The block keeps a sanitized class of the provider's own error (`classify_provider_error`; never its text).
   - A CL7b rate-limit error marks the attempt `rate_limited`, sets STOP.codex as a Codex launcher trial's limit error does, and is carried forward.
   - The block's account-wide gateway counts never mark a trial on their own.
5. **CL7b re-runs reused the first attempt's identity.**
   - Every CL7b attempt after the one stage 1 built gets its own trial id, fixture, clone and provider config, under the same test ref (`allocate_app_server_attempt`), with its own ledger rows.
   - Attempts are counted per trial id, so a carried attempt never suppresses a later one, and G10 reads the re-run, not the carried attempt.
6. **G13 invalidated mentions and failed reads.**
   - The reach classifier now keeps each call's status, access type and returned content (`call_access`).
   - Only a successful read that returned content can make an answer source invalidate a trial. A path that is mentioned, listed, written, or read without success stays a tag (`answer_source_mentions`).
   - That is the 11:43Z principle: reading the oracle's output is what invalidates.
7. **G11 passed with no forwarded effort.**
   - `g11_trial_ok` requires an observed, nonempty forwarded-effort value.
   - Pipeline exposure is reported apart, and the calls with no value are listed (`gateway_calls_missing_forwarded_effort`).

## 1. Censoring (finding 3)

**Decision:**
- T rises to 1,800 s.
- Each cell records two times: the model's final turn end and the result event.
- A cell is complete only when its result event arrives. A final turn alone is not completion, because background Workflows may still be running.
- If claude-env still gives no result by 1,800 s, the cause is diagnosed before the pilot goes on. A background workflow that never ends is one example.

**Harness:**
- **`common.py`:**
  - `T_SECONDS = 1800`. The protocol's 900 s stays as `PROTOCOL_T_SECONDS`, for runs prepared without a completion record.
  - `CLAUDE_COMPLETION_DEFAULT = "complete-at-result"`.
- **`prepare.py`:**
  - These are the stage-1 defaults, and run.json records this decision as their amendment.
  - Another policy or T needs its own `--amendment-ref`.
  - T applies to every cell, including CL7b's turn timeout.
- **`launcher.py` completion rule (unchanged):** a result event before T completes the trial. A result written at or after T, on the timeout's SIGTERM, censors as `timeout_after_result`.
- **`launcher.py` records per trial (Claude since decision 1, Codex since the 12:30Z ruling):**
  - `final_turn_end_s` and `final_turn_end_at`: the main thread's last assistant text with no later tool call or tool result. Claude Code 2.1.291 leaves `stop_reason` unset on stream-json assistant events, so the content decides.
  - `time_to_result_s`, and the result event's own fields.
- **`launcher.py` when a Claude trial has no result before T:**
  - It writes a `no_result_diagnosis` with:
    - whether the final turn ended;
    - the last main-thread event;
    - open tool calls, by name;
    - background-task counts and types;
    - the processes at the last poll.
  - It writes `HOLD.<cell>`. Later trials of that cell are refused as `held_for_diagnosis` and carried forward until the operator removes the flag.
  - `block.py` refuses the cell's blocks too, so pilot.py's Claude chain stops at that cell's next test until the flag is gone.
- **`grade.py`:**
  - For runs whose launcher predates this decision, it reads the same two times from the stream.
  - The grade lists them as `completion_times` and `no_result_trials`.
- **Confirmed (CC 11:43Z), point 1:** the hold applies to every Claude cell, not only claude-env (`holds_cell()`).
  - Since the 87f9f1d7 micro-check, the rule reads the evidence, not the exit code: the session reached T with no result event before T. A timeout that needed SIGKILL therefore holds the cell too.
- **Confirmed (CC 12:30Z), (b):** the two times are recorded for every cell, Codex included (see that section).

**Offline re-grade of smoke-20261006c:**
- claude-native's final turn ended at 578.7 s, and its result event reports duration_ms 575,920. The result arrived at 900.7 s.
- claude-env never ended its final turn: its last main-thread event was a tool call. It gave no result.

## 2. Exposure (finding 17)

**Decision:**
- A CLI counts as exposed when its own upstream installer has put its native surface in place: a hook, a skill or an instruction file, as `rtk init -g` does.
- Presence on PATH alone does not count.

**Harness:**
- **`common.py` `CLI_NATIVE_SURFACES`** lists:
  - mineru: MinerU's own skill, opendatalab/MinerU `skills/mineru` at c221cc41, installed through the supported `--manifest` route (docs/decisions/2026-10-04-2604-e2e-fix-wave-g3-code-docs.md);
  - worktrunk: Worktrunk's own Claude and Codex plugins.
- **`grade.py` `cli_exposure()`** checks each trial's own listing: the Claude init's plugins and skills, and the Codex rollout's `world_state` skills catalog.
- **OIR:** a CLI target that is only on PATH is not exposed.
  - Its trials are counted in `not_exposed_path_only`, never as misses.
  - The item has no OIR of its own.
- **PATH-only under this rule:** every other CLI item, including:
  - gh: its skills gh-fix-ci and gh-address-comments come from openai/skills, not from gh's installer;
  - rtk on Codex: `rtk init -g` registers a hook that the per-trial clone leaves untrusted (§12.3), and Codex does not expand the `@RTK.md` line (§2.2).
  - On Claude, rtk is the hook item hook/claude/rtk, not a CLI item.
- **Confirmed (CC 11:43Z), point 2:** gh is PATH-only. Its trials are also reported in the vendor-skill surface stratum.

## 3. G13 host-checkout reads

**Decision:**
- Tag them; never deny them, because a deny changes the treatment.
- The primary analysis reports tagged trials separately.
- A trial is invalid only if it reads the task's gold or a fixture answer source.

**Harness (`grade.py`):**
- Every G13 reach category is a tag (`tagged`).
- These answer sources invalidate the trial:
  - the coordination category: run roots with the oracle runs and other trials' drafts, the suite cards, and the fixture cache with `oracles.json`;
  - the fixture or Claude transcript of another trial of the same task.
- G13 passes when no trial read an answer source. It also lists the tagged trials and their categories.
- OIR is reported per stratum (`oir_untagged` and `oir_tagged`, each with its Wilson interval) beside the pooled `oir`.
- **Confirmed (CC 11:43Z), point 3:** the list stands, with grader expected-output files outside oracles.json and earlier graded smoke or pilot receipts added (see the section above). A host checkout's copy of an oracle input stays a tag.
  - `answer_source_reasons()` names each reason: harness store, experiment output, declared grader output, same-task fixture or same-task trial.

**Offline re-grade of smoke-20261006c:**
- G13 now passes; it failed under the old rule.
- 3 trials are tagged: host-checkout 3, user-harness-file 1.
- No trial read an answer source.

**Superseded at 13:29Z** (item `task-ns2604-coop-20261006T132948Z`, the first section above). The tags stay, but answer-source reads no longer invalidate a trial; they are a diagnostic. G13 now checks that the wrapper hid every listed answer source. Under that rule the same re-grade fails G13 for want of receipts.

## 4. chrome-devtools

**Decision:** log it with a watcher only; no pre-execution deny.

**Harness:**
- The behaviour is unchanged. The watcher logs every chrome-devtools MCP call in both clients as a hit that does not halt the trial, and `grade.py`'s comment cites this decision.
- The harness adds no pre-execution rule for the server.

## 5. G10

**Decision:** the gateway entry is confirmed as best-effort. Record that call logs undercount clients that exit fast.

**Harness:**
- The G10 gate records this as `gateway_entry`.
- A missing entry stays a gap, never the gate, as at 9835f66c.

## 6. The §9.1 meter guard, amended

**Decision:**
- Compare the trial's expected usage with the remaining headroom.
- Don't require a quiet account: under the standing rule, limits never gate work.
- Mark any trial that hits a rate limit, and re-run it.

**Harness:**
- **Start rule:** start when expected usage ≤ 1.0 − utilization in both windows.
  - It is checked inside the lock and again on the trial's own first in-stream reading.
  - A window whose `resetsAt` has passed counts as fresh, so a reading taken before its own reset no longer blocks starts for up to 30 minutes.
- **Removed:** the 0.50/0.75 prior, the 0.80/0.85 kill thresholds and the +0.15 rise guard. All three read the account-wide meter.
- **Expected usage:** run.json `claude_meter.expected_usage`, set by `prepare.py --claude-expected-usage`.
  - The default is 0.15, the protocol's own per-trial fan-out bound.
  - The grade reports each trial's account-wide meter delta. The protocol's after-pilot rule uses m_p90.
  - **Confirmed (CC 11:43Z), point 5:** 0.15 is the starting default, recalibrated after the first pilot block to the measured p90 per trial and recorded per trial (see the section above).
- **Short of headroom:** the trial writes DEFER.claude with the window's reset time. pilot.py clears the flag on resume once the newest reading leaves headroom.
- **Rate limits:**
  - A Claude trial that receives a rejected `rate_limit_event`, or an error result naming a limit, is stopped and marked `rate_limited`.
  - It is carried forward and re-run, and DEFER.claude waits for headroom.
- **Codex (§9.2, not part of this decision):**
  - A limit error in a trial stream still stops the Codex chain (STOP.codex).
  - The trial is now marked `rate_limited` and carried forward, so the resume re-runs it.

## 7. In-run re-baseline

**Decision:** adopt it if it costs at most one extra cell per arm.

**Harness:**
- **One in-run re-baseline per run** (`REBASELINES_PER_RUN = 1`).
  - The first persistent S7 change becomes the run's new baseline: `s7/baseline-r1.json`, logged in `rebaselines.jsonl`. It can be found at a launcher trial's exit, or at a block's start when no block was running.
  - **Never absorbed** (`REBASELINE_REFUSED_S7_KEYS`):
    - the arm-defining files, ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md (§2.2);
    - ~/.claude/settings.json, whose hash the native arm's probe rests on (§2.1: a change needs a new probe);
    - every trust-bearing key: Codex `hooks_state`, the Codex project table and trusted set, the Claude trusted set, the trust fields of existing Claude projects, and removed projects;
    - a newly trusted project.
- **Cost:** the trials running at that moment are carried forward and re-run (`host_change_rebaselined`).
  - The Claude chain runs one trial at a time.
  - A Codex block runs up to its `-j` trials at once: 3 for codex-native and codex-env in the pilot, 2 for the SDK cells. So one re-baseline can re-run one Claude trial plus up to `-j` trials of the Codex cell in flight.
  - A CL7b trial, which has no launcher, is re-run when a re-baseline falls inside its eval.
  - A change found between blocks costs no trial.
- **What still stops the run, as before:**
  - any further persistent change;
  - a refused key;
  - a persistent change found at a block's end that no launcher absorbed. CL7b has no launcher, and a change after a block's last trial exits is seen only at the block's end; `block.py` writes STOP.
- **G4:** it lists re-baselined trials and the re-baseline instead of failing on them.
- **Confirmed (CC 11:43Z), point 4:** the cost holds, because the Codex trials in flight form one Codex cell, the arm's concurrency unit, and Claude adds one trial. `rebaseline_cost_ok()` enforces it, with one trial per arm as the fallback cap. Past it, the run stops.

## 8. RP4 (G11)

**Decision:**
- Enable the gateway's pipeline details only for the pilot runs.
- Keep only the effort fields in receipts.
- Then disable the pipeline details again.
- This is a host change, and the co-op applies it.

**Harness:**
- It never switches the gateway.
- From the pipeline details it keeps only `providerRequest.reasoning.effort` and `providerRequest.reasoning_effort` (`forwarded_effort`). It stores none of the rest of the payload.
- `prepare.py --gateway-pipeline-details on|off` records the operator's statement in run.json.
- The grade's G11 entry adds what the call logs showed: on, partly on, off or no calls.

**Offline re-grade of smoke-20261006c:** off (127 calls, none with pipeline details), so G11 still fails there.

## Not in this change

- **Decision 9:** Codex standalone web search returns 404 through the gateway (`/v1/alpha/search`). The fix is to the co-op's host profile wiring; neither this file nor the harness changes host configuration.
- **The `ack` row:** the item asks for one in the command-center ledger. That row is the co-op's to append.

## Verification (offline; no pilot or smoke)

- **The structural G13 and the P3 (13:29Z item):** `harness/test_isolation.py`, the harness's own focused module (`nice -n 19 python3 -B -m unittest -v test_isolation`), passes 26 of 26 tests on this harness. On the harness at 1f81d645, 3 of its 20 runnable tests fail and 16 error: there is no isolation module, and the decisions read the rounded fields. It covers:
  - in a synthetic trial's namespace (claude-like and codex-like), `cat` on a real file in each hidden location fails with ENOENT. The same files read outside the wrapper. The test fails if any is readable inside. The locations are:
    - this run's sibling trial's -o answer, settings, prompt, clone history, promptfoo output and fixture draft;
    - another run root, the v1 captures, the suite cards, the fixture cache's oracles.json and the command-center ledger;
    - another trial's fixture, its files and its Claude transcript;
    - a real Codex rollout, also through the clone's own sessions alias;
    - Claude's file history, context-mode's stores and Claude's /tmp area;
  - the trial's own fixture, prompt, settings, clone and neutral binaries, the native home's client configuration, and a Claude project outside the experiment stay readable;
  - writes to the shared sessions alias and to the -o folder land in the trial's own folders, and PID 1's argv shows no option or hidden path;
  - the receipt's hidden list, with path and content sha256s;
  - G13 failing on a missing location, a tmpfs left out, another fixture or an experiment's project bound back, the home re-bound after the tmpfs, a tree outside the namespace, and a missing receipt;
  - a nested `unshare -rm` that cannot unmount a hidden tmpfs and is counted apart, never as outside;
  - the launcher's wrapped run recording the namespace, and its kill reaching the client's TERM handler;
  - the client start checks;
  - finish() moving the -o file and publishing rollouts (into a temporary sessions folder), and CL7b's runtime record read back from the wrapper's info file;
  - the self-test report and the receipt serialising as plain JSON, as prepare.py and the ledger write them;
  - the P3 decisions on 1800.02 s and 1799.96 s.
- **The stage-1 self-test on this host** (`isolation.py selftest --clients`, no model call): 43 probes are hidden, all with ENOENT, and all 7 client checks pass. An S7 snapshot before and after it is equal, with no new trust.
- **Scratch suites of rounds 1 to 3:** they were kept outside the repository and were lost when the host restarted at 13:47Z. They were not re-run in round 4, so their results below are as reported when they ran.
- **Static checks:** every harness module parses (`ast.parse`) and imports. A stdlib `symtable` check found no undefined global names.
- **Synthetic checks:** 95 checks of the decision helpers, all passing. The script is kept outside the repository.
  - They cover headroom and resets, rate-limit hits, completion reasons, the hold flag, exposure, answer sources, effort-only fields, the re-baseline bound, each refused key class, the absorbed concurrent exit and the CL7b re-run rule.
  - 36 of them cover the 11:43Z confirmations:
    - the evidence-based hold rule on every Claude cell of the run of record;
    - the vendor-skill stratum and its counting;
    - each answer-source reason, and that sources and oracle inputs stay tags;
    - the re-baseline cost bound and its fallback;
    - the p90 calibration with its single-reading and rollover exclusions, the pilot hook and per-window headroom.
  - Eight of the checks run on smoke-20261006c's own streams and rollout, and one reads its run.json.
- **Red-green checks for the seven P2 findings:** 10 checks, kept outside the repository.
  - On the harness at 536487a4 all 10 fail; on this one all 10 pass.
  - They cover: the clone trust change (judgement, CL7b view, grader); the absorbed concurrent exit; the orphan reconciliation and counting; the CL7b rate-limit class; the fresh CL7b attempt and its counting; mentions, failed and empty reads; and G11's forwarded-effort value.
- **Red-green checks for the 87f9f1d7 micro-check and the 12:30Z timing ruling:** 12 checks in two scripts, kept outside the repository.
  - On the harness at 87f9f1d7 all 12 fail.
  - At feebace4, the first push of this round, 7 of 12 pass. The two checks of the first review fail (find or xargs with grep -l, `git -C`, and glob or directory-wide reads), and so do the three of the second review.
  - At 1c04fc79, the second push, 9 of 12 pass. The three checks of the second review fail: piped and sequenced listings, xargs options and multi-action find, and everyday commands.
  - On this one all 12 pass.
  - They cover:
    - filename-only operations against content reads (ls, find, stat, realpath, rg --files and -l, git ls-files, wc, Grep's name modes, cat, head, rg, Read, Grep content mode, xargs cat);
    - find -exec grep -l and xargs grep -l as tags, and `git -C <dir> show` and find -exec cat as content reads;
    - a glob or directory-wide read of transcripts as an answer source only when its returned content names a same-task trial or thread;
    - listings piped into head, sort, grep, awk or tr, or written beside an unrelated read, as tags even when the listing names a same-task id;
    - against those, reads through `cd`, a find action's `sh -c`, a loop, a command substitution, xargs, `$HOME`, an input redirection or a heredoc program;
    - xargs `-i`, `-l`, `-e`, `--replace` and `--process-slot-var`, and a find command with several actions;
    - the CL7b repeat rejection;
    - a real `timeout --kill-after` SIGKILL (rc 137) holding a Claude cell while a kill before T does not;
    - same-task Codex rollouts (native, clone alias, collected child) against another task's;
    - both Codex times from a real `printf` event stream through the launcher, and from a rollout;
    - and, on smoke-20261006c read-only, all 11 Codex trials carrying both times.
- **Operator step:** `grade.py meter-calibration` ran read-only on smoke-20261006c and wrote nothing in the run root. Its `--write` form was exercised on a copy of the ledger.
- **Re-grade:** a read-only re-grade of smoke-20261006c with this `grade.py`, with its output kept outside the run root, which it left unchanged.
  - Every gate matches the 10:48Z grade. Under round 3's classifier rule G13 had passed. Under the structural G13 it fails again, now for want of receipts: smoke-20261006c was prepared before the wrapper existed.
  - None of its 16 launched trials is valid, for the same reason.
  - The classifier's diagnostic still tags three trials (host-checkout 3, user-harness-file 1) and finds no answer-source read.
- **Not yet run live:**
  - the launcher's final-turn and hold paths;
  - the headroom start rule and rate-limit re-runs;
  - the in-run re-baseline with its cost check and in-lock reconciliation;
  - the pilot's meter recalibration and orphan reconciliation;
  - CL7b's fresh attempts, clone trust comparison and rate-limit marking;
  - the launcher's Codex timing record.

  The first pilot or smoke under these commits will be the first time they execute.
