# Adjudication input: 2026-09-27 prompt-audit convergence, one round (order BA)

Two independent reviews judged the same frozen packet (`packet.md`, sha256 0e6b6430a06f1de9f92d7c5a3316e698e7f365aac85515db7d2d32645da27877) and disagreed on the six units
below. For each unit, choose the return whose effective resolution the evidence supports better, or `neither`.

Rules:
- The returns are anonymous (Return A and Return B). Do not try to identify who wrote them; judge the evidence only.
  Model and product names inside quoted sources or repository files are subject matter, not authorship.
- Verify, do not trust: excerpts here are copies. The original files are at the read-only repository root
  `<base>` (main at 55fc8d17). Primary sources: `<adjudication>/sources.json` (gathered for the first round) and
  `<adjudication>/sources-supplement.json` (added for this round, fetched 2026-09-27: quotes from pages cited below that
  sources.json lacks).
- Choose `A`, `B` or `neither` per unit. `neither` means the current text stays unchanged. Do not write new text:
  only a return's resolution can be applied, exactly as written, and nothing is merged across returns.
- A resolution that another file, test or fixture would contradict or break, or that states something the repository
  or sources do not support, loses to one that does not. If both would, choose `neither`.
- Keep the operator's standing rules: licenses and incumbency are never selection criteria.
- Judge wording on whether the target model will follow it as intended, not on style.
- Each packet item keeps its first-round "Verdict meaning" line, which explains the returns' verdicts; your answer
  is a choice among the returns, not a new verdict.
- Unit F3X7 covers packet items F3 and X7, which edit the same sentence; the choice applies to both.
- Dependencies: N3's rows describe the mistakes that F3X7, F1 and N1 fix. Judge each N3 return on whether its rows
  describe the base's proven mistakes accurately and pass the log's shape test. After this round a chosen N3 row that
  states something the applied F3X7, F1 or N1 resolution does not make true is not added (it becomes a recorded
  residual); no row is rewritten.
- Every `sources` entry names a file:line or URL and quotes the text that supports your choice.
- An item is applied only when every adjudication of it chooses the same resolution; otherwise it stays unchanged
  and both positions are recorded.

---

# Unit F1

## F1: Role-dispatch rule in AGENTS.md vs the README rule it links

Location: AGENTS.md:36

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`AGENTS.md:34-37`
```
  34: - One coordinator integrates. Writing workers need separate worktrees and bounded file ownership.
  35: - This repository commits `.claude/settings.json` with Ultracode on. The Claude coordinator stays at `xhigh` under Ultracode, because a `max` session turns its workflow orchestration off, and never sets `CLAUDE_CODE_EFFORT_LEVEL` (any value overrides every child's effort). Pass `effort: 'max'` with an explicit task-matched `model` on every ad-hoc workflow `agent()` call: a stage without its own `effort` inherits the coordinator's `xhigh` unless its agent's frontmatter sets one. Probes and overturn conditions: `docs/decisions/2026-09-23-max-effort-default.md`.
  36: - Dispatch each workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call.
  37: - Until the trading lane moves to its own repository, `docs/lanes.md` assigns foundation, trading and shared paths, gives the protocol for shared hot files such as `manifests/evidence.json`, and requires one `lane:*` label per PR. Hand off to a live session that owns an area instead of editing it.
```
git blame `AGENTS.md:36-36`: 623d34fa 2026-09-27 "Add security-reviewer role and targeted skill preloads (WP5 PR-B) (#376)"
`examples/claude-native/workflows/README.md:219-219`
```
 219: - **Dispatch by role.** Every new or ad-hoc `agent()` stage names the `agentType` of its role in [the role table](#dispatch-by-role-2026-09-26); a stage with `general-purpose` or no `agentType` carries a `// dispatch: <reason>` comment beside the call. The saved scripts keep their reviewed routing, since they are vendored byte-identical (the `readiness-audit` verify stage runs as the default child).
```
git blame `examples/claude-native/workflows/README.md:219-219`: 623d34fa 2026-09-27 "Add security-reviewer role and targeted skill preloads (WP5 PR-B) (#376)"
`examples/claude-native/workflows/README.md:227-231`
```
 227: ### Dispatch by role (2026-09-26)
 228: 
 229: Name the role's `agentType` on each stage beside an explicit `model` and `effort: 'max'`; the stage's `model` overrides the agent's own default (the official workflows doc counts it as the per-invocation model). Each agent's body carries its role's lanes, so the packet carries only the task. Semantic (TypeSafe) reviews and layer-verdict lane stages keep the agents the routing table below names; a stage no role fits runs as the default child with a `// dispatch: <reason>` comment beside the call.
 230: 
 231: | Role | `agentType` | Model, effort | Use |
```
`examples/claude-native/workflows/README.md:23-32`
```
  23: ## Byte-identity check
  24: 
  25: `SHA256SUMS` in this directory (`sha256sum -- *.mjs *.js *.json`, excluding
  26: `README.md` and `SHA256SUMS` itself) is checked byte-for-byte by the
  27: `validate` workflow's "Check example workflow byte identity" step
  28: (`.github/workflows/validate.yml`) on every push and pull request. It is
  29: refreshed on purpose whenever one of these example files changes: regenerate
  30: it with the same command from this directory and commit the new file in the
  31: same change as the edited example. An unexplained mismatch on an unrelated PR
  32: means one of these files changed without an intentional update here.
```
`examples/claude-native/workflows/readiness-audit.js:95-99`
```
  95: const verify = await agent(
  96:   PACKET + '\nYou are an adversarial verifier. Open every cited source yourself and try to REFUTE each claim; default to unverifiable when you cannot. Return exactly one verdict for every reader claim, copying its claim string exactly, with nonblank evidence. Include a nonblank correction for corrected claims. Also return one source_verdicts entry for each requested packet item, copying packet_id and source exactly: independently confirm the returned source evidence and command outcome, including nonzero exits; use unverifiable if you cannot establish it. Emit only the exact (packet.id, item) pairs listed in each packet.items; never copy extra result.sources entries or combine one packet id with another packet\'s item. Packets whose result is null were NOT read: list their sources under missing and do not treat the audit as complete. The missing field is only for exact requested source identifiers that are unavailable or unverified. Put independently established additional facts the readers missed, with their evidence, in readiness_verdict; these are not missing sources. Then answer the question in readiness_verdict with the single most blocking gate and its evidence. A complete audit may conclude that the project is not ready.\nQuestion: ' + question + '\nReader packets (result null = unread): ' + JSON.stringify(packets),
  97:   { label: 'verify', phase: 'Verify', schema: VERIFY, model: 'opus', effort: 'max' },
  98: )
  99: if (!verify) log('verifier returned null; claims are unverified')
```
`tools/sota-convergence/landscape-sweep/sweep.js:38-42`
```
  38: // The Claude judgment stages (discover, refute-facts, refute-fit, critic) run as this agent type
  39: // (adoption/agents/claude/landscape-sweep-worker.md): Opus at effort max with WebFetch disallowed, so pages come in
  40: // through context-mode's ctx_fetch_and_index and ctx_search as the page's own text, while Skill and the ctx_* tools
  41: // stay available. The GPT-6 wrappers keep the default type: they only run commands and return the raw result.
  42: const WORKER = 'landscape-sweep-worker'
```
`tools/sota-convergence/landscape-sweep/sweep.js:109-110`
```
 109:   const r = await agent(wrapperPrompt(job, steps, promptFile, 'discover'),
 110:     { label: `gpt6-discover:${L.layer_id}${suffix ? ':followup' : ''}`, phase: phaseName, model: 'sonnet', effort: 'max', schema: WRAP_SCHEMA })
