# Judgment packet: two findings left from a headless prompt-audit run (frozen at 9f8db582)

You are an independent reviewer. A headless prompt-audit run over this repository (its client's own audit command)
reported the two findings below with proposed rewrites. Nobody else has judged them yet. Judge each on its merits:
verify the evidence against the original source (the repository is checked out read-only at the base path in your
task), check the shared primary sources, research further where a claim depends on current official documentation or
on the upstream project, and decide whether the proposed rewrite is right.

Rules:
- Verify, do not trust: excerpts below are copies; the files at the base path and the upstream URLs are the original
  source.
- A proposal that another file, test, pin or fixture would contradict or break is wrong; say which.
- Keep the operator's standing rules: the current upstream state of a maintained source is the source of truth, and a
  vendored upstream file is changed by re-pinning to an upstream revision, not by a local edit; licenses and
  incumbency are never selection criteria.
- Judge wording on whether the target models will follow it as intended, not on style.
- A change whose effect on behavior is unmeasured may still be right, but say what would show it wrong.
- Every `sources` entry names a file:line or URL and quotes the text that supports your verdict.

Verdicts per item: `agree`, `amend` or `reject`, with the meaning stated in each item. `resolution_text` holds the
exact edit for `amend` and is empty otherwise. `confidence` is 0..1.

---

## M4: pressure wording and broad triggers in a vendored skill that the builder agent preloads

Location: the user-level skill `verification-before-completion` (vendored from `obra/superpowers`, installed for all
projects and shared with the second coding client), and its preload in `.claude/agents/isolated-builder.md:9`.

Verdict meaning: agree = apply hunks D1-D3 below to the vendored user-level skill exactly as written; amend = apply the
exact edit you give in resolution_text instead (name every file and give the exact text; it may change project files,
for example the builder's preload list or the skill's adoption status, instead of the vendored skill); reject = change
no file for this item in this unit.

### The finding, as the audit reported it
**M4a · `~/.claude/skills/verification-before-completion/SKILL.md:10-36, 50-73` (all projects, vendored) · medium · rewrite (hunks D1, D2)**
- **Text:** "Violating the letter of this rule is violating the spirit of this rule." · "NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE" · "Skip any step = lying, not verifying" · "Red Flags - STOP … ("Great!", "Perfect!", "Done!", etc.) … Tired and wanting work over" · "| "I'm tired" | Exhaustion ≠ excuse |" · "| "Just this once" | No exceptions |"
- **Pattern:** pressure wording and claims about the model's character; lists of banned phrases with no stated reason.
- **Why it's a problem:** current models over-apply shouted, absolute rules, and an anxious prompt makes the model cautious and hedging. The phrase lists target an older model's habits, and no matching failure is known on Opus 5.5. The Opus 5 guidance also says verification instructions like these cause over-verification; the Opus 5.5 guidance says to re-test that.
- **Keep:** the Common Failures table (lines 38–48) and Key Patterns; they define what counts as evidence.

**M4b · the same file, lines 106–120 · medium · rewrite (hunk D3)**
- **Text:** "**ALWAYS before:** - ANY variation of success/completion claims - ANY expression of satisfaction - ANY positive statement about work state … - Moving to next task - Delegating to agents … - ANY communication suggesting completion/correctness"
- **Why it's a problem:** read literally, the check runs before every status line, task switch and delegation. It only needs to cover success claims and commit, push or PR steps.
- **Side effects of editing this file (M4a and M4b):**
  1. It affects all projects.
  2. The path is a symlink into `~/.agents/skills`, which Codex also loads (`codex_enabled: true` in `adoption/skills/manifest.json`).
  3. It breaks the pinned `skill_md_sha256` (`2befe7fc…`, `obra/superpowers@8ca22db`, status `trial`), and a skills update would undo it.
- **Alternative inside the project (no diff proposed):** end the trial, or stop preloading the skill into `isolated-builder`. Your role-dispatch decision (`2026-09-26-stack-agents-role-dispatch.md:49`) records that the skill was never re-tested natively. That change touches `adoption/agents/`, `examples/claude-native/agents/`, the workflow test mutations and the manifest, so it's separate work.

### The audit's proposed rewrite (hunks D1-D3, against the installed copy)
````diff
--- ~/.claude/skills/verification-before-completion/SKILL.md   (hunks D1–D3; vendored, shared with Codex, all projects)
+++ ~/.claude/skills/verification-before-completion/SKILL.md
@@ -8,31 +8,5 @@
 ## Overview
 
-**Core principle:** Evidence before claims, always.
-
-**Violating the letter of this rule is violating the spirit of this rule.**
-
-## The Iron Law
-
-```
-NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
-```
-
-If you haven't run the verification command in this message, you cannot claim it passes.
-
-## The Gate Function
-
-```
-BEFORE claiming any status or expressing satisfaction:
-
-1. IDENTIFY: What command proves this claim?
-2. RUN: Execute the FULL command (fresh, complete)
-3. READ: Full output, check exit code, count failures
-4. VERIFY: Does output confirm the claim?
-   - If NO: State actual status with evidence
-   - If YES: State claim WITH evidence
-5. ONLY THEN: Make the claim
-
-Skip any step = lying, not verifying
-```
+Claim that work is complete, fixed or passing only on evidence from this turn: identify the command that proves the claim, run it in full, read the whole output and exit code, and state the result with that evidence. If the check fails or you could not run it, report the actual status instead.
 
 ## Common Failures
@@ -48,27 +22,3 @@
 | Requirements met | Line-by-line checklist | Tests passing |
 
-## Red Flags - STOP
-
-- Using "should", "probably", "seems to"
-- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
-- About to commit/push/PR without verification
-- Trusting agent success reports
-- Relying on partial verification
-- Thinking "just this once"
-- Tired and wanting work over
-- **ANY wording implying success without having run verification**
-
-## Rationalization Prevention
-
-| Excuse | Reality |
-|--------|---------|
-| "Should work now" | RUN the verification |
-| "I'm confident" | Confidence ≠ evidence |
-| "Just this once" | No exceptions |
-| "Linter passed" | Linter ≠ compiler |
-| "Agent said success" | Verify independently |
-| "I'm tired" | Exhaustion ≠ excuse |
-| "Partial check is enough" | Partial proves nothing |
-| "Different words so rule doesn't apply" | Spirit over letter |
-
 ## Key Patterns
@@ -106,15 +56,3 @@
 ## When To Apply
 
-**ALWAYS before:**
-- ANY variation of success/completion claims
-- ANY expression of satisfaction
-- ANY positive statement about work state
-- Committing, PR creation, task completion
-- Moving to next task
-- Delegating to agents
-
-**Rule applies to:**
-- Exact phrases
-- Paraphrases and synonyms
-- Implications of success
-- ANY communication suggesting completion/correctness
+Before you report a task, fix, test run or build as successful, and before committing, pushing or opening a pull request.
````

### Evidence
The installed copy is byte-identical to the pin: sha256 `2befe7fc55bcadaa3d97dd9e8efeb633d2561c0ebe74c5a8b17c4d9e7e4520b3` (3646 bytes), the same as
source U1, which holds a copy of the upstream file at the pin. Upstream's own history of this file is source U2.

`adoption/skills/manifest.json:315-339`
```
 315:     {
 316:       "name": "verification-before-completion",
 317:       "source": "obra/superpowers",
 318:       "url": "https://github.com/obra/superpowers/tree/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/verification-before-completion",
 319:       "ref": "8ca22dba9a94f28898bbce59f2537ff4d87c747d",
 320:       "path": "skills/verification-before-completion",
 321:       "tree_sha": "a4cb0b69aaefeab540947a7f1642bdaad810e37a",
 322:       "skill_md_sha256": "2befe7fc55bcadaa3d97dd9e8efeb633d2561c0ebe74c5a8b17c4d9e7e4520b3",
 323:       "skill_md_bytes": 3646,
 324:       "description_chars": 225,
 325:       "upstream_disable_model_invocation": false,
 326:       "license": "MIT",
 327:       "official": false,
 328:       "audits": {
 329:         "gen_agent_trust_hub": "Pass",
 330:         "socket": "Pass",
 331:         "snyk": "Pass",
 332:         "url": "https://skills.sh/obra/superpowers/verification-before-completion",
 333:         "checked_at": "2026-09-25"
 334:       },
 335:       "status": "trial",
 336:       "gap": "CLAUDE.md requires supported findings resolved and changed behavior verified before claiming completion; no checklist skill enforces it.",
 337:       "claude_listing": "on",
 338:       "codex_enabled": true
 339:     },
```
git blame `adoption/skills/manifest.json:316-338`: 9a8257cd 2026-09-26 "Skills trial: 26 pinned skills, portable installer, status check and invoke-rate monitoring (all hosts) (#301)"

`.claude/agents/isolated-builder.md:1-10`
```
   1: ---
   2: name: isolated-builder
   3: description: Implement a bounded task in the owned worktree its brief names, prepared by the coordinator at the exact base, and return a verified handoff; refuses to edit without one or in the coordinator's own checkout.
   4: tools: Read, Edit, Write, Glob, Grep, Bash, ToolSearch, mcp__serena__find_symbol, mcp__serena__find_referencing_symbols, mcp__serena__find_declaration, mcp__serena__get_symbols_overview, mcp__serena__get_diagnostics_for_file, mcp__socraticode__codebase_search, mcp__socraticode__codebase_symbol, mcp__socraticode__codebase_impact, mcp__jcodemunch__route, mcp__jcodemunch__order, mcp__plugin_context-mode_context-mode__ctx_execute, mcp__plugin_context-mode_context-mode__ctx_execute_file, mcp__plugin_context-mode_context-mode__ctx_batch_execute, mcp__plugin_context-mode_context-mode__ctx_search, mcp__ai-memory__memory_query, mcp__ai-memory__memory_read_page
   5: model: opus
   6: effort: max
   7: skills:
   8:   - context-mode:context-mode
   9:   - verification-before-completion
  10: ---
```
git blame `.claude/agents/isolated-builder.md:9-9`: d022295a 2026-09-27 "Claude harness settings: credential-store and destructive-git denies, Opus role agents without frontmatter isolation, rtk-aware guard (#402)"
`adoption/agents/claude/isolated-builder.md:9` and `examples/claude-native/agents/isolated-builder.md:9` carry the same
preload.

`examples/claude-native/workflows/test-contract-mutations.mjs:68-73`
```
  68:   ['the security reviewer loses its preload', 'agents/security-reviewer.md', 'skills:\n  - security-best-practices\n', '', 'security-reviewer preloads exactly its reviewed skill'],
  69:   ['the role table sends security to the general reviewer', ROUTING_DOC_FILE, '| security | `security-reviewer` |', '| security | `evidence-reviewer` |', 'the role table maps each dispatch role'],
  70:   ['the builder loses its preloads', 'agents/isolated-builder.md', 'skills:\n  - context-mode:context-mode\n  - verification-before-completion\n', '', 'isolated-builder preloads exactly its reviewed skills'],
  71:   ['the builder substitutes a user-invocable-only skill', 'agents/isolated-builder.md', '  - verification-before-completion\n', '  - grill-me\n', 'isolated-builder preloads exactly its reviewed skills'],
  72:   ['a harmless reordering of the security reviewer tools', 'agents/security-reviewer.md', 'tools: Read, Glob, Grep, ', 'tools: Glob, Read, Grep, ', null],
  73:   ['a harmless reordering of the builder preloads', 'agents/isolated-builder.md', '  - context-mode:context-mode\n  - verification-before-completion\n', '  - verification-before-completion\n  - context-mode:context-mode\n', null],
```
git blame `examples/claude-native/workflows/test-contract-mutations.mjs:70-71`: 623d34fa 2026-09-27 "Add security-reviewer role and targeted skill preloads (WP5 PR-B) (#376)"

`adoption/bootstrap.md:343-349`
```
 343:      files verbatim to `~/.claude/agents/`; skipped per-file when already
 344:      byte-identical. They changed after `v2026.09.26`: `stack-researcher`,
 345:      `stack-verifier` and `security-reviewer` were added (the security role
 346:      preloads `security-best-practices`), and `isolated-builder` preloads
 347:      `context-mode:context-mode` and `verification-before-completion` and lost Serena's
 348:      symbol-edit tools, which would edit the parent session's checkout rather
 349:      than the builder's worktree.
```

`docs/decisions/2026-09-26-stack-agents-role-dispatch.md:43-51`
```
  43: The upstream [preload mechanism](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents)
  44: is documented, and the [listing-state addendum](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-listing-state-and-agent-preload)
  45: is now present in this checkout with its 2.1.283 `tdd`/`semgrep` probe. That addendum's probe covers
  46: pinned, table-listed skills; `context-mode:context-mode` is a plugin-scoped skill outside the pinned table,
  47: so its eligibility rests on the same upstream mechanism (no `disable-model-invocation` field in its
  48: installed `SKILL.md`) rather than a repeat of the probe on a plugin skill specifically.
  49: `verification-before-completion` and `security-best-practices` likewise have no repeat native probe
  50: specifically. First-prompt size for all three preloaded configurations remains unmeasured; source review
  51: is not preload acceptance. Their first-prompt sizes join the researcher/verifier rows' preregistered comparison.
```

### Constraints
- The adoption manifest pins the skill by upstream ref, tree and `skill_md_sha256`; a local edit breaks that pin and a
  skills update from upstream would undo it.
- The builder's preloads are a reviewed contract that the workflow contract mutations pin
  (`test-contract-mutations.mjs:70-73`: removing or substituting a preload must fail the suite).
- The same user-level skill is enabled for the second coding client (`codex_enabled: true`).

---

## M5: a history narrative in place of a rule, in a nested application's instruction file

Location: `blueprints/convergence-practice/application-delivery/AGENTS.md:15-18`

Verdict meaning: agree = replace lines 15-18 with hunk E's three lines exactly; amend = replace lines 15-18 with your
exact resolution_text instead; reject = keep lines 15-18 unchanged.

### The finding, as the audit reported it
**M5 · `blueprints/convergence-practice/application-delivery/AGENTS.md:15-18` · medium · rewrite (hunk E)**
- **Text:** "Project-readiness inspected the enclosing public worktree. Its installer writes worktree-root guidance and actions, so this bounded application retains the reviewable nested contract for the coordinator to integrate without modifying the enclosing repository's native actions."
- **Pattern:** a history narrative.
- **Why it's a problem:** it's a past-tense account of a readiness run, and the actual rule is buried in the "so" clause.


### The audit's proposed rewrite (hunk E)
```diff
--- a/blueprints/convergence-practice/application-delivery/AGENTS.md   (hunk E)
+++ b/blueprints/convergence-practice/application-delivery/AGENTS.md
@@ -15,4 +15,3 @@
-Project-readiness inspected the enclosing public worktree. Its installer writes
-worktree-root guidance and actions, so this bounded application retains the
-reviewable nested contract for the coordinator to integrate without modifying
-the enclosing repository's native actions.
+Keep this application's contract in this directory. The enclosing repository's
+installer writes its worktree-root guidance and actions; leave those to the
+coordinator, who integrates this nested contract.
```

### Evidence
`blueprints/convergence-practice/application-delivery/AGENTS.md:1-18`
```
   1: # Run-ledger application
   2: 
   3: Use the exact local commands and prerequisites in `project-contract.json` and
   4: `README.md`. Restore `uv.lock` and `pnpm-lock.yaml`; do not replace PostgreSQL
   5: with SQLite or use a shared database for tests. The transaction rollback test
   6: temporarily creates a constraint in the dedicated test database.
   7: 
   8: Generate `openapi.json` and `app/api.generated.ts` with `make schema` after API
   9: changes. Keep types derived from the native FastAPI schema. `make run` runs the
  10: two owned loopback application processes in the foreground; the operator owns
  11: the dedicated database lifecycle. Keep account stores and real research data
  12: outside this unauthenticated synthetic local fixture. No model/provider calls
  13: or deployment follow from these commands.
  14: 
  15: Project-readiness inspected the enclosing public worktree. Its installer writes
  16: worktree-root guidance and actions, so this bounded application retains the
  17: reviewable nested contract for the coordinator to integrate without modifying
  18: the enclosing repository's native actions.
```
git blame `blueprints/convergence-practice/application-delivery/AGENTS.md:15-18`: 04721779 2026-09-20 "Qualify typed Next FastAPI PostgreSQL application slice"

`blueprints/convergence-practice/application-delivery/CLAUDE.md` is the single line `@AGENTS.md`.

### Constraints
- No test, receipt, freeze record or fixture in the repository quotes or hashes this file's text, except the evidence
  manifest, which records its sha256 and byte count (`scripts/validate.py:376-387`); an edit is re-registered there.
- The file is the nested contract of a qualified application slice (`blueprints/convergence-practice/application-delivery/README.md`).
