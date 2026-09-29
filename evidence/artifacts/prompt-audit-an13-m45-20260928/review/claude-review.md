VERDICT: changes-needed

All paths are relative to the worktree `<worktree>/`. `PKG` stands for `evidence/artifacts/prompt-audit-an13-m45-20260928`, and `LA` stands for `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication`, which is on this head.

1. **should-fix: the anti-pattern row leaves out that the log's own template already covered both voids, and its rule is too narrow.** `docs/harness-defaults.md:131`
   - **Evidence:**
     - The row just below it names the template: "this log (the lane-A self-tests under `evidence/artifacts/prompt-audit-20260927/lane-a/` are the template)" (`:133`).
     - That template on this head already handles this exact case:
       - `LA/audit_final.py:89`: `if kind != "prompt_snapshot":  # the judge's own agent definition`.
       - `LA/void_patterns_final.py:12-16`: family-attribution phrases apply "only to context a Claude judge did not fetch … because the repository's own prose about the two families is subject matter in files a judge reads", and "prompt_snapshot is the judge's own agent definition" is exempt.
       - `LA/audit_selftest_final.py` requires two payloads to stay clean (`set()`): the tool result "docs: the GPT-6 lane and the Claude lane agreed on F1 (round 1)." (`:131`) and a `prompt_snapshot` holding "…such as \"the Codex lane\"…" (`:136-138`).
       - `LA/root_scan_final.py:1-8` runs before dispatch: it counts "root files whose text matches MAPPING or PHRASES" and "Exits 1 on any hit".
     - The round did not use that template. `PKG/README.md:88` says `audit_m45.py` adapts X9 round 3's `audit_r3.py`. Against `audit_r3.py` at branch commit `45edc9af`, the only differences are the docstring, the module name, the job path and the output name. It has no `prompt_snapshot` exemption.
     - Applying the M45 `MAPPING` regex in memory, it fires on both template payloads: "GPT-6 lane" and "Codex lane".
     - A supporting count, derived in memory for the coordinator to reproduce: `MAPPING` matches the text of 242 of the 8,223 tracked files at `9f8db582`, and the paths of 8. The row's "an exported file name" misses the text matches.
   - **Fix:**
     - In "What happened", say the round adapted X9 round 3's audit instead of the lane-A template the log names, and that the template's exemption and its cases 131 and 136-138 already cover both voids.
     - Rewrite the rule column: start from the named template; keep family-attribution phrases to injected context with the judge's definition exempt; add each new pattern to the self-test; run the root scan over exported file text and names before any judge starts.
     - Give the decision record's `:144-146` the same wording.

2. **should-fix: "Where enforced" cites a control whose pass condition cannot fail on this mistake.** `docs/harness-defaults.md:131`, checked against `:81`
   - **Evidence:**
     - The log rule at `:81` says: "name a check there only after seeing it fail on that mistake or a reproduction of it".
     - `PKG/scripts/audit_control_m45.py` passes when the clean copies reproduce the published audit: `ok_clean = clean == published` (`:69`), `ok_planted = all(...)` (`:70`) and `sys.exit(0 if ok_clean and ok_planted and …)` (`:82`).
     - In `PKG/adjudication/audit-control-m45.json`, both flags are `true` (`:112`, `:205`) while both Claude clean copies are `"void": true` (`:61-110`).
     - The script has no "real runs stay clean" criterion, so it is a post-hoc reproduction of the voids. It cannot serve as the pre-dispatch control the row prescribes.
   - **Fix:**
     - Keep "this log", and describe `audit-control-m45.json` as the reproduction of the voids, not "the control".
     - Name `LA/audit_selftest_final.py` and `LA/root_scan_final.py` there only after the coordinator runs cases 131 and 136-138 against `void_patterns_m45.py` and sees them fail. That reproduction is not yet run.