```
`tests/test_install_claude_profile.py:650-658`
```
 650:         self.assertTrue(rows)
 651:         for role, agent in rows.items():
 652:             with self.subTest(role=role):
 653:                 self.assertTrue((icp.AGENTS_SRC_DIR / f"{agent}.md").is_file(), f"{role} names {agent}")
 654:         pointer = [line for line in (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
 655:                    if "examples/claude-native/workflows/README.md" in line]
 656:         self.assertTrue(any("agentType" in line for line in pointer), "no AGENTS.md line points dispatch at the table")
 657: 
 658:     def test_the_role_table_reader_needs_the_role_header(self):
```
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "AGENTS.md",
 "old": "- Dispatch each workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call.",
 "new": "- Dispatch each new or ad-hoc workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call. Saved scripts keep their reviewed routing; the vendored ones in that directory are byte-identical."
}
```
### Constraints
- Some AGENTS.md line must contain both the workflows README path and `agentType` (tests/test_install_claude_profile.py:654-656).
- AGENTS.md is always loaded; keep it short.

## Return A

Verdict: agree

Effective resolution: Agrees with the packet's proposed resolution for this item, exactly as written in the item above.

Reasons: The edit restores the README's explicit scope and preserves the tested README/agentType pointer. It also avoids incorrectly requiring changes to the saved readiness verifier's reviewed routing.

Sources:
- `examples/claude-native/workflows/README.md:219`: "The saved scripts keep their reviewed routing, since they are vendored byte-identical (the `readiness-audit` verify stage runs as the default child)."
- `examples/claude-native/workflows/readiness-audit.js:97`: "{ label: 'verify', phase: 'Verify', schema: VERIFY, model: 'opus', effort: 'max' }"
- `tests/test_install_claude_profile.py:656`: "self.assertTrue(any(\"agentType\" in line for line in pointer), \"no AGENTS.md line points dispatch at the table\")"

## Return B

Verdict: amend

Effective resolution: Replacement (verbatim):

```text
{
 "file": "AGENTS.md",
 "line": 36,
 "old": "- Dispatch each workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call.",
 "new": "- Dispatch each new or ad-hoc workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call. The saved scripts vendored in that directory keep their reviewed routing, byte-identical to agent-lab."
}
```

Reasons: The diagnosis is right. AGENTS.md:36 requires role dispatch for every workflow agent() stage, while README:219 (same commit 623d34fa) exempts the saved scripts because they are vendored byte-identical, so a literal reader could retrofit readiness-audit.js and break its agent-lab/SHA256SUMS identity. The proposed addition overshoots in two ways. First, 'Saved scripts keep their reviewed routing' widens README:219's exemption, which rests on vendoring, to every saved script in the repository. That includes repository-authored workflows such as tools/sota-convergence/landscape-sweep/sweep.js, whose GPT-6 wrapper stages (109-110, 121-122) carry no agentType and no // dispatch: comment; this is the scope-restating mistake N3 row 3 records. Second, 'byte-identical' has no object; README:9-10 says byte-identical to agent-lab. The amended line keeps the new-or-ad-hoc scope, names only the vendored scripts, and still passes tests/test_install_claude_profile.py:654-656 (README path and agentType on one line; checked). The old line occurs once. Routine for every edit in this unit: manifests/evidence.json /files records each edited file's sha256 (AGENTS.md at 3474-3476), so regenerate it with scripts/evidence_manifest.py --write (named at scripts/validate.py:373).

Sources:
- `AGENTS.md:36`: "- Dispatch each workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call."
- `examples/claude-native/workflows/README.md:219`: "The saved scripts keep their reviewed routing, since they are vendored byte-identical (the `readiness-audit` verify stage runs as the default child)."
- `examples/claude-native/workflows/README.md:9-10`: "`review-changes.js`, `readiness-audit.js` and `layer-verdict-lane.js` are\nbyte-identical to agent-lab `b31f640`"
- `tools/sota-convergence/landscape-sweep/sweep.js:109-110`: "const r = await agent(wrapperPrompt(job, steps, promptFile, 'discover'),\n    { label: `gpt6-discover:${L.layer_id}${suffix ? ':followup' : ''}`, phase: phaseName, model: 'sonnet', effort: 'max', schema: WRAP_SCHEMA })"
- `tests/test_install_claude_profile.py:656`: "self.assertTrue(any(\"agentType\" in line for line in pointer), \"no AGENTS.md line points dispatch at the table\")"

---

# Unit F2

## F2: All-caps scope words in the landscape-sweep templates

Location: tools/sota-convergence/landscape-sweep/templates.json (common, discover, facts, fit, critic)

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
Consumers (tools/sota-convergence/landscape-sweep/sweep.js): `common` is prepended to every Claude stage; `discover` goes to Claude and GPT-6 discovery, `facts` to the Claude refute-facts stage only, `fit` to the Claude and GPT-6 fit refuters, `critic` to the Claude critic.
`tools/sota-convergence/landscape-sweep/sweep.js:168-175`
```
 168:   let facts = null, fitC = null, fitG = null
 169:   if (kept.length) {
 170:     const props = JSON.stringify(forRefuters(kept), null, 1)
 171:     ;[facts, fitC, fitG] = await parallel([
 172:       () => agent(T.common + '\n\n' + fill(T.facts, { LAYER_ID: L.layer_id, REQUIREMENT: `see ${inputPath(L.layer_id)} (Read tool)`, PROPOSALS: props }) + `\nUse gh api (Bash) for GitHub facts; ${PAGES}.`,
 173:         { label: `refute-facts:${L.layer_id}${lsuf}`, phase: phaseR, model: 'opus', effort: 'max', agentType: WORKER, schema: A.schemas.votes }),
 174:       () => agent(T.common + '\n\n' + fill(T.fit, { LAYER_INPUT: `Read the layer input JSON file with the Read tool: ${inputPath(L.layer_id)}`, PROPOSALS: props, LAYER_ID: L.layer_id }) + `\nUse gh api (Bash) for GitHub facts; ${PAGES}.`,
 175:         { label: `refute-fit:${L.layer_id}${lsuf}`, phase: phaseR, model: 'opus', effort: 'max', agentType: WORKER, schema: A.schemas.votes }),
```
Occurrences (key: phrase):
- common: `is NOT evidence of quality`
- discover: `discovery researcher for ONE layer`
- discover: `find the strongest CURRENT candidates`
- discover: `winners for THIS requirement`
- facts: `facts/identity refuter for ONE layer`
- facts: `For EACH proposal check`
- fit: `fit/standing refuter for ONE layer`
- fit: `For EACH proposal vote refuted=true if ANY holds`
- fit: `winners for THIS requirement`
- critic: `discovery most likely MISSED a strong`
git blame `tools/sota-convergence/landscape-sweep/templates.json:1-8`: 1b0e4598 2026-09-26 "Landscape-sweep harness: two-family (Claude + GPT-6) saturation sweep as a repro"; 1d8f2f7c 2026-09-27 "Landscape-sweep templates: OpenSSF Scorecard maintenance rule; licenses never a "
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "tools/sota-convergence/landscape-sweep/templates.json",
 "replacements": [
  {
   "key": "common",
   "old": "is NOT evidence of quality",
   "new": "is not evidence of quality"
  },
  {
   "key": "discover",
   "old": "discovery researcher for ONE layer",
   "new": "discovery researcher for one layer"
  },
  {
   "key": "discover",
   "old": "find the strongest CURRENT candidates",
   "new": "find the strongest current candidates"
  },
  {
   "key": "discover",
   "old": "winners for THIS requirement",
   "new": "winners for this requirement"
  },
  {
   "key": "facts",
   "old": "facts/identity refuter for ONE layer",
   "new": "facts/identity refuter for one layer"
  },
  {
   "key": "facts",
   "old": "For EACH proposal check",
   "new": "For each proposal, check"
  },
  {
   "key": "fit",
   "old": "fit/standing refuter for ONE layer",
   "new": "fit/standing refuter for one layer"
  },
  {
   "key": "fit",
   "old": "For EACH proposal vote refuted=true if ANY holds",
   "new": "For each proposal, vote refuted=true if any of these holds"
  },
  {
   "key": "fit",
   "old": "winners for THIS requirement",
   "new": "winners for this requirement"
  },
  {
   "key": "critic",
   "old": "discovery most likely MISSED a strong",
   "new": "discovery most likely missed a strong"
  }
 ],
 "note": "Section labels such as `ROLE:` and `FOLLOW-UP ROUND.` stay. The change-detector pin PROMPTS_SHA256_CURRENT in tests/test_landscape_sweep_harness.py is recomputed for the final text."
}
```
### Constraints
- Phrase assertions in tests/test_landscape_sweep_harness.py:249-270 must keep passing.
- The `common` Skills paragraph must keep matching TEMPLATE_SKILLS (build_args.py:55-57).

## Return A

Verdict: agree

Effective resolution: Agrees with the packet's proposed resolution for this item, exactly as written in the item above.

Reasons: Each of the ten old phrases occurs exactly once in its key (checked). The capitalized scope words reach Claude through common plus the role text (sweep.js:85, 172, 174, 197) and GPT-6 through make_prompt.py:65. A fit prompt therefore carries five emphases and a discover prompt four. Claude Code's CLAUDE.md guidance (S5) reserves emphasis for a single line the model keeps skipping. S1 (Opus 4.5/4.6) and S9 (GPT-5) report capitalized or aggressive wording over-triggering, and S10 says GPT-6 Astra is more sensitive to instructions. The lowercase wording keeps the same scope, and 'One vote per proposal' and 'Set layer_id' remain. No test asserts a replaced phrase. The FOLLOW-UP ROUND. label (test :325), the ROLE: labels and the test-asserted output marker TOO NEW TO ASSESS (<90 days) (test :266) stay, and TEMPLATE_SKILLS is untouched. PROMPTS_SHA256_CURRENT (test :45, :247) must be recomputed once, for the final text after F2, F3 and X7. Confidence is moderate because sources.json records no Anthropic statement on all-caps wording for the 5.x models.

Sources:
- `https://code.claude.com/docs/en/best-practices.md (sources.json S5)`: "If Claude keeps skipping one instruction, add emphasis such as \"IMPORTANT\" to that line alone. If you emphasize many lines, none of them stands out."
- `https://github.com/openai/openai-cookbook/blob/6dc6324fb9ed780b32b787f23fad336e9f1eff15/examples/gpt-5/gpt-5_prompting_guide.ipynb (sources.json S9)`: "While this worked well with older models that needed encouragement to analyze context thoroughly, they found it counterproductive with GPT-5, which is already naturally introspective and proactive at gathering context."
- `tools/sota-convergence/landscape-sweep/make_prompt.py:65`: "return templates[\"common\"] + \"\\n\\n\" + body + TAIL"
- `tests/test_landscape_sweep_harness.py:247`: "self.assertEqual(sweep_common.prompts_sha256(frozen), PROMPTS_SHA256_CURRENT)"
- `tests/test_landscape_sweep_harness.py:266`: "self.assertIn(\"TOO NEW TO ASSESS (<90 days)\", common)"

