VERDICT: changes-needed

1. **should-fix — [lane-a/final/audit_selftest_a2.py:31](<worktree>/evidence/artifacts/prompt-audit-20260927/lane-a/final/audit_selftest_a2.py:31): unmasked subagent identifiers.**  
   The privacy scan found **three distinct Claude subagent IDs in six locations across three files**. Additional locations are `final/adjudication/audit_selftest_final.py:36–38` and `final/adjudication/void_patterns_final.py:27`. These are concrete transcript identifiers, unlike the surrounding `<session-id>` placeholders.  
   **Fix:** replace them consistently with symbolic placeholders, extend the publication scanner to detect this identifier format, and update their manifest registrations.

2. **should-fix — [decision record:12](<worktree>/docs/decisions/2026-09-28-top-rule-templates.md:12): provenance conflates different bases.**  
   The record says “The packets were frozen at `8315274f`.” However, `round1/packet.md:1` says **“frozen at 46184751”**, and `adjudication/attempt2/packets/x5.json` also identifies `46184751`. Only the final packets identify `8315274f`. Furthermore, `git merge-base HEAD origin/main` returned **`eb678281fd87c5d33b7dd0833f85727491ece03e`**, rather than the stated branch base `4a8b729a`.  
   **Fix:** distinguish the early and final packet bases, and describe `4a8b729a` as historical if intended. I verified that the four modified pre-existing files are unchanged between these later bases.

3. **should-fix — [lane-a/README.md:14](<worktree>/evidence/artifacts/prompt-audit-20260927/lane-a/README.md:14): S1/X5b application status is unsupported.**  
   “They are applied in the pull request” does not match the available committed state. [PR #444](https://github.com/seathatflowsinourveins/native-agent-stack/pull/444) is open at `46184751`; its returned patch contains neither addition. Both corresponding local and remote branch snapshots also lack them.  
   **Fix:** say they are assigned to that PR and pending application/publication, or cite the actual applying commit. Uncommitted work in another session was unchecked.

4. **should-fix — [docs/harness-defaults.md:131](<worktree>/docs/harness-defaults.md:131): the reported headless-run incident lacks corroborating retained output.**  
   Within the prompt-audit evidence, the incident appears only in `final/adjudication/antipattern-rows.md`, which repeats this row. I found no retained stderr/result supporting the four reviewers, idle termination, or interim response. The documented setting, 600000 default, and meaning of `0` are correct. [Official environment-variable reference](https://code.claude.com/docs/en/env-vars)  
   **Fix:** retain a sanitized incident receipt containing the relevant returned output and run metadata, or explicitly identify those incident details as an uncorroborated coordinator recollection.

5. **nit — [lane-a/README.md:58](<worktree>/evidence/artifacts/prompt-audit-20260927/lane-a/README.md:58): two scan descriptions are inaccurate.**  
   `exposure_scan_dir.py` exits **1** and reports **17 files**, not 16; the README itself matches its `<user>` pattern. Line 66 correctly counts six files naming settings, but incorrectly says those names occur only in a prohibition: `round1/packet.md:40` quotes the repository’s affirmative `.claude/settings.json` policy, propagated into the other five files.  
   **Fix:** correct the count and describe these as repository-instruction quotations. These matches do not establish disclosure of private settings contents.

The two new template lines themselves preserve the tested obligations and installed-client authority, reproduce the operator’s heading and compounding sentence, and remain consistent with the capability-check order. I found no misleading instruction introduced by either line.

The remaining substantive measurements matched:

- Hash **`ce957fd86d5457f0e0a83fa726afa5aa4fbfd94d49471835dc83526ce3aa3b9d`**, **153 words**; baseline **120 words**.
- Portable template: **1,235 words**, ceiling **1,265**, no missing required phrase or repository-relative top-rule path.
- All reported byte/word/token changes reproduced, including o200k counts **1719→1757** and **786→829**.
- Round-one, attempt-two, final-lane, and final-adjudication tallies recomputed consistently from returns, mappings, and audits. Final amendment confidences are **0.94, 0.91, 0.75, 0.78**, with no voiding hit.
- Usage figures and agent types match the retained runner/usage JSON. `controls/controls.json` contains the reported failing/passing exits and **353 tests, 15 skipped**; current collection also contains 353 tests.
- All **121 evidence files plus the decision record** are registered. Only the four intended existing registrations changed; no unrelated manifest section changed.
- All three anti-pattern rows pass the table checks. The first two incidents have supporting void/audit records. Historical self-tests explicitly permit old work-directory hits; their success does not mean zero raw matches.
- Apart from the subagent IDs above, the scan found no concrete private host path, host username, parent-session UUID, credential, or private settings-file contents. Remaining tool names are generic/synthetic references; the email-shaped match is a public noreply allow-list literal.

Historical raw-transcript audits, original host-file modification time, and pre-dispatch chronology remain **unchecked independently** because the underlying private records are withheld. The full historical 353-test execution was not repeated.

Commands run, with shell commands prefixed by `rtk`:

- Git status, merge-base, log, diff, and exact historical blob reads — **0**; worktree clean.
- `python3 -B -c …` using the test module’s `template_segments()` and portable checks — **0**.
- Focused pin/portable unittest invocation — **0**, **3 tests passed**.
- `python3 -B -m unittest tests.test_adoption_docs_consistency.UpstreamVerificationSectionTests` — **0**, **3 tests passed**.
- `python3 -B scripts/validate.py` — **0**: `{"components":69,"hashed_files":7634,"profiles":4,"receipts":161,"status":"passed"}`.
- Native `token_manifest.count_files()` and installed gpt-tokenizer 3.4.0 computations — **0**.
- `python3 -B …/exposure_scan_dir.py …/lane-a` — **1**, the 17 classified matches described above.
- Claude version/help, versioned upstream changelog lookup, and PR #444 metadata/files queries — **0**.
- `python3 -B evidence/artifacts/prompt-audit-20260927/lane-a/verify_lane_a.py` — **0**, with output:

```text
final round X5a: apply the proposed change
final round X5c: adjudicate
X5c adjudication: {'gpt6-AB': 'c', 'gpt6-BA': 'c', 'claude-AB': 'c', 'claude-BA': 'c'} -> apply the amendment (c)
repository: CLAUDE.md:3 and template:3 checked; top-rule block ce957fd8 153 words
all checks passed
```