3. **should-fix: the governing rule is cited to a file that does not contain it.** `docs/decisions/2026-09-28-an13-m4-m5.md:3-8`
   - **Evidence:**
     - The record says "the convergence rule in [`docs/convergence-architecture.md`]". That 260-line file has no lane, family, adjudication or "four judgments" text.
     - The rule is at `docs/decisions/2026-09-27-prompt-audit-resolution.md:54-60`: "Both lanes agree: apply the proposal. Both reject: keep the text." … "A unit is applied only when all four adjudications choose the same return. Otherwise it stays unchanged, and both positions are recorded, because a split stays pending".
     - The coordinator's brief makes the same citation.
   - **Fix:** cite `2026-09-27-prompt-audit-resolution.md:54-60`.

4. **should-fix: `receipt.json:88` does not credit the installer, and the same premise went to all four judges.** Decision record `:69-70`; `PKG/adjudication/packets/m5.{AB,BA}.json:4`
   - **Evidence:**
     - `receipt.json:88`, the file's only project-readiness mention, reads "validated against installed project-readiness contract validator; enclosing worktree actions not modified". It names a validator, not the installer.
     - GPT-6 B/A says so itself: "the installer description comes from AGENTS.md" (`PKG/adjudication/gpt6.BA.json:6`).
     - The sent packet states "while lines 15-16 and …receipt.json:88 attribute it to project-readiness" (built at `make_m5_adjudication.py:44-47`).
     - Only the Claude lane cited the receipt, and only for the validator's name (`round1/returns/claude-m45.json:96`).
     - Both Claude judges then relied on it (`claude.AB.json:8`, `claude.BA.json:8`).
   - **Fix:**
     - Change `:70` to cite `AGENTS.md:15-16` for the installer attribution.
     - Add a limitation: the sent packet stated this premise as a round-1 fact, which favours the text that keeps the installer sentence. A new round's packet must drop it. The outcome is unaffected.

5. **should-fix: the judges were not given the returns' reasons or sources.** Decision record `:115-116`
   - **Evidence:**
     - The record says "The inputs hold two returns, Return A and Return B, with only their texts, reasons and sources".
     - The inputs' keys are `unit, question, current_text, return_A, return_B, choices, rules`, and `return_A` and `return_B` are bare texts (`PKG/adjudication/adjudication-inputs/m5.AB.json:5-6`). The builder sets `"return_A": texts[mapping[order]["A"]]` (`make_m5_adjudication.py:99-107`).
     - The packets carry no per-return reasons or sources either.
   - **Fix:** "with only their texts". The packet adds a one-sentence round-1 summary, S1, S10 and the file list.

6. **should-fix: "Both lanes checked" the hash is contradicted by the Claude lane's own return.** Decision record `:31-32`
   - **Evidence:**
     - The record says: "Both lanes checked that the installed copy and the upstream file at the pin have the manifest's hash".
     - The Claude lane's return says: "I did not check the installed host copy's hash or symlink" (`PKG/round1/returns/claude-m45.json:7`).
     - Only the GPT-6 lane says "I verified that the installed skill and U1 match the manifest's hash" (`gpt6-m45.json:7`). The check itself is recorded in U1's note in `round1/sources.json`.
   - **Fix:** attribute the check to the GPT-6 lane and the packet's U1, and say the Claude lane relied on the packet.

7. **nit: the cited file does not carry the hash time.** Decision record `:122-123`; `PKG/README.md:28`
   - **Evidence:** the record says "hashed at 14:21:23Z (`scripts/frozen-sha256.txt`)". That file holds three hash lines and no time. No package file contains 14:21:23Z; the retained times are 14:21:32Z in `isolation.log` and 14:21:39Z in the runner records. No Claude judge start time is retained.
   - **Fix:** retain the timestamped hashing output, or say the time is unretained. Either way, keep only what the files show: the patterns' hash equals `audit-m45.json:2`.

8. **nit: the stated reason for withholding the hit windows does not match the recorded hits.** `PKG/README.md:58-59`
   - **Evidence:** the README says the windows "quote the Claude judges' injected session context". The recorded hit scopes are `attachment prompt_snapshot`, `tool_result` and `tool result (structured)` (`audit-m45.json:24-50`); none is `session_context`.
   - **Fix:** state the real reason, or publish the four cleaned windows. They are the only evidence for "all are false positives".