## Return B

Verdict: reject

Effective resolution: Keep the current text; no edit.

Reasons: These capitals emphasize scope, quantifiers and recency in separate bounded prompts. The supplied evidence does not establish a compliance problem for the configured models. The cited warning concerns aggressive tool prompting for older named models; it does not justify this case-only cleanup on behavioral grounds.

Sources:
- `tools/sota-convergence/landscape-sweep/templates.json:3`: "Task: find the strongest CURRENT candidates that could beat, replace or usefully complement this layer's winners for THIS requirement on these hosts."
- `tools/sota-convergence/landscape-sweep/README.md:35-46`: "Claude `opus` (claude-opus-5-5 on 2026-09-26), max, as `landscape-sweep-worker`"
- `[Anthropic prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)`: "Claude Opus 4.5 and Claude Opus 4.6 are also more responsive to the system prompt than previous models."

---

# Unit F3X7

## F3: facts refuter defaults to refuted on unverifiable facts, contradicting the maintenance rule in common and fit

Location: templates.json `facts`

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`facts` template (full text):
```
ROLE: facts/identity refuter for ONE layer. Assume every proposal below may contain a false or unsupported fact.
Layer: <<LAYER_ID>> -- requirement: <<REQUIREMENT>>
Proposals (JSON):
<<PROPOSALS>>
For EACH proposal check with primary sources (GitHub API/pages via gh api or fetch; official docs): the repository exists at that canonical URL (or its rename), is not archived or abandoned contrary to the claim, and the license, latest release, release date, stars/activity and every cited evidence URL actually say what the proposal claims. Vote refuted=true if any material factual claim is false, unsupported by its cited source, or unverifiable; refuted=false only when you verified the facts. Default to refuted=true when uncertain. Give confidence 0..1, short reasoning, and the refs (URLs) you checked. One vote per proposal, same repository string. Set role to facts and layer_id to <<LAYER_ID>>.
Verification budget (hard): at most 8 web searches, 10 page fetches and 30 GitHub API calls in total for all proposals.
```
`fit` template (full text):
```
ROLE: fit/standing refuter for ONE layer. Assume every proposal below is wrong for this repository and try to break it.
Layer input:
<<LAYER_INPUT>>
Proposals (JSON):
<<PROPOSALS>>
For EACH proposal vote refuted=true if ANY holds: no concrete, evidence-backed gap versus the current winners for THIS requirement (a plausible advantage in measured quality, SOTA-ness, maintenance or fit counts; incumbency does not count for the winner); it duplicates a winner or an already-known alternative without new evidence; it does not support linux x86_64/WSL2 or macOS arm64 where the layer needs it; it is infeasible on the hosts (e.g. needs more than 24 GB VRAM or more RAM than available, or NVFP4-only weights on Ada); it is stale under the selection principles' maintenance rule (archived, or no default-branch commit in the last 90 days, established from evidence; unknown maintenance is never a reason to refute); it requires a paid SaaS or new credentials without a gap that justifies it; it conflicts with the selection principles; or its label is wrong (a targeted_candidate with no feasible bounded trial, or a not_adopted whose rejection reason is itself wrong). Vote refuted=false only when the proposal and its label hold up. Default to refuted=true when uncertain. Give confidence 0..1, reasoning, refs. One vote per proposal, same repository string. Set role to fit and layer_id to <<LAYER_ID>>.
Verification budget (hard): at most 8 web searches, 10 page fetches and 30 GitHub API calls in total for all proposals.
```
`common` template (full text; it is prepended to the facts prompt, sweep.js:172):
```
Date: <<DATE>>. You are one worker in a saturation sweep of the public repository seathatflowsinourveins/native-agent-stack: a portable reference stack of native agent tooling (Claude Code, Codex, MCP, memory/RAG, token efficiency, CI/supply chain, observability) whose north star is US-equities research and historical simulation (NautilusTrader 2.0.0rc5 with an IBKR destination and a separate Alpaca adapter; LEAN as comparison engine), followed by independently qualified paper trading. Live trading is out of scope.
Hosts: linux-wsl2-x86_64 GPU workstation (Threadripper PRO 5975WX 48 CPUs, 102 GiB RAM, RTX 4090 24 GB, Ada: FP8 native, NVFP4 not native) and macos-arm64 Macs (M5 Pro, 24 GB and 64 GB).
Selection principles: native accounts and supported upstream installation; maintained upstream, by a rule derived from the OpenSSF Scorecard Maintained check (https://github.com/ossf/scorecard/blob/main/docs/checks.md#maintained), which scores an archived repository lowest, uses a 90-day window and gives its top score to at least one commit per week and partial credit for maintainers' issue activity: a repository is stale, and excluded whatever its stars, when it is archived or has no commit on its default branch in the last 90 days (establish this with gh api repos/<owner>/<repo>/commits?since=<date 90 days ago>&per_page=1 or the same https://api.github.com REST URL, not from pushed_at, which counts any branch; a lane that cannot reach either source, such as a web-only lane, records the commit fact as unknown and never excludes or refutes a repository on unknown maintenance, because a missing result is pending, never refuted); this rule excludes only the zero-activity end, so record lower activity as a maintenance fact without excluding; a repository created less than 90 days ago is too new to assess and must say so at the start of its demonstrated_gap ("TOO NEW TO ASSESS (<90 days): ..."); an old release tag on an actively committed branch is not stale (pin the commit when a needed fix exists only on the branch); licenses are recorded as information only and are never a reason to exclude, refute or rank down a candidate (the operator's private experimental environment); no paid SaaS or new credentials unless a demonstrated gap requires it; local-first and privacy-filtered; evidence over popularity (stars and install counts are never evidence of fit).
Rules: primary sources only (GitHub API/pages for releases, tags, stars, pushed_at, archived, license, renames; official docs and changelogs; Hugging Face model cards). Cite the URL for every fact. Read-only: never install, clone-and-run, or execute candidate code; never read or print credentials. Canonical repository form: https://github.com/<owner>/<repo> (follow renames to the current owner). Answer only in the required JSON.
Skills (installed from adoption/skills/manifest.json, the pinned <<SKILLS_CHECKED_AT>> skills trial): use the ones that fit your role and record every skill you actually used in skills_used. Discovery: search-first (survey maintained upstream options before judging) and iterative-retrieval (staged, bounded retrieval). Refutation: verification-before-completion (evidence before any verdict), supply-chain-risk-auditor (maintenance, ownership, advisories, archived/renamed upstreams) and fp-check (verify a claim before calling it true or false). Layer-specific where relevant: agentic-actions-auditor (CI and GitHub automation), security-threat-model / codeql / semgrep / sarif-parsing (security and supply chain), property-based-testing (quality evaluation), mcp-builder (MCP surfaces), modern-python (Python tooling), agent-browser (JavaScript-heavy pages you cannot read otherwise). In Claude Code invoke a skill with the Skill tool; in Codex mention it as $skill-name. Do not load skills you do not use.
Merit, not incumbency: the current winners are provisional. Being the current winner, the retained control (for example ai-memory in durable-memory is recorded as the retained control, not a measured best), popular, or already installed is NOT evidence of quality. Judge every repository, winners included, on current evidence: measured quality on this requirement (benchmarks, retained comparisons), SOTA-ness (recent releases, capability), maintenance and supply-chain health, and platform fit (license is information only). A candidate that is plausibly better than a winner on such evidence has a demonstrated gap. Report in notes any winner whose standing rests on incumbency rather than evidence.
```
`tests/test_landscape_sweep_harness.py:249-270`
```
 249:     def test_templates_never_refute_on_license_and_name_the_maintenance_rule(self):
 250:         templates = json.loads((HARNESS / "templates.json").read_text())
 251:         common, fit = templates["common"], templates["fit"]
 252:         # Licenses: information only, in the selection principles and in the merit criteria every role receives.
 253:         self.assertIn("never a reason to exclude, refute or rank down", common)
 254:         self.assertIn("and platform fit (license is information only)", common)
 255:         self.assertNotIn("license and platform fit", common)
 256:         self.assertNotIn("OSI or clearly usable license", common)
 257:         self.assertNotIn("license is non-commercial", fit)
 258:         # No role other than the facts refuter's accuracy check may treat a license as a criterion.
 259:         for key, text in templates.items():
 260:             for phrase in ("license is non-commercial", "restrictive license", "unclear license", "usable license"):
 261:                 self.assertNotIn(phrase, text, f"{key} still uses a license as a criterion: {phrase!r}")
 262:         # Maintenance: derived from the Scorecard check, with its evidence command and a flag destination.
 263:         self.assertIn("derived from the OpenSSF Scorecard Maintained check", common)
 264:         self.assertIn("commits?since=", common)
 265:         self.assertIn("not from pushed_at", common)
 266:         self.assertIn("TOO NEW TO ASSESS (<90 days)", common)
 267:         self.assertIn("it is stale under the selection principles' maintenance rule", fit)
 268:         # A lane that cannot reach the commit evidence (the web-only GPT-6 lane) never refutes on it.
 269:         self.assertIn("never excludes or refutes a repository on unknown maintenance", common)
 270:         self.assertIn("unknown maintenance is never a reason to refute", fit)
```
Commit that added the rule to common and fit (#385):
```
1d8f2f7c 2026-09-27 Landscape-sweep templates: OpenSSF Scorecard maintenance rule; licenses never a refutation reason (#385)

* Landscape-sweep templates: OpenSSF Scorecard maintenance rule; licenses never a refutation reason

The sweep's templates change in two ways:
- "Maintained upstream with 2025-2026 activity" becomes the OpenSSF Scorecard
  Maintained check. A stale repository (archived, or without a default-branch
  commit in the last 90 days) is excluded whatever its stars. A repository
  under 90 days old is flagged as too new to assess. An old tag on an active
  branch is not stale; pin the commit instead.
- Licenses are recorded as information only and are never a reason to exclude,
  refute or rank down a candidate. This follows the operator's 2026-09-26
  decision; the fit refuter was still told to refute non-commercial or unclear
  licenses.
The template-hash change detector moves to PROMPTS_SHA256_CURRENT (dc5ffcb6...).
The 2026-09-26 value stays as that run's recorded hash. A new test checks both
rules are in the templates.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <session URL redacted>

* #385 review repair: drop license from the shared merit criteria; state the maintenance rule precisely

Independent review (headless Sonnet 5, effort max): needs_changes, 1 major and 4 minor findings.
- major: the shared common template, which reaches every role including the
  fit refuter, still judged "license and platform fit". It now reads "and
  platform fit (license is information only)".
- 
[... truncated]
```
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "tools/sota-convergence/landscape-sweep/templates.json",
 "key": "facts",
 "old": "Default to refuted=true when uncertain.",
 "new": "Default to refuted=true when uncertain. Maintenance is the exception: an unverifiable commit or activity fact is recorded as unknown and is never a reason to refute (the selection principles' maintenance rule).",
 "note": "If X7 is also adopted, the combined sentence is used instead: `Default to refuted=true when uncertain. Maintenance and license are the exceptions: an unverifiable commit or activity fact is recorded as unknown, and a wrong or unverifiable license is corrected in the reasoning; neither is a reason to refute (the selection principles).`"
}
```
### Constraints
- A new test asserts the facts template states the rule; it is first run on the base and must fail there.

## X7: facts refuter checks license accuracy while common says licenses are never a refutation reason

Location: templates.json `facts` (license)

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
See F3 for the full `facts` and `common` texts. The relevant common clause: "licenses are recorded as information only and are never a reason to exclude, refute or rank down a candidate". The facts text: "the license, latest release, release date, stars/activity and every cited evidence URL actually say what the proposal claims. Vote refuted=true if any material factual claim is false ..."
`tests/test_landscape_sweep_harness.py:249-259`
```
 249:     def test_templates_never_refute_on_license_and_name_the_maintenance_rule(self):
 250:         templates = json.loads((HARNESS / "templates.json").read_text())
 251:         common, fit = templates["common"], templates["fit"]
 252:         # Licenses: information only, in the selection principles and in the merit criteria every role receives.
 253:         self.assertIn("never a reason to exclude, refute or rank down", common)
 254:         self.assertIn("and platform fit (license is information only)", common)
 255:         self.assertNotIn("license and platform fit", common)
 256:         self.assertNotIn("OSI or clearly usable license", common)
 257:         self.assertNotIn("license is non-commercial", fit)
 258:         # No role other than the facts refuter's accuracy check may treat a license as a criterion.
 259:         for key, text in templates.items():
