# Organic-invocation E2E v1.1: the command center's decisions (2026-10-06)

- **Source:** command-center item `task-ns2604-coop-20261006T105529Z`, section "Organic E2E v1.1: the CC's decisions before the pilot", sent 2026-10-06 at 10:55Z. The decisions below keep that item's numbers.
- **Confirmations:** command-center item `task-ns2604-coop-20261006T114319Z`, sent at 11:43Z, settles the five points this file had marked for confirmation. Each is recorded below as "Confirmed (CC 11:43Z)", with its point number.
- **Applies to:** PROTOCOL-v1.1.md (organic-e2e-v1.1-20261005), which stays verbatim, and PILOT-SPEC-v1.1.md. Where they differ from this file, this file governs from 2026-10-06 10:55Z.
- **Harness:** each decision's code is in `harness/`, in the commit that adds this file.
  - `CC_V11_DECISIONS` in `harness/common.py` names the item.
  - `prepare.py` writes this file's sha256 into run.json as `amendment_file_sha256`.
- **Status:** no pilot or smoke has run under these changes. The checks under Verification are synthetic or offline.

## Confirmed (CC 11:43Z)

Item `task-ns2604-coop-20261006T114319Z` confirms the five points, with three additions the harness now implements:

1. **The no-result hold applies to every Claude cell,** not only claude-env. One rule for all Claude cells keeps the arms symmetric. The launcher's `holds_cell()` depends on the client and the censoring reason only: CLI or SDK, native or env, stage 2, 3 or 4.
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
   - The operator step is `grade.py meter-calibration --run-root <root> [--write]`.
   - The value each trial started with is recorded in its ledger rows (`expected_usage`, `meter_expected_usage`) and in the grade (`meter_expected_usage`, with the calibration and the current p90).
   - On smoke-20261006c's three organic Claude trials, the p90 would be 0.06 (five-hour) and 0.01 (seven-day).

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
- **`launcher.py` records per Claude trial:**
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

- **Static checks:** every harness module parses (`ast.parse`) and imports. A stdlib `symtable` check found no undefined global names.
- **Synthetic checks:** 91 checks of the decision helpers, all passing. The script is kept outside the repository.
  - They cover headroom and resets, rate-limit hits, completion reasons, the hold flag, exposure, answer sources, effort-only fields, the re-baseline bound, each refused key class and the CL7b re-run rule.
  - 35 of them cover the 11:43Z confirmations:
    - the hold rule on every Claude cell of the run of record;
    - the vendor-skill stratum and its counting;
    - each answer-source reason, and that sources and oracle inputs stay tags;
    - the re-baseline cost bound and its fallback;
    - the p90 calibration, the pilot hook and per-window headroom.
  - Eight of the checks run on smoke-20261006c's own streams and rollout, and one reads its run.json.
- **Operator step:** `grade.py meter-calibration` ran read-only on smoke-20261006c and wrote nothing in the run root. Its `--write` form was exercised on a copy of the ledger.
- **Re-grade:** a read-only re-grade of smoke-20261006c with this `grade.py`, with its output kept outside the run root. Every gate matches the 10:48Z grade except G13, which now passes, as described under decision 3.
- **Not yet run live:** the launcher's final-turn and hold paths, the headroom start rule, rate-limit re-runs, the in-run re-baseline with its cost check, and the pilot's meter recalibration. The first pilot or smoke under these commits will be the first time they execute.
