VERDICT: changes-needed

Paths used below:
- W = `<worktree>`
- REC = `W/docs/decisions/2026-09-28-top-rule-templates.md`
- LA = `W/evidence/artifacts/prompt-audit-20260927/lane-a`

1. **should-fix, REC:12.** The record says: "based on `origin/main@4a8b729a`. The packets were frozen at `8315274f`".
   - **Evidence:** after the rebase, `git merge-base origin/main HEAD` is `eb678281`. `LA/round1/packet.md:1` says "(frozen at 46184751)", which is PR #444's head, and attempt 2 used that base too.
   - **Fix:** name `eb678281` as the base. Say round 1 and attempts 1–2 were frozen at 46184751 and the final round at 8315274f. Add that both templates and both test files are identical across 46184751, 8315274f and eb678281 (empty `git diff`); only `docs/harness-defaults.md` differs, by #444's three rows.

2. **should-fix, REC:42.** The record says: "The previous line had called only "upstream" a source of truth."
   - **Evidence:** the removed lines say "Upstream and the installed client are the source of truth" (`W/examples/claude-native/CLAUDE.md:3`) and "upstream and the installed client are the source of truth" (`W/adoption/templates/codex.AGENTS.template.md:3`). REC:43 itself says "as the base lines did".
   - **Fix:** delete the sentence, or attribute it to the packet's proposed X5c text.

3. **should-fix, REC:111.** The record says: "Earlier rounds' usage is in their directories."
   - **Evidence:** `LA/adjudication/attempt1/void.json` says the two GPT-6 jobs "are left to finish and are kept as records", but no usage for them exists anywhere in LA. Attempt 1's Claude usage is in `LA/round1/claude-usage.json` (`adj1-*`), not in `attempt1/`. AGENTS.md says to keep failed attempts with their usage and to leave unknown usage unknown.
   - **Fix:** publish both runner usage blocks without the returns, or state "not retained".

4. **should-fix, REC:71 against REC:78–79.** REC:71 says "Each check was seen failing before it passed", but two rows below it say "not applicable".
   - **Evidence:** `LA/verify_lane_a.py` has no recorded failing run. `W/docs/acceptance-evidence-policy.md:42-45` counts a new check only after the same check has failed with its condition absent.
   - **Fix:** run it where it must fail (for example with 8315274f's `CLAUDE.md:3`), record the exit 1, and reword REC:71.

5. **should-fix, `LA/README.md:32`.** `controls/` is labelled "local integration run".
   - **Evidence:** it holds unittest pin and phrase checks and `scripts/validate.py` registration checks (`LA/controls/controls.json`). Policy line 33 puts these in its "Structural validation" class, whose limit is "Artifact consistency; not execution or adoption". REC:127 already calls them "text, pin and registration checks".
   - **Fix:** relabel `controls/` as Structural validation.

6. **nit, evidence notes misdescribe their own files.**
   - `README.md:66` says the settings-file mentions are "only in the packet's quoted rule not to read one". All six files quote `AGENTS.md:35` instead: "This repository commits `.claude/settings.json` with Ultracode on". The six are `round1/packet.md:40`, `round1/gpt6-prompt.txt:46`, `round1/claude-brief.txt:46`, `attempt2/packets/x5.json:4`, and `judge-AB.txt:195` / `judge-BA.txt:195`.
   - `README.md:58` does not say that a scan reporting 16 files exits 1 by design (`LA/exposure_scan_dir.py:35`: `sys.exit(1 if bad else 0)`).
   - Both adjudication `sent-sha256.json` notes say the published "inputs, packet and prompts replace host paths". The inputs' and packets' hashes equal the as-sent hashes; only the prompts differ.
   - **Fix:** correct all three descriptions.

7. **nit, precision in REC.**
   - REC:7 says "a blind adjudication settled any split". X5a's split was settled by the final lane round (REC:32).
   - REC:101 says the probes' output was "about 1,600". The records show 1,639 (`LA/final/gpt6-probe.runner.json`) and 1,500 (`LA/final/adjudication/probe.runner.json`).
   - REC:131 says "a dry run, then `--apply`". Running `--apply` without the dry run's `--expect-*` hashes exits 2 (`W/tests/test_codex_worker_lane.py:501-505`). Say "the `--apply` command the dry run prints".

8. **nit, `W/docs/harness-defaults.md:130` (anti-pattern row 2).**
   - The row says "the `cat ~/.codex/RTK.md` that the Codex runtime runs at startup". `LA/adjudication/attempt2/audit.json:11` records a model `command_execution`, `/bin/bash -lc 'rtk cat ~/.codex/RTK.md'`, which the user instructions prompted. It is not a read by the runtime itself.
   - The row's rule says real runs "must stay clean". The template it cites, `LA/final/adjudication/audit-selftest-final.json`, allows `ACCESS:hold_and_work_dirs` hits on real runs (63 on `final-claude-lane`).
   - **Fix:** say "clean apart from their own work directories".

**Confirmed against the files:**
- Every verdict, confidence, tally and mapping.
- All usage figures in REC:98–109, and the advisor-call counts.
- The `agent_type` values: evidence-reviewer, blind-lane-reviewer and blind-adjudicator.
- Bytes, `wc -w` words and o200k counts; the 120→153 word count and the pin; the ceilings of 1,265 words and 8,192 bytes.
- The exit codes in `controls.json`.
- 121 files on disk, matching 121 manifest entries.
- The frozen hashes of the void patterns, audit, tally, mapping, outcome actions and inputs.

Both new lines pass `PortableTopRuleTests` and `TemplateTests` and agree with `harness-defaults.md:58` and `:62`. Rows 129 and 131 follow the log's column rules. Neither the record nor the README makes a behaviour claim or presents a local check as upstream acceptance.

**Private content:** a regex scan of the 121 files and REC found none of the following:
- host or tmp paths;
- the user or git name;
- email addresses (the only one is `noreply@anthropic.com`, used as a pattern exclusion);
- UUIDs or session-id fragments;
- token-shaped strings;
- Windows or WSL identifiers;
- settings-file content.

`context-mode` and `ai-memory` are components the repository already documents, and `native-agent-stack-a9` already appears in a merged receipt.

**Could not check:**
- **Full test suite on the rebased head b4472998.** In particular, #455's `tests.test_gitleaks_config` (its HEAD-ancestry scan at `:813`) and `tests.test_workflow_hardening` have not run on this head. Please run them.
- **The exposure scan's "16 files"**, because I did not rerun it.
- **Redacted files and freeze timing.** Where files were redacted, the published copies' hashes cannot be compared with the frozen or sent hashes. Nothing shows that the `frozen-*.sha256` lists were written before dispatch.
- **The failing self-test that caught the plugin-skill read.** Only the passing run after the fix is retained.
- **Row 130's statement that the probe and lane runs had shown the RTK read.** It rests only on the docstring at `LA/final/void_patterns_a2.py:4-6`.
- **Row 131.** The `/doctor` run it describes has no retained evidence, and I did not fetch the env-vars page.
- **PR #444's current head.** The locally known head, 46184751, does not change `AGENTS.md:3`. Three things depend on the real head:
  - whether S1 and X5b "are applied", as `README.md:14` says;
  - whether #444 updates `harness-defaults.md:7`, which still says "research first, and never self-write…" and so no longer matches the portable template's line 3;
  - a likely merge conflict, because #444 appends three rows at the same end of the anti-pattern table.