```
A refuted facts vote drops the proposal from the sweep's survivors (a proposal survives only if the facts refuter and both fit refuters vote not refuted; tools/sota-convergence/landscape-sweep/README.md:48-55).
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "tools/sota-convergence/landscape-sweep/templates.json",
 "key": "facts",
 "old": "Default to refuted=true when uncertain.",
 "new": "Default to refuted=true when uncertain. License is the exception: a wrong or unverifiable license is corrected in the reasoning and is never a reason to refute (licenses are information only under the selection principles).",
 "note": "If F3 is also adopted, the combined sentence is used instead: `Default to refuted=true when uncertain. Maintenance and license are the exceptions: an unverifiable commit or activity fact is recorded as unknown, and a wrong or unverifiable license is corrected in the reasoning; neither is a reason to refute (the selection principles).`. The test comment at tests/test_landscape_sweep_harness.py:256 would then say the facts refuter records license corrections and no role refutes on a license."
}
```
### Constraints
- The existing test comment deliberately names the facts refuter's license accuracy check as the one exception; weigh it.

## Return A

Verdict: agree (both items)

Effective resolution: Agrees with both proposals, so the combined sentence in their notes applies, exactly:

```text
Default to refuted=true when uncertain. Maintenance and license are the exceptions: an unverifiable commit or activity fact is recorded as unknown, and a wrong or unverifiable license is corrected in the reasoning; neither is a reason to refute (the selection principles).
```

with the test-comment change the X7 note describes.

Reasons: (F3) The later facts instruction can override the shared unknown-maintenance rule in practice. An explicit local exception resolves that conflict while leaving established falsehoods refutable. Since X7 is also accepted, use the proposed combined sentence once, add the required regression test, and recompute PROMPTS_SHA256_CURRENT.

(X7) A license-only facts refutation eliminates the candidate, making license accuracy a selection gate despite the categorical standing rule. Preserve accuracy by recording a correction—or unknown when unverifiable—without refuting on that basis. The test comment must follow the standing rule. Use the proposed combined F3/X7 sentence.

