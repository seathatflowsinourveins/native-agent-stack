VERDICT: changes-needed

1. **should-fix — [2026-09-28-an13-m4-m5.md:31](<worktree>/docs/decisions/2026-09-28-an13-m4-m5.md:31): incorrectly attributes independent verification to both lanes.**  
   The record says both checked the installed and upstream hashes. `round1/returns/claude-m45.json:7` explicitly says: “I did not check the installed host copy's hash or symlink.” GPT-6’s return reports checking it.  
   **Fix:** attribute the installed-hash check to GPT-6; state that Claude relied on the packet’s U1 evidence.

2. **should-fix — [2026-09-28-an13-m4-m5.md:4](<worktree>/docs/decisions/2026-09-28-an13-m4-m5.md:4): the cited architecture document does not contain this voting rule.**  
   I read the complete document. Searching it for `both lanes|both reject|blind|adjudicat|all four` returned no matches, exit 1. The unanimity rule does appear in the frozen adjudication inputs.  
   **Fix:** cite the actual retained rule source and distinguish the task’s voting procedure from the architecture’s general convergence guidance.

3. **should-fix — [2026-09-28-an13-m4-m5.md:122](<worktree>/docs/decisions/2026-09-28-an13-m4-m5.md:122): the claimed freeze time lacks retained support.**  
   `scripts/frozen-sha256.txt` contains three hashes and filenames, without timestamps. `14:21:23Z` occurs only in the decision record. The runner records support the judges’ `14:21:39Z` start; `isolation.log` records isolation operations at `14:21:32Z`, but no hash freeze. Hash verification proves current byte identity, not when the hashes were recorded. README:28 similarly asserts pre-dispatch timing.  
   **Fix:** retain an original timestamped receipt binding those hashes to the freeze event, or qualify the timing as unverified.

4. **should-fix — [2026-09-28-an13-m4-m5.md:115](<worktree>/docs/decisions/2026-09-28-an13-m4-m5.md:115): inaccurately describes what the judges received.**  
   `adjudication-inputs/m5.{AB,BA}.json` supplies `return_A` and `return_B` as replacement-text strings. It does not include each lane’s reasons or source list. The accompanying packet supplies a shared summary and common sources. `make_m5_adjudication.py:26–28,103–104` confirms that extraction.  
   **Fix:** describe text-only candidates plus the shared evidence packet; preserve the frozen inputs.

5. **nit — [2026-09-28-an13-m4-m5.md:70](<worktree>/docs/decisions/2026-09-28-an13-m4-m5.md:70): overstates the receipt citation.**  
   `receipt.json:88` says “validated against installed project-readiness contract validator; enclosing worktree actions not modified.” It does not describe an installer or its outputs. That attribution comes from `AGENTS.md:15–16`, as GPT-6’s B/A judgment correctly distinguishes.  
   **Fix:** cite AGENTS.md for installer ownership and the receipt for validation and unchanged actions.

6. **nit — [2026-09-28-an13-m4-m5.md:128](<worktree>/docs/decisions/2026-09-28-an13-m4-m5.md:128): the stated checksum command fails from the package directory.**  
   `sha256sum -c round1/packet.sha256` returned exit 1: `packet.md: FAILED open or read`. The checksum file names `packet.md` relative to the working directory. README:66 already gives the working invocation.  
   **Fix:** use `(cd round1 && sha256sum -c packet.sha256)`.

The no-edit outcomes themselves are supported. Round-one verdicts, confidences and both recorded M5 texts match the returns. Independent recomputation gives:

| Judgment | Choice | Mapped text | Audit |
|---|---|---|---|
| GPT-6 A/B | B | GPT-6 | Valid |
| GPT-6 B/A | B | Claude | Valid |
| Claude A/B | A | Claude | Void |
| Claude B/A | B | Claude | Void |

Thus M5 cannot reach four matching valid votes. Ignoring the voids produces 3–1, still no edit. M4’s rejection follows the pinned-source constraint and the recorded comparison deferral; it does not establish behavioral superiority.

All other requested HEAD citations support their stated claims: the canonical path and hash-failure logic; locked-skill reinstall classification; exact preload tests and mutations; bootstrap/preload declarations; scheduled comparison and deferral; historical role-body seal; and the current M5 wording. `.claude/agents/blind-adjudicator.md:25` contains the matched “the Codex lane” example.

Live upstream checks confirmed identical pin/main blobs and SHA-256 `2befe7fc55bcadaa3d97dd9e8efeb633d2561c0ebe74c5a8b17c4d9e7e4520b3`. The latest file change is the quoted July 24 commit. The Opus 5 section supports the over-verification quotation. [Pinned skill](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/verification-before-completion/SKILL.md), [main](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md), [commit](https://github.com/obra/superpowers/commit/3be5aad3dd2400ef23b15680969f4bcd3b6d7b8b), [Opus guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5#task-scope-and-over-verification).

The remaining checks found:

- Usage tables match `usage.json`; all four GPT-6 records corroborate their listed counters, versions and times.
- All five non-prompt sent hashes match. Restoring only `<adj>` in memory reproduces all four original prompt hashes exactly.
- The audit/control records agree. Executing the frozen audit functions on synthetic inputs reproduces the published hit signatures and planted-access results. The record correctly limits what already-void Claude controls establish.
- The anti-pattern row complies with the log’s format and explicitly names “this log” as enforcement.
- Registration covers exactly 48 files: 47 additions and the harness-document update. No unrelated manifest entry changed.
- Searches found no unexpected private-content matches; the host-path hits were the expected sanitization patterns.

**Unchecked:** original report quotations and #444 history; historical transcript replay, actual injected hit windows, independent Claude usage/type derivation, historical installed-copy verification, and freeze timing. Full JSON Schema validation was unavailable because `jsonschema` was not installed.

Commands/checks run, with exit codes:

- `rtk git status --short` — **0**, clean before and after.
- `rtk proxy git diff origin/main...HEAD` and manifest-only diff — **0**.
- `rtk proxy python3 -B -m unittest tests.test_adoption_docs_consistency` — **0**, 37 tests, one skipped.
- `rtk proxy python3 -B scripts/validate.py` — **0**, 7,710 hashed files; status `passed`.
- Package-directory `sha256sum -c round1/packet.sha256` — **1**, working-directory failure above.
- Round-one-directory `sha256sum -c packet.sha256` — **0**, `packet.md: OK`.
- Scripts-directory `sha256sum -c frozen-sha256.txt` — **0**, all three `OK`.
- Three `rtk proxy gh api` upstream queries — **0**.
- Architecture-rule `rg` search — **1**, no matches.
- In-memory Python tally, hash, registration, privacy and behavioral checks — **0**.