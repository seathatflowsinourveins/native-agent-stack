I reviewed the committed branches: PR-1 at `99bcd4f8` and PR-2 at `d3d8095b`, against base `7fa3849c`. I found no high-severity defects. There are two medium findings, six low ones, and several verification gaps.

While I was reviewing, someone started editing PR-1's worktree without committing. The decision record, `packet.md` and both adjudication inputs are modified, and there is a new untracked `prompts/` directory. I judged the commits, not those edits, except where a finding says so.

Paths below are relative to one of these two roots:
- PR-1: `<pr1>`
- PR-2: `<pr2>`

## Findings

**1. Medium: PR-1 records AGENTS.md edits as applied that only PR-2 contains.**
- **Where:** PR-1 `docs/decisions/2026-09-27-prompt-audit-resolution.md:24` and `:27` (F1 and F4 "Applied"), and `docs/harness-defaults.md:95` (the log row for the F1 mistake).
- **Defect:** both AGENTS.md edits exist only in PR-2, and PR-2 must wait for the trading lane.
  - If PR-1 merges first, or PR-2 stalls, main says "Applied" for AGENTS.md text that has not changed.
  - It also logs a mistake in repository text without fixing that text.
- **Source:**
  - `docs/lanes.md:149`: "A `lane:shared` PR needs the other lane's acknowledgement … before merge".
  - `docs/harness-defaults.md:81`: "When the mistake came from repository text, fix that text."
  - The record mentions this only as a residual, at `:220`.
- **Fix:** merge PR-2 first or together with PR-1, or mark F1 and F4 "applied in the lane:shared PR (pending acknowledgement)". This limits merge order, not either PR's content.

**2. Medium: a Claude Code session link is in the committed evidence.**
- **Where:** PR-1 `evidence/artifacts/prompt-audit-20260927/packet.md:288`, `adjudication/input.AB.md:370` and `adjudication/input.BA.md:370`.
- **Defect:** each line carries `Claude-Session: <session URL redacted>`, copied from #385's commit message (`1d8f2f7c`). That is an account-scoped conversation link.
- **Source:** `AGENTS.md:44`: "no raw conversations, tokens, personal paths…".
- **Mitigation:** the same URL is already public in main's history. Main's commit messages carry 20 `Claude-Session` trailer lines, 4 of them in `1d8f2f7c`.
- **Fix:**
  - Commit the redaction that is already in the working tree.
  - Re-register those files, and any `prompts/` files, in `manifests/evidence.json` in the last commit.
  - Extend the new note in the decision record, which names only `packet.md`, to say both adjudication inputs were redacted too.

**3. Low: the F1 row cites a stale line number, and the brief's starting assumption is wrong.**
- **Where:** decision record `:24`, "as that README states (lines 9-10, 219)".
- **Defect:** at `7fa3849c` the "Dispatch by role" bullet is at `examples/claude-native/workflows/README.md:439`. Line 219 now falls in the `m4` counting paragraph.
  - #432 (`bfdc99cb`) inserted 222 lines into that README and also changed its `SHA256SUMS`.
  - So the brief's "identical at 7fa3849c except harness-defaults.md" is false for the README.
- **Impact:** the bullet's text and its blame (`623d34fa`) are unchanged, so the F1 judgment still holds.
- **Fix:** commit the working-tree wording "(lines 9-10 and 219 at `55fc8d17`)", or cite `:439`.

**4. Low: `docs/harness-defaults.md:94` says "after the fifth 2026-09-27 row", which is false where it lands.**
- **Defect:** at `7fa3849c` the removed blank line (old `:93`) followed the sixth 2026-09-27 row, because #438 added row `:87`.
- **Source:** the record lists this only as a residual (`:219`).
- **Fix:** name the preceding row ("Using strict config…") or add "at `55fc8d17`". Either keeps the adjudicated meaning.

**5. Low: the record says no prohibition text was edited, but F4 rewrites one.**
- **Where:** decision record `:17`, "edited no permission or prohibition text (X5, X8)".
- **Defect:** F4 (PR-2 `AGENTS.md:73-74`) changes "future experiments must not call it" to "no experiment may present it".
  - This widens the prohibition from future experiments to all experiments. It is stronger, not weaker.
  - The trading lane should see it named when it acknowledges PR-2.
- **Fix:** "edited no permission text; F4 rewords one prohibition without weakening it".

**6. Low: "once per layer" (decision record `:116`) is wrong.**
- **Source:** `tools/sota-convergence/landscape-sweep/sweep.js:169-175` runs the refute-facts stage only when a layer has proposals.
  - `:217` runs it again for each follow-up layer.
  - For example, `evidence/artifacts/landscape-sweep-20260926/returns.json:17001` records `"round": "followup"`.
- **Fix:** "once per layer and round that has proposals".

**7. Low: the failing f3x7-1 control was not run on the committed test file.**
- **Where:** `controls/f3x7-1-new-test-base-templates.txt`.
- **Defect:** its traceback points to line 282, but the committed `tests/test_landscape_sweep_harness.py` has `self.assertIn(phrase, facts)` at `:283`.
  - The n2-3 control (`:842`) and the f3x7-3 control (`:247`, run on the base test file) do match their files.
  - So the retained failing run is of an uncommitted test revision.
  - `docs/harness-defaults.md:81` requires seeing a named check fail before listing it.
  - The passing side is covered by `pr1-modules-after.txt`.