Sources:
- `tools/sota-convergence/landscape-sweep/templates.json:2`: "never excludes or refutes a repository on unknown maintenance, because a missing result is pending, never refuted"
- `tools/sota-convergence/landscape-sweep/templates.json:4`: "Vote refuted=true if any material factual claim is false, unsupported by its cited source, or unverifiable; refuted=false only when you verified the facts. Default to refuted=true when uncertain."
- `tests/test_landscape_sweep_harness.py:41-42`: "# PROMPTS_SHA256_CURRENT, the sha256 of json.dumps(T, sort_keys=True, ensure_ascii=False). An intended template edit\n# changes every later run's prompts_sha256; update PROMPTS_SHA256_CURRENT with it."
- `tools/sota-convergence/landscape-sweep/templates.json:2`: "licenses are recorded as information only and are never a reason to exclude, refute or rank down a candidate"
- `tools/sota-convergence/landscape-sweep/README.md:48-49`: "A proposal survives only when the facts refuter, the Claude fit refuter and the\nGPT-6 fit refuter all vote not refuted."
- `tests/test_landscape_sweep_harness.py:258`: "# No role other than the facts refuter's accuracy check may treat a license as a criterion."

## Return B

Verdict: amend (both items)

Effective resolution: Replacement (verbatim):

```text
{
 "file": "tools/sota-convergence/landscape-sweep/templates.json",
 "key": "facts",
 "old": "Default to refuted=true when uncertain.",
 "new": "Default to refuted=true when uncertain. Unknown fields, maintenance and license are the exceptions (the selection principles): a null upstream_now field means unknown, not a false claim; record an unverifiable commit or activity fact as unknown, and a wrong or unverifiable license as a correction or as unknown, in your reasoning; none of these is a reason to refute.",
 "test_comment": {
  "file": "tests/test_landscape_sweep_harness.py",
  "line": 258,
  "old": "        # No role other than the facts refuter's accuracy check may treat a license as a criterion.",
  "new": "        # No role treats a license as a criterion: the facts refuter records a wrong or unverifiable license in its\n        # reasoning and never refutes on it."
 },
 "new_test_asserts_in_facts": [
  "a null upstream_now field means unknown",
  "record an unverifiable commit or activity fact as unknown",
  "none of these is a reason to refute"
 ],
 "note": "One replacement serves F3 and X7 together; apply it once, then recompute PROMPTS_SHA256_CURRENT for the final templates."
}
```

Reasons: (F3) The conflict is real. facts is sent with common (sweep.js:172). common tells a lane that cannot reach commit evidence to record it as unknown and never refute on it, and fit says unknown maintenance is never a reason to refute. facts, however, refutes unverifiable facts and defaults to refuted, and survival needs a not-refuted facts vote (README:48-49), so the facts gate cancels the #385 rule. The proposed sentence covers only unverifiable facts and misses the case the pipeline produces by design. The facts refuter receives each proposal's upstream_now (sweep.js:155-156), and the discover template and schemas/discover.json:53-100 allow null 'when unknowable'. After #385 the web-only GPT-6 discovery lane records commit facts as unknown. In the retained 2026-09-26 run the facts refuter refuted anomalyco/opencode and alpacahq/cli for null upstream_now fields (returns.json:2218, :17006); that role ran on Sonnet then and runs on Opus now, so this evidence is weighted modestly. The replacement is one edit of the single sentence 'Default to refuted=true when uncertain.' in facts, identical to X7's resolution_text, so apply it once. It also fixes the combined note's 'a wrong or unverifiable license is corrected', since an unverifiable license cannot be corrected. Checked on the base text: no banned license phrase (test :259-261), every assertion at :249-270 still holds, and the three new-test phrases are absent on base (the new test fails there) and present after the edit. Left as a residual: a verified but stale activity value, such as the same-day pushed_at drift that refuted eslazarev/purged-cross-validation, still refutes. A blanket exemption would let fabricated upstream_now pass the facts gate, and the xtdb vote used an implausible pushed_at as a fabrication signal.

(X7) The direction is right. common, which is sent in the same prompt as facts, says licenses are never a reason to refute. facts makes a wrong license a refuting fact, and a refuted facts vote drops the candidate (README:48-49), so a license mismatch acts as a selection gate against the operator's standing rule. The deliberate carve-out lives only in a test comment (test :258), which the model never sees, so the prompt itself is contradictory. Refuting is also unnecessary for accuracy: the facts vote's reasoning is carried into the record (convert.py:484), and survivors' licenses are read from the GitHub API in their source reviews (source_reviews.py:175). Apply the same single replacement as F3 (identical resolution_text), which states the license exception without implying that an unverifiable license can be 'corrected'. The proposal's note cites the test comment at line 256; it is at line 258 (line 256 is an assertion). The exact new comment text is in the resolution. The text contains no banned license phrase (test :259-261; checked).

Sources:
- `tools/sota-convergence/landscape-sweep/templates.json:4 (facts)`: "Vote refuted=true if any material factual claim is false, unsupported by its cited source, or unverifiable; refuted=false only when you verified the facts. Default to refuted=true when uncertain."
- `tools/sota-convergence/landscape-sweep/templates.json:2 (common)`: "a lane that cannot reach either source, such as a web-only lane, records the commit fact as unknown and never excludes or refutes a repository on unknown maintenance, because a missing result is pending, never refuted"
- `tools/sota-convergence/landscape-sweep/templates.json:3 (discover)`: "upstream_now (latest_release tag, released_at date, stars, pushed_at, archived, license -- from the GitHub API or page; null when unknowable)"
- `tools/sota-convergence/landscape-sweep/sweep.js:156`: "comparison_that_would_overturn: p.comparison_that_would_overturn, evidence: p.evidence, upstream_now: p.upstream_now, proposed_by: p.families }))"
- `evidence/artifacts/landscape-sweep-20260926/returns.json:2218`: "The proposal's upstream_now block claims stars, pushed_at, archived, latest_release, and released_at are all unavailable (null)"
- `evidence/artifacts/landscape-sweep-20260926/returns.json:17006`: "upstream_now block states latest_release=null, released_at=null and pushed_at=null, which is factually false"
- `tools/sota-convergence/landscape-sweep/README.md:48-49`: "A proposal survives only when the facts refuter, the Claude fit refuter and the\nGPT-6 fit refuter all vote not refuted."
- `tools/sota-convergence/landscape-sweep/templates.json:2 (common)`: "licenses are recorded as information only and are never a reason to exclude, refute or rank down a candidate (the operator's private experimental environment)"
- `tools/sota-convergence/landscape-sweep/templates.json:4 (facts)`: "and the license, latest release, release date, stars/activity and every cited evidence URL actually say what the proposal claims. Vote refuted=true if any material factual claim is false"
- `tests/test_landscape_sweep_harness.py:258`: "# No role other than the facts refuter's accuracy check may treat a license as a criterion."
- `tools/sota-convergence/landscape-sweep/source_reviews.py:175`: "license_id = (meta.get(\"license\") or {}).get(\"spdx_id\") or \"NOASSERTION\""
- `tools/sota-convergence/landscape-sweep/convert.py:484`: "\"reasoning\": f\"facts ({facts_model}): \" + (as_dict(fv).get(\"reasoning\") or \"missing\")},"

---

# Unit N1

## N1: Landscape-sweep README quotes a superseded prompt hash as the templates' current value

Location: tools/sota-convergence/landscape-sweep/README.md:192-195 and :435-439

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`tools/sota-convergence/landscape-sweep/README.md:190-196`
```
 190:     `convert.py` writes them as `@RETURNS@#/...` and `make_result.py` fills in the path.
 191:   - `proposed` must equal the set of adjudicated repositories, and every proposal gets both votes.
 192: - **`prompts_sha256`.** This is `sha256(json.dumps(T, sort_keys=True, ensure_ascii=False))` of the run's frozen,
 193:   dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the
 194:   templates here give `3adfbed7…18d4` (tested), the value computed on 2026-09-26 from that run's staged
 195:   `templates.json`. That is a local check; the run's registered record is the evidence of what it used.
 196: - **Manifest.** `manifest_ref` is the dated SOTA manifest built from `lanes.json`. The record's `date` is its
```
`tools/sota-convergence/landscape-sweep/README.md:432-440`
```
 432: 
 433: ## Differences from the 2026-09-26 prototype
 434: 
 435: Parity with the prototype is not established by this package. On 2026-09-26 three unretained local checks were
 436: run (prompt bytes, the smoke's conversion, `usage_record.py` on the smoke's transcripts); their outputs are not
 437: kept, so they are not evidence. `PROMPTS_SHA256_20260926` in the tests is the value this package computes from its
 438: templates, and it matches the 2026-09-26 run only if that run's retained record carries the same
 439: `prompts_sha256`. Treat parity as unverified until that record is registered and compared.
 440: 