9. **nit: precision.**
   - (a) `:33` "The packet's first source": U1 is the 11th of 13 entries in `sources.json` (S1-S10 come first). Say "the first U source".
   - (b) `:38` "Hunks D1 and D2 replace those kept parts with shorter text": D2 (`round1/packet.md:88-114`, `@@ -48,27 +22,3 @@`) deletes Red Flags and the rationalization table and adds nothing. Say "D1 replaces and D2 deletes".
   - (c) `:63-64`: the trigger-list point is the Claude lane's alone (`claude-m45.json:7`). GPT-6 said only "The over-verification concern is credible".
   - (d) `:129-130` "no model names": the packets contain "Claude responds well…" and an openai URL. The builder's regex (`make_m5_adjudication.py:142`) looks only for model ids and "codex lane"/"claude lane". Say "none of its leak words".
   - (e) `:133` "four hits from two patterns": `audit-m45.json` labels all four `"pattern": "MAPPING"`. The two are unnamed alternatives of one regex (`void_patterns_m45.py:14-16`).
   - (f) `:90-97`: both valid GPT-6 judgments chose position B (`gpt6.AB.json:5`, `gpt6.BA.json:5`), so the GPT-6 pair depends on order. Add one sentence.
   - (g) `:113`, `:201` and `PKG/README.md:85` "no web access": the role grants context-mode's `ctx_execute`, `ctx_execute_file` and `ctx_batch_execute` (`.claude/agents/evidence-reviewer.md:4`), and the sent brief says "You have no shell or web access" (`round1/prompts/claude-brief-m45.txt:4`). Say "no web tool; told not to use the web".

**Checked on this head, no finding:**
- **Outcomes:** M4 "no edit" and M5 "split, no edit" are the rule's correct application.
- **Voids:** "the outcome does not depend on the voids" holds; with valid Claude judgments the count would be 3 of 4.
- **Citations:** all of them say what the record says, except `receipt.json:88` (finding 4): `skills_status.py:12, 262, 431-511`, `install_skills.py:127`, `test-envelope.mjs:505`, `test-contract-mutations.mjs:70-73`, `bootstrap.md:346-347`, the three decision and README ranges, `AGENTS.md:15-18` and `isolated-builder.md:9`. All three builder copies carry the preload.
- **Figures:** the M5 texts, the adjudicator quotes, the round-1 confidences, the usage table, the times 14:02-14:24Z, and the versions and models all match the retained files.
- **Inputs:** they are equal after swapping A and B, and the packets are identical.
- **Privacy:** no host paths, user name, UUIDs, emails, secret-like strings, agent ids or client-configuration quotes in the 48 files. Hits are only pattern text in the two expected scripts and lines of `harness-defaults.md` this change does not touch.
- **Manifest:** all 48 files are registered with matching sha256 and byte counts.

**Could not check:**
- **Unpublished runs:** the transcripts, `events.jsonl` files and hit windows are not in the package. So I could not check the hit locations, "none of the hits says which lane", the GPT-6 audit's clean result, "neither saw the other's return", the judges reading only the export, or whether the Claude lane used `ctx_execute` for network access.
- **Timing:** the 14:21:23Z hash time and the Claude judges' start times.
- **Sent prompts:** their bytes as sent. I only confirmed that `make_m5_adjudication.py:113-130` inserts 1 path per judge prompt and 3 per `claude-task` prompt, which matches your count.
- **Probe:** whether the GPT-6 probe actually searched the web.
- **Tests:** I ran no tests, validators or reproductions, and relied on your results. I don't know which test was skipped in `test_adoption_docs_consistency`.
- **To run:** the lane-A cases against `void_patterns_m45.py` (finding 2), and the 242-of-8,223 count, which I derived in memory from `git show 9f8db582:<file>`.
- **Token tools:** context-mode `ctx_execute` for diffs, greps, the manifest check and in-memory regex checks, so large outputs stayed out of context; Read and Grep for known files.