- **Fix:** please re-run the committed test against `7fa3849c`'s `templates.json`, then replace and re-register the control.

**8. Low: a note in `usage.json` points at a file that does not exist.**
- **Where:** `usage.json:70`.
- **Defect:** the note begins "Write claude-usage.json: …", which is leftover instruction text. There is no such file in the evidence directory.
- **Fix:** drop the prefix and re-register the file.

## Verification gaps (not defects)
- **Skip reasons:** the reasons stated at decision record `:101-104` are not in the retained controls, which were run without `-v`. They are plausible from these skip decorators:
  - `tests/test_landscape_sweep_harness.py:782`, `:1410`, `:1415`;
  - `tests/test_adoption_docs_consistency.py:400`;
  - `tests/test_install_claude_profile.py:524`, `:535`, `:599`.
- **Control provenance:** the controls lack command lines, revision and exit codes, which `docs/acceptance-evidence-policy.md:57-59` asks for. n2-3 does not say which base page it ran on.
- **Prompts:** at `99bcd4f8` the GPT-6 prompts as sent are not retained.
  - The runner prompt hashes (`b3dab676…`, `c51ccd65…`, `8c0047d1…`) do not match `input.AB.md` (`a521ee94…`) or `input.BA.md` (`529e5b64…`).
  - The schemas do match (`2990223f…`, `3748fdf6…`), and so does the probe (`PROBE_PROMPT` plus a newline gives `2a4fe3fb…`).
  - I did not review the new `prompts/` directory.
- **Tests not run:** no CI or gitleaks output was supplied. On PR-1, `test_ecosystem_manifest`, `test_token_e2e_preregistration` and `test_install_claude_profile` were not run. By inspection, none of them parses the changed content.
- **PR metadata:** I could not see PR labels, the trading-lane acknowledgement or the PR bodies.
- **Supplied diff:** `pr2.diff` omits PR-2's `manifests/evidence.json` hunk, which re-registers AGENTS.md as `0178874…`, 12025 bytes. It is present in PR-2's single commit.
- **Agent-lab identity:** AGENTS.md:36's "byte-identical to agent-lab" rests on README:9-11. I did not check it against agent-lab itself.

## Areas with no finding
- **Exact application:** F1, F3/X7 (with the test comment), all three N1 replacements, the four N3 rows in place of the blank line, F4 and N2 are byte-exact. Each old string matched once, and the other template keys are unchanged.
- **Tallies:** `decisions.json` matches the round-1 and adjudication returns through `mapping.json` for all six units, including the 2-2 split on X9.
- **Hashes:** `packet.md` is `0e6b6430…27877` as recorded, the recomputed prompt hash equals `PROMPTS_SHA256_CURRENT`, and every changed file's registration matches.
- **Usage and wall times:** all match `usage.json`, including the sums across the three Explore agents.
- **Token counts:** match the `token-counts-*.txt` controls.
- **Sources:** S2, S5, S6, S7, S9, S10, S11 and T1-T3 support the record's wording. There are 14 sources and 7 not-found entries, as stated.
- **Retained sweep returns:** `returns.json` lines 2218, 17006 and 15198 support the opencode, alpaca CLI and purged-cross-validation claims. #385 changed only `common` and `fit`, and "null when unknowable" was already in the discover template.
- **Other files and hash chains:**
  - Nothing references the old file hashes.
  - The ledger note at `:2846`, `lanes.json:6548` and `manifest-20260926.json:19387` are recorded residuals.
  - No test pins the old AGENTS.md text.
- **Test discrimination:**
  - The new split-table check fails on the unfixed page (n2-3) and on the mutant (n2-2), and passes after the fix (n2-4).
  - The facts test fails on the base templates.
  - The hash pin fails when the templates change (f3x7-3).
- **Hot-file protocol and lanes:**
  - PR-1's last commit touches only `manifests/evidence.json`.
  - PR-2 is a single commit carrying both hot files.
  - The labels as briefed (`lane:foundation` for PR-1, `lane:shared` for PR-2) fit `docs/lanes.md:24-26` and `:145-150`.
- **Anti-pattern log rule (`docs/harness-defaults.md:81`):** rows `:93` and `:94` name checks that were seen failing. Rows `:95` and `:96` say "This log".
- **Other hygiene:** there are no host paths, personal e-mail addresses, UUIDs or tokens, and the controls use `<pr1>` and `<tmpdir>` placeholders.
  - The only e-mail is the public `noreply@anthropic.com` trailer.
  - The "Managed config" lines come from a test fixture (`tests/test_install_claude_profile.py:872`).

I wrote one file by mistake, `<work>/review/.pr1-actual.tmp`. It is a copy of the branch's `git diff`, identical to `pr1.diff`, which I used to confirm that `pr1.diff` matches the branch. Please delete it; I wrote nothing else.

I used context-mode `ctx_execute` for the git, grep and JSON work so the raw diffs and JSON stayed out of context, and Read for bounded windows of known files.