```
git blame `tools/sota-convergence/landscape-sweep/README.md:192-195`: 1b0e4598 2026-09-26 "Landscape-sweep harness: two-family (Claude + GPT-6) saturation sweep as a repro"
`tests/test_landscape_sweep_harness.py:40-48`
```
  40: # A change detector: templates.json filled with the 2026-09-26 run's values (date, layer count, skills date) must give
  41: # PROMPTS_SHA256_CURRENT, the sha256 of json.dumps(T, sort_keys=True, ensure_ascii=False). An intended template edit
  42: # changes every later run's prompts_sha256; update PROMPTS_SHA256_CURRENT with it.
  43: # 2026-09-27: the maintenance rule is derived from the OpenSSF Scorecard Maintained check, and licenses are information only
  44: # (never a refutation reason), per the operator's 2026-09-26/27 decisions.
  45: PROMPTS_SHA256_CURRENT = "f64eec22f82355b18854be9c05c4eba0fdbaf6b6732296fc18c2fae0ff5daf8d"
  46: # The 2026-09-26 run's own value, kept in that run's record (evidence/artifacts/landscape-sweep-20260926/README.md);
  47: # fixtures below use it as a historical run's recorded prompts_sha256.
  48: PROMPTS_SHA256_20260926 = "3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4"
```
`evidence/artifacts/landscape-sweep-20260926/README.md:15-19`
```
  15: The run used the 2026-09-26 scratchpad prototype of the lane. The same lane is now packaged as
  16: [`tools/sota-convergence/landscape-sweep/`](../../../tools/sota-convergence/landscape-sweep/README.md) (#324). The
  17: run's `prompts_sha256` is `3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4`, the sha256 of the
  18: prototype's staged templates. The packaged templates, filled with this run's values, give the same hash (a local check
  19: in `tests/test_landscape_sweep_harness.py`). The packaged tools produced the returns, lanes, layers, usage records,
```
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "tools/sota-convergence/landscape-sweep/README.md",
 "replacements": [
  {
   "old": "dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the\n  templates here give `3adfbed7…18d4` (tested), the value computed on 2026-09-26 from that run's staged\n  `templates.json`. That is a local check; the run's registered record is the evidence of what it used.",
   "new": "dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the\n  templates here give `PROMPTS_SHA256_CURRENT` in `tests/test_landscape_sweep_harness.py`, which changes with\n  every intended template edit; the 2026-09-26 run's own value is kept there as `PROMPTS_SHA256_20260926`.\n  That is a local check; the run's registered record is the evidence of what it used."
  },
  {
   "old": "kept, so they are not evidence. `PROMPTS_SHA256_20260926` in the tests is the value this package computes from its\ntemplates, and it matches the 2026-09-26 run only if that run's retained record carries the same\n`prompts_sha256`. Treat parity as unverified until that record is registered and compared.",
   "new": "kept, so they are not evidence. `PROMPTS_SHA256_20260926` in the tests is the value this package computed from its\ntemplates before the 2026-09-27 template edits, and the 2026-09-26 run's registered record\n(`evidence/artifacts/landscape-sweep-20260926/README.md`) carries the same `prompts_sha256`, so the templates\nmatched that run's staged copy. The other parity checks were not retained and stay unverified."
  }
 ]
}
```
### Constraints
- Keep the evidence distinction: a local hash check is not the run's evidence.

## Return A

Verdict: amend

Effective resolution: Replacement (verbatim):

```text
{
 "replacements": [
  {
   "file": "tools/sota-convergence/landscape-sweep/README.md",
   "old": "dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the\n  templates here give `3adfbed7…18d4` (tested), the value computed on 2026-09-26 from that run's staged\n  `templates.json`. That is a local check; the run's registered record is the evidence of what it used.",
   "new": "dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the\n  templates here give `PROMPTS_SHA256_CURRENT` in `tests/test_landscape_sweep_harness.py`, which changes with\n  every intended template edit; the 2026-09-26 run's own value is kept there as `PROMPTS_SHA256_20260926`.\n  That is a local check; the run's registered record is the evidence of what it used."
  },
  {
   "file": "tools/sota-convergence/landscape-sweep/README.md",
   "old": "Parity with the prototype is not established by this package. On 2026-09-26 three unretained local checks were\nrun (prompt bytes, the smoke's conversion, `usage_record.py` on the smoke's transcripts); their outputs are not\nkept, so they are not evidence. `PROMPTS_SHA256_20260926` in the tests is the value this package computes from its\ntemplates, and it matches the 2026-09-26 run only if that run's retained record carries the same\n`prompts_sha256`. Treat parity as unverified until that record is registered and compared.",
   "new": "The prompt templates are the only part with a retained comparison to the prototype. Until the 2026-09-27 template edits (#385),\nthis package's templates filled with the run's values gave `PROMPTS_SHA256_20260926` in the tests (a local check),\nand the run's registered record, `landscape-sweep-20260926` in `catalogs/saturation/ledger.json`, carries the same\n`prompts_sha256`. On 2026-09-26 three unretained local checks were run (prompt bytes, the smoke's conversion,\n`usage_record.py` on the smoke's transcripts); their outputs are not kept, so they are not evidence, and parity of\nthe smoke's conversion and of `usage_record.py` stays unverified."
  },
  {
   "file": "evidence/artifacts/landscape-sweep-20260926/README.md",
   "old": "prototype's staged templates. The packaged templates, filled with this run's values, give the same hash (a local check\nin `tests/test_landscape_sweep_harness.py`). The packaged tools produced the returns, lanes, layers, usage records,",
   "new": "prototype's staged templates. The packaged templates, filled with this run's values, gave the same hash until the\n2026-09-27 template edits (#385), a local check whose value `tests/test_landscape_sweep_harness.py` keeps as\n`PROMPTS_SHA256_20260926`. The packaged tools produced the returns, lanes, layers, usage records,"
  }
 ],
 "unchanged": "catalogs/saturation/ledger.json:2846 and the lane-limit text in evidence/artifacts/landscape-sweep-20260926/lanes.json and catalogs/sota-convergence/manifest-20260926.json are dated run records and stay as written (the ledger chain and manifest_sha256 pin the ledger note and the manifest)."
}
```

Reasons: The diagnosis is right: the test now pins PROMPTS_SHA256_CURRENT (f64eec22...), while README:193-195 still says the templates give 3adfbed7...18d4 (tested). Replacement 1 of the proposal is kept unchanged. Replacement 2 needs three fixes. (1) The registered record is the ledger entry landscape-sweep-20260926 (catalogs/saturation/ledger.json:2839), not the evidence README. (2) Keeping the lead sentence 'Parity with the prototype is not established by this package.' beside a new claim that the templates matched contradicts it, so the paragraph is replaced whole. (3) The evidence classes stay distinct: the pre-#385 hash computation is a local check, and the ledger record carrying the same prompts_sha256 is the run's evidence. The unretained checks stay 'not evidence'. The evidence README cited by the proposal (lines 18-19) makes the same stale present-tense claim ('give the same hash'), so leaving it would contradict the corrected README; it gets replacement 3. The ledger note (2846) and the lane-limit text in lanes.json and manifest-20260926.json are dated run records and stay. Each old string occurs exactly once (checked).

Sources:
- `tools/sota-convergence/landscape-sweep/README.md:194`: "templates here give `3adfbed7…18d4` (tested), the value computed on 2026-09-26 from that run's staged"
- `tests/test_landscape_sweep_harness.py:45`: "PROMPTS_SHA256_CURRENT = \"f64eec22f82355b18854be9c05c4eba0fdbaf6b6732296fc18c2fae0ff5daf8d\""
- `catalogs/saturation/ledger.json:2839`: "\"prompts_sha256\": \"3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4\","
- `catalogs/saturation/ledger.json:2846`: "prompts_sha256 is the prototype's prompts_sha256.txt, which the packaged templates reproduce."
- `evidence/artifacts/landscape-sweep-20260926/README.md:18-19`: "The packaged templates, filled with this run's values, give the same hash (a local check\nin `tests/test_landscape_sweep_harness.py`)."
- `tools/sota-convergence/landscape-sweep/README.md:435`: "Parity with the prototype is not established by this package."

## Return B

Verdict: agree

Effective resolution: Agrees with the packet's proposed resolution for this item, exactly as written in the item above.

Reasons: Recomputation confirms the current f64eec22…daf8d hash and the pre-#385 package's historical 3adfbed7…18d4 hash. The latter matches the registered ledger record. The replacement correctly separates the changing local check, historical run evidence and unretained parity checks.

Sources:
- `tests/test_landscape_sweep_harness.py:45`: "PROMPTS_SHA256_CURRENT = \"f64eec22f82355b18854be9c05c4eba0fdbaf6b6732296fc18c2fae0ff5daf8d\""
- `tests/test_landscape_sweep_harness.py:48`: "PROMPTS_SHA256_20260926 = \"3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4\""
- `catalogs/saturation/ledger.json:2839`: "\"prompts_sha256\": \"3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4\""
- `tools/sota-convergence/landscape-sweep/README.md:435-437`: "On 2026-09-26 three unretained local checks were\nrun (prompt bytes, the smoke's conversion, `usage_record.py` on the smoke's transcripts); their outputs are not\nkept, so they are not evidence."

---

# Unit X9

## X9: CLAUDE.md tells the model to run built-in slash commands it cannot invoke

Location: CLAUDE.md:3-4

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`CLAUDE.md:1-4`
```
   1: @AGENTS.md
   2: 
   3: Inspect native loaded tools with `/mcp` and loaded context with `/context` before
   4: claiming a plugin is active.
```
git blame `CLAUDE.md:3-4`: 231f2ab7 2026-09-26 "Harness rules cleanup: one statement per rule, token practice as the base layer "
Installed client evidence (Claude Code 2.1.283, the Skill tool's own description): "Only names from the listing (or that the user typed explicitly) are valid. Built-in CLI commands (/help, /clear, …) aren't skills." MCP tools may be deferred: their names are listed and ToolSearch loads a schema.
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "CLAUDE.md",
 "old": "Inspect native loaded tools with `/mcp` and loaded context with `/context` before\nclaiming a plugin is active.",
 "new": "Before claiming a plugin or MCP server is active, confirm that its tools are among your\navailable or deferred tools (ToolSearch loads a deferred one). `/mcp` and `/context` are user\ncommands: ask the user to run them when your tool list cannot settle it."
}
```
### Constraints
- CLAUDE.md line 1 `@AGENTS.md` stays.

## Return A

Verdict: amend

Effective resolution: Replacement (verbatim):

```text
{
 "file": "CLAUDE.md",
 "old": "Inspect native loaded tools with `/mcp` and loaded context with `/context` before\nclaiming a plugin is active.",
 "new": "Before claiming a plugin or MCP server is active, confirm that its tools, skills or hook output are\npresent in this session (ToolSearch loads a deferred tool). `/mcp` and `/context` are user-typed commands:\nwhen your session cannot settle the claim, report it as unconfirmed and name the command that would."
}
```

Reasons: The diagnosis stands. The repository's own recipe and closure record treat /context and /mcp as commands run in the interactive client, and the commands reference presents commands as typed at the start of the user's message. The installed client's Skill description (quoted in the packet) excludes built-in CLI commands, apart from a few the skills page names, such as /init and /security-review. sources.json records not_found for an explicit statement about /mcp or /context, so this rests on the client text and the repository records, not on a docs statement. The proposed fallback 'ask the user to run them' can stall headless or workflow runs, which load CLAUDE.md but have no user to answer. It also conflicts with AGENTS.md:15, which limits stopping to sign-in, OS consent or an unresolved decision. The amendment reports the claim as unconfirmed and names the command instead. It also counts skills and hook output, since a plugin can be active without tools. It stays three lines, line 1 '@AGENTS.md' stays, the old text occurs once, and no test pins it.

Sources:
- `CLAUDE.md:3-4`: "Inspect native loaded tools with `/mcp` and loaded context with `/context` before\nclaiming a plugin is active."
- `recipes/claude-native-profile.md:272-273`: "Inside an authenticated interactive Claude session, use `/context all`, `/mcp`\nand `/usage` to inspect loaded context, connections and usage."
- `docs/foundation-closure-20260921.md:110-111`: "`/context all`, `/context`,\n`/usage` and `/mcp` ran in the interactive client, not as headless model prompts."
- `https://code.claude.com/docs/en/commands.md (sources.json S6)`: "A command is only recognized at the start of your message. Text that follows the command name becomes its arguments."
- `https://code.claude.com/docs/en/skills.md (sources.json S7)`: "A few built-in commands are also available through the Skill tool, including `/init` and `/security-review`. Other built-in commands such as `/compact` are not."
- `AGENTS.md:15`: "Stop only for necessary native sign-in, operating system consent or an unresolved material decision, and continue independent work."

## Return B

Verdict: amend

Effective resolution: Replacement (verbatim):

```text
Before claiming a plugin or MCP server is active, verify the relevant component in this
session: tools (including deferred tools via ToolSearch), skills, agents or hooks.
Distinguish listed availability from successful execution. Use available read-only
diagnostics first; if the claim remains unresolved, ask for the relevant `/plugin`,
`/mcp` or `/context` output. Invoke a command through Skill only if the installed
client exposes it there.
```

Reasons: The original needs an actionable verification path, but tool presence is not a universal plugin test: plugins can contain skills, agents or hooks. Also, some built-in commands are model-invocable through Skill. The amendment verifies the claimed component, distinguishes availability from operation, and makes user diagnostics a conditional fallback.

Sources:
- `CLAUDE.md:3-4`: "Inspect native loaded tools with `/mcp` and loaded context with `/context` before\nclaiming a plugin is active."
- `[Claude Code plugins overview](https://code.claude.com/docs/en/plugins)`: "A Claude Code plugin is a directory of skills, agents, hooks, MCP servers, or other components"
- `[Claude Code skills](https://code.claude.com/docs/en/skills)`: "A few built-in commands are also available through the Skill tool, including `/init` and `/security-review`."
- `[Claude Code MCP documentation](https://code.claude.com/docs/en/mcp)`: "MCP tools are deferred and discovered on demand."

---

# Unit N3

## N3: Anti-pattern log rows for the mistakes this audit proved

Location: docs/harness-defaults.md anti-pattern table

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`docs/harness-defaults.md:79-81`
```
  79: ### Record a correction the same turn
  80: 
  81: When a claim or action proves wrong, correct it where it was relayed and record the correction with its verification path in durable memory: the client's own memory and, where the host adopted one, the project's shared memory that other clients read. When the lesson is general engineering, add a row below that names the check preventing a repeat and where it is enforced (a test, CI job, hook or rule text; "this log" when nothing enforces it yet), and name a check there only after seeing it fail on that mistake or a reproduction of it. The portable instructions name no log file, because they load in every project: each project declares its own log in its instructions, as this repository's `AGENTS.md` declares this one. When the mistake came from repository text, fix that text. Rows cite repository evidence or upstream sources and keep host paths, host identities and credentials out.
```
`tests/test_adoption_docs_consistency.py:786-794`
```
 786: class UpstreamVerificationSectionTests(unittest.TestCase):
 787:     """The harness defaults carry the long form of the top rule's upstream-verification procedure
 788:     and a dated anti-pattern log, and the always-loaded AGENTS.md points to that section. Each log
 789:     row records the date, the anti-pattern, what happened, the rule or check that prevents it and
 790:     where that is enforced, so a mistake corrected in one session is not repeated in the next."""
 791: 
 792:     PAGE = ROOT / "docs/harness-defaults.md"
 793:     SECTION = "Upstream verification and compounding learning"
 794:     COLUMNS = ["Date", "Anti-pattern", "What happened", "Rule or check that prevents it", "Where enforced"]
```
Proposed rows (placed where the blank line was, among the 2026-09-27 rows):
```
| 2026-09-27 | Changing a rule in some co-loaded prompt templates but not all | #385 put the unknown-maintenance and license rules into the landscape sweep's `common` and `fit` templates, but the `facts` refuter, which receives `common` in the same prompt, kept "Default to refuted=true when uncertain" for unverifiable activity facts | When a rule changes, update every template that shares the prompt; the facts template states the rule | `tests/test_landscape_sweep_harness.py` (the facts-refuter rule test) |
| 2026-09-27 | Leaving a blank line inside a Markdown table | A blank line after the 2026-09-27 rows ended this log's table on GitHub, so every later row rendered as plain text; the shape test read only `|`-prefixed lines and passed | Keep a table's rows contiguous; GFM ends a table at the first empty line | `tests/test_adoption_docs_consistency.py` (the anti-pattern log check) |
| 2026-09-27 | Restating a linked rule without its scope | `AGENTS.md` required role dispatch for every workflow `agent()` stage, while the README section it links, from the same commit, exempts the saved scripts | Restate a linked rule with its scope, or link it without restating | this log |
| 2026-09-27 | Quoting a changing value as current in prose | The landscape-sweep README still called the 2026-09-26 prompt hash current after #385 changed the templates and the test's pin | Point at the pinned source of a changing value instead of quoting it | this log |
```
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "docs/harness-defaults.md",
 "rows": [
  "| 2026-09-27 | Changing a rule in some co-loaded prompt templates but not all | #385 put the unknown-maintenance and license rules into the landscape sweep's `common` and `fit` templates, but the `facts` refuter, which receives `common` in the same prompt, kept \"Default to refuted=true when uncertain\" for unverifiable activity facts | When a rule changes, update every template that shares the prompt; the facts template states the rule | `tests/test_landscape_sweep_harness.py` (the facts-refuter rule test) |",
  "| 2026-09-27 | Leaving a blank line inside a Markdown table | A blank line after the 2026-09-27 rows ended this log's table on GitHub, so every later row rendered as plain text; the shape test read only `|`-prefixed lines and passed | Keep a table's rows contiguous; GFM ends a table at the first empty line | `tests/test_adoption_docs_consistency.py` (the anti-pattern log check) |",
  "| 2026-09-27 | Restating a linked rule without its scope | `AGENTS.md` required role dispatch for every workflow `agent()` stage, while the README section it links, from the same commit, exempts the saved scripts | Restate a linked rule with its scope, or link it without restating | this log |",
  "| 2026-09-27 | Quoting a changing value as current in prose | The landscape-sweep README still called the 2026-09-26 prompt hash current after #385 changed the templates and the test's pin | Point at the pinned source of a changing value instead of quoting it | this log |"
 ],
 "note": "The first two rows name checks that are seen failing on the base before they pass; the last two name 'this log'."
}
```
### Constraints
- Rows follow docs/harness-defaults.md:81 and the shape check (dates, five non-empty cells, escaped pipes).

## Return A

Verdict: amend

Effective resolution: Replacement (verbatim):

```text
| 2026-09-27 | Changing a rule in some co-loaded prompt templates but not all | #385 put the unknown-maintenance and license rules into the landscape sweep's `common` and `fit` templates, but the `facts` refuter, which receives `common` in the same prompt, kept "Default to refuted=true when uncertain" for unverifiable activity facts | When a rule changes, update every template that shares the prompt; the facts template states the rule | `tests/test_landscape_sweep_harness.py` (the facts-refuter rule test) |
| 2026-09-27 | Leaving a blank line inside a Markdown table | A blank line after the 2026-09-27 rows ended this log's table on GitHub, so every later row rendered as plain text; the shape test read only `\|`-prefixed lines and passed | Keep a table's rows contiguous; GFM ends a table at the first empty line | `tests/test_adoption_docs_consistency.py` (the anti-pattern log check) |
| 2026-09-27 | Restating a linked rule without its scope | `AGENTS.md` required role dispatch for every workflow `agent()` stage, while the README section it links, from the same commit, exempts the saved scripts | Restate a linked rule with its scope, or link it without restating | this log |
| 2026-09-27 | Quoting a changing value as current in prose | The landscape-sweep README still called the 2026-09-26 prompt hash current after #385 changed the templates and the test's pin | Point at the pinned source of a changing value instead of quoting it | this log |
```

Reasons: Escape the pipe inside the second row's inline code. The proposed row produces six cells and fails log_errors; the escaped version passes. The substantive corrections are supported. Retain the requirement to observe the new checks failing on the mistakes before recording them as enforcement.

Sources:
- `tests/test_adoption_docs_consistency.py:820-823`: "for number, line in enumerate(rows[2:], 1):\n            cells = cls.cells(line)\n            if len(cells) != len(cls.COLUMNS) or not all(cells):\n                errors.append(f\"row {number} has {len(cells)} cells or an empty cell\")"
- `[GitHub Flavored Markdown, tables](https://github.github.com/gfm/#tables-extension-)`: "Include a pipe in a cell’s content by escaping it"
- `docs/harness-defaults.md:81`: "name a check there only after seeing it fail on that mistake or a reproduction of it"

## Return B

Verdict: amend

Effective resolution: Replacement (verbatim):

```text
{
 "file": "docs/harness-defaults.md",
 "placement": "in place of the blank line at line 92 (N2), between the 'Using strict config as a universal worker-profile validator' and 'Guessing version-specific CLI syntax or source paths' rows",
 "rows": [
  "| 2026-09-27 | Changing a rule in some co-loaded prompt templates but not all | #385 put the unknown-maintenance and license rules into the landscape sweep's `common` and `fit` templates, but the `facts` template, which the refuter receives with `common` and each proposal's `upstream_now`, still said \"Default to refuted=true when uncertain\" and counted a wrong license as a refuting fact. In the 2026-09-26 run the facts refuter refuted proposals whose `upstream_now` fields were null, which the discover template allows (\"null when unknowable\"; `evidence/artifacts/landscape-sweep-20260926/returns.json`, anomalyco/opencode and alpacahq/cli) | When a rule changes, update every template that shares the prompt; the facts template states the unknown-field, maintenance and license exceptions | `tests/test_landscape_sweep_harness.py` (the facts-refuter rule test) |",
  "| 2026-09-27 | Leaving a blank line inside a Markdown table | A blank line after the fifth 2026-09-27 row ended this log's table, since GFM 0.29-gfm 4.10 says \"The table is broken at the first empty line\", so every row after it fell outside the table; the shape test read only lines that start with a pipe and passed | Keep a table's rows contiguous from the header to the last row | `tests/test_adoption_docs_consistency.py` (the anti-pattern log check) |",
  "| 2026-09-27 | Restating a linked rule without its scope | `AGENTS.md` required role dispatch for every workflow `agent()` stage, while the Workflow contract of the README it links (`examples/claude-native/workflows/README.md`, its Dispatch by role bullet, from the same commit) exempts the vendored saved scripts | Restate a linked rule with its scope, or link it without restating | This log |",
  "| 2026-09-27 | Quoting a changing value as current in prose | The landscape-sweep README and the 2026-09-26 run's evidence README still said the packaged templates give the 2026-09-26 prompt hash after #385 changed the templates and the test's pin | Point at the pinned source of a changing value instead of quoting it | This log |"
 ]
}
```

Reasons: Four defects. (1) Row 2 contains an unescaped pipe inside backticks ('`|`-prefixed'). The shape check splits it into 6 cells (checked), so test_the_anti_pattern_log_has_the_columns_and_dated_rows fails, and GFM splits the cell as well. The amended row says 'lines that start with a pipe'. (2) Row 3 says the README section AGENTS.md links exempts the saved scripts. The linked section (#dispatch-by-role-2026-09-26, README:227-241) has no such exemption; it is in the Workflow contract's Dispatch by role bullet (README:219). (3) Row 2 places the blank line 'after the 2026-09-27 rows', but it follows the fifth of seven 2026-09-27 rows at the top of the table. It also asserts GitHub rendering that was not observed, so the amended row cites GFM 4.10 instead. (4) Rows 1 and 4 are aligned with the F3/X7 and N1 amendments: row 1 covers license and null fields and cites the retained returns, and row 4 names the evidence README. All four amended rows parse to 5 non-empty cells with valid dates, and after N2 the table has no gap (checked). The first two rows still name checks that must be seen failing on base (harness-defaults:81).

Sources:
- `tests/test_adoption_docs_consistency.py:802`: "return [cell.strip() for cell in re.split(r\"(?<!\\\\)\\|\", row)]"
- `tests/test_adoption_docs_consistency.py:822-823`: "if len(cells) != len(cls.COLUMNS) or not all(cells):\n                errors.append(f\"row {number} has {len(cells)} cells or an empty cell\")"
- `examples/claude-native/workflows/README.md:229`: "a stage no role fits runs as the default child with a `// dispatch: <reason>` comment beside the call."
- `examples/claude-native/workflows/README.md:219`: "- **Dispatch by role.** Every new or ad-hoc `agent()` stage names the `agentType` of its role in [the role table](#dispatch-by-role-2026-09-26)"
- `docs/harness-defaults.md:81`: "name a check there only after seeing it fail on that mistake or a reproduction of it"
