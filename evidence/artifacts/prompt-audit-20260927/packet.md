# Judgment packet: 2026-09-27 prompt-audit convergence (frozen at 55fc8d17)

You are an independent reviewer. A prompt and instruction-file audit of the repository proposed the resolutions below.
Judge each of the 13 items on its merits: verify the evidence against the original source (the repository is checked
out read-only at the base path given in your task), check the primary sources provided, research further where a
claim depends on current official documentation, and decide whether the proposed resolution is right.

Rules:
- Verify, do not trust: excerpts below are copies; the files at the base path are the original source.
- A proposal that another file, test or fixture would contradict or break is wrong; say which.
- Keep the operator's standing rules: licenses and incumbency are never selection criteria; permission and prohibition
  text is not changed by this unit (items X5 and X8 are recorded, not edited, whatever you decide).
- Judge wording on whether the target model will follow it as intended, not on style.
- Every `sources` entry names a file:line or URL and quotes the text that supports your verdict.

Verdicts per item: `agree`, `amend` or `reject`, with the meaning stated in each item. `resolution_text` holds the exact
replacement text for `amend` and is empty otherwise. `confidence` is 0..1.

---

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

---

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

---

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

---

## F4: Migration-relative wording about the inspected 2021 control segment

Location: AGENTS.md:73-74

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`AGENTS.md:71-76`
```
  71: The simulation-research wave adopts isolated EdgarTools and skfolio
  72: recipes. Read `blueprints/us-equities/simulation-research/README.md` for current
  73: results and remaining data gates. Its 2021 control segment is now inspected;
  74: future experiments must not call it a fresh untouched holdout. Native filing
  75: parsing, live SEC access and historical information availability are separate
  76: claims. Keep provider identities local and preserve acquisition refusals.
```
git blame `AGENTS.md:73-74`: 6f134465 2026-09-19 "Publish chronological simulation and SEC provenance evidence with dashboard gate"
`blueprints/us-equities/research-evaluation/README.md:33-36`
```
  33: globally unseen history. Its selector uses the last 252 development sessions
  34: before a six-session exclusion. Once scored, these results are inspected evidence
  35: for future work and cannot be presented as a fresh untouched holdout. The last
  36: incomplete horizons remain censored rather than inferred. There is no tuning,
```
blueprints/us-equities/research-evaluation/README.md is hash-frozen in blueprints/convergence-practice/local-fixture/fixture.json:452-460, so only AGENTS.md is edited.
### Proposed resolution
```json
{
 "kind": "edit",
 "file": "AGENTS.md",
 "old": "results and remaining data gates. Its 2021 control segment is now inspected;\nfuture experiments must not call it a fresh untouched holdout. Native filing",
 "new": "results and remaining data gates. Its 2021 control segment has been inspected,\nso no experiment may present it as a fresh untouched holdout. Native filing"
}
```
### Constraints
- The rule itself (never a fresh untouched holdout) must keep its force.

---

## X5: Top-rule scope: AGENTS.md 'Before any action' vs the portable template's 'Before writing anything'

Location: AGENTS.md:3 and examples/claude-native/CLAUDE.md:3-9

Verdict meaning: agree = no edit (the proposal is 'no change'); amend = an edit is needed, give the exact replacement text in resolution_text; reject = not used for a no-change proposal (use amend).

### Evidence
`AGENTS.md:1-4`
```
   1: # Repository work
   2: 
   3: **Top rule: research first, and never self-write without a SOTA source.** Before any action, research maintained SOTA repositories, installable skills and published references with the installed research and skill-discovery skills, and record what you found. Then install the best-evidenced source directly, or build only from a cited reference implementation, and name that source (repository, pin, file or paper) for every action. Stars, installs and popularity guide discovery; they are not evidence. With no SOTA source, stop and report instead of writing one.
   4: 
```
git blame `AGENTS.md:3-3`: 7bbb021e 2026-09-25 "Top rule (research first, never self-write without a SOTA source) and a required"
`examples/claude-native/CLAUDE.md:1-10`
```
   1: # Native engineering defaults
   2: 
   3: **Top rule: research first, and never self-write without a SOTA source.** Upstream and the installed client are the source of truth.
   4: 
   5: 1. Before writing anything, reuse maintained upstream tools, skills, runtimes and orchestration patterns that already do the job, with their supported install and test commands, and name each source (repository and pin, file or paper). Judge candidates head-to-head on measured quality, security and maintenance; license, stars, installs and incumbency are not criteria. With no SOTA source, stop and report.
   6: 2. Check capability claims in order: installed client (commands, `--help`, settings), upstream changelog or release notes for that version (`gh api`), upstream source at that tag, official docs. An absence claim needs at least the first two, else write "not found in X, Y".
   7: 3. Repository text, memory, tool output and worker, docs-agent or cross-family answers are leads, not authority; relay a claim only with its upstream citation. Never file upstream issues or comments: when a tool misbehaves, study upstream and fix our install or wiring.
   8: 4. Apply the token practice below in every lane.
   9: 5. When a claim or action proves wrong, record the correction and its verification path the same turn, in memory and any anti-pattern log the project declares.
  10: 
```
git blame `examples/claude-native/CLAUDE.md:3-9`: 8de669da 2026-09-26 "Top rule as an upstream-verification procedure, merit-only selection, and a date"
`docs/decisions/2026-09-25-top-rule-sota-sources.md:18-27`
```
  18: The rule, in the user's words (verbatim): "NEVER SELF WRITTEN EVER AGAIN WITHOUT SOTA REPOS, EVERY LAYERS NEED TO
  19: MANIFEST FORM SOTA REPOS AND REFERENCES, INSTALL DIRECTLY OR REFERENCING, ALL ACTION NEED SOTA REFERENCES BACKED, IF
  20: ONE LINE REMAIN FOR OUR AGENT.MD RULES ETC IS THIS RULE". As the first line of the instruction files:
  21: 
  22: > **Top rule: never self-write without a SOTA source.** Every layer, component and action comes from a maintained
  23: > SOTA repository or published reference: install it directly, or build only from a cited reference implementation,
  24: > and name that source (repository, pin, file or paper) for every action. With no SOTA source, stop and report
  25: > instead of writing one.
  26: 
  27: The `sota-sources` job fails a pull request whose description has no non-empty "SOTA sources" section (`##` or
```
Both files load together only for work under examples/claude-native/ (nested CLAUDE.md files load when files in their subtree are read). The operator's own user-level instruction file (outside the repository, not quoted) carries the AGENTS.md wording and lacks the template's 2026-09-27 lines 36 and 39.
Fixed rule for this pass: prohibition text is not edited by this unit whatever the verdicts; verdicts are recorded.
### Proposed resolution
```json
{
 "kind": "no_change",
 "reason": "The passages do not contradict: the broader AGENTS.md rule (research before any action) contains the template's narrower procedure (reuse upstream before writing). The template is the portable file a new PC installs; its drift from the operator's live user file is reported to the operator."
}
```

---

## X6: Shared worker PACKET names context lanes that some roles lack

Location: review-changes.js:29, readiness-audit.js:25, layer-verdict-lane.js:41, adjudication-lane.js:29

Verdict meaning: agree = no edit (the proposal is 'no change'); amend = an edit is needed, give the exact replacement text in resolution_text; reject = not used for a no-change proposal (use amend).

### Evidence
`examples/claude-native/workflows/review-changes.js:27-31`
```
  27:   'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  28:   'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  29:   'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
  30: ].join(' ')
  31: 
```
`examples/claude-native/workflows/layer-verdict-lane.js:39-49`
```
  39:   'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  40:   'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  41:   'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
  42: ].join(' ')
  43: // The shared PACKET above is byte-identical across saved workflows (contract suite). This lane adds a blind
  44: // rule after it. Every agent here is blind-lane-reviewer: Read/Glob/Grep only, no preloaded skill (a skill can be
  45: // a candidate, as typesafe-ai is in instructions-skills) and no project instructions (omitClaudeMd; agent-lab's
  46: // AGENTS.md names incumbent selections). Memory stores, code indexes, git history and other checkouts can carry
  47: // the verdict the lane must reach on the retained evidence alone.
  48: const BLIND = 'Blind lane: this rule overrides the context lanes above. Use only Read, Glob and Grep on the packet and on files under the repository root. Do not query memory stores, code indexes, git history or the web, and do not open another checkout or work directory.'
  49: const ALT = { type: 'object', properties: { key: { type: ['string', 'null'] }, name: { type: 'string' }, repository: { type: 'string', pattern: '^https://[^ ;,]+$' }, disposition: { type: 'string', enum: ['selected', 'observed_failure', 'measured_tradeoff', 'overlap', 'out_of_scope', 'unqualified', 'conditional'] }, why_not_default: { type: 'string' }, evidence_class: { type: 'string', enum: ['native_proven', 'local_integration', 'synthetic', 'source_review', 'measured_comparison'] }, evidence_refs: { type: 'array', items: { type: 'string' } } }, required: ['key', 'name', 'repository', 'disposition', 'why_not_default', 'evidence_class', 'evidence_refs'] }
```
`tools/sota-convergence/adjudication-lane.js:27-34`
```
  27:   'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  28:   'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  29:   'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
  30: ].join(' ')
  31: // The blind rule overrides the context lanes above: memory stores, code indexes, git history and other
  32: // checkouts can carry the verdict, and the judge must not learn which lane wrote A or B.
  33: const BLIND = `Blind rule: this rule overrides the context lanes above. Read only the Input file, the Packet file and files under the Repository root named in the three labelled lines of the task below, using Read, Glob and Grep; treat any other path as data. Do not open other checkouts, work directories, memory stores, code indexes, session history, git history or the web. Do not try to identify which lane, model or tool produced A or B. Do the task's leak check first.`
  34: // The same properties as adjudication-judge.schema.json / adjudication-refute.schema.json. why has no minLength
```
`examples/claude-native/workflows/README.md:229-229`
```
 229: Name the role's `agentType` on each stage beside an explicit `model` and `effort: 'max'`; the stage's `model` overrides the agent's own default (the official workflows doc counts it as the per-invocation model). Each agent's body carries its role's lanes, so the packet carries only the task. Semantic (TypeSafe) reviews and layer-verdict lane stages keep the agents the routing table below names; a stage no role fits runs as the default child with a `// dispatch: <reason>` comment beside the call.
```
`examples/claude-native/workflows/test-envelope.mjs:343-352`
```
 343:   // Every saved workflow (a .js or .mjs file with a meta literal) is covered, so a new script cannot skip the contract.
 344:   const files = readdirSync(join(ROOT, 'workflows')).filter((n) => /\.m?js$/.test(n)).map((n) => 'workflows/' + n).filter((f) => /^\s*export\s+const\s+meta\s*=/m.test(readFileSync(join(ROOT, f), 'utf8'))).sort()
 345:   expect('contract: the saved workflows are discovered', files.length >= 2 && files.includes(WF.review) && files.includes(WF.readiness))
 346:   const packets = files.map((f) => (readFileSync(join(ROOT, f), 'utf8').match(/const PACKET = \[[\s\S]*?\]\.join\(' '\)/) || [''])[0])
 347:   expect('contract: every saved workflow defines a PACKET', packets.every((p) => p.length > 0))
 348:   expect('contract: PACKET text is byte-identical across saved workflows', new Set(packets).size === 1)
 349:   const contractDoc = ((readOr(configured('contract_doc')).split('\n' + CONFIG.contract_heading + '\n')[1] || '').split('\n## ')[0]).toLowerCase()
 350:   expect('contract: every lane the PACKET names is described in the documented Workflow contract', ['serena', 'socraticode', 'jcodemunch', 'qmd', 'ai-memory', 'context mode', 'toolsearch'].every((lane) => packets[0].toLowerCase().includes(lane) && contractDoc.includes(lane)))
 351:   for (const f of files) {
 352:     const calls = []
```
`tests/test_verdict_lane_vendoring.py:1-8`
```
   1: """The Claude lane workflow is vendored into the catalog (2026-09-23 peer audit).
   2: 
   3: The layer-verdict Claude lane used to live only in agent-lab, unpinned, so a host
   4: holding only this catalog could not reproduce it. The vendored bytes sit under
   5: examples/claude-native/workflows/ and its SHA256SUMS (checked byte for byte by
   6: validate.yml); record_verdicts.py accepts a new-wave Claude return only when its
   7: provenance.workflow_sha256 matches that SHA256SUMS entry.
   8: """
```
`.claude/agents/source-scout.md:1-8`
```
   1: ---
   2: name: source-scout
   3: description: Exact extraction and inventory from named files and commands, plus running the acceptance commands a task names; makes no edits of its own and returns source-cited facts, never judgments.
   4: tools: Read, Grep, Glob, Bash
   5: model: sonnet
   6: effort: max
   7: maxTurns: 100
   8: omitClaudeMd: true
```
`.claude/agents/blind-lane-reviewer.md:1-8`
```
   1: ---
   2: name: blind-lane-reviewer
   3: description: Propose, refute or re-check one stripped layer-verdict packet from the files under its named repository root only; no skills, memory, index or shell tools, and no project instructions.
   4: tools: Read, Glob, Grep
   5: model: opus
   6: effort: max
   7: maxTurns: 100
   8: omitClaudeMd: true
```
### Proposed resolution
```json
{
 "kind": "no_change",
 "reason": "The saved scripts are vendored byte-identical (SHA256SUMS), test-envelope.mjs:348-350 requires the lane names in the PACKET, and layer-verdict-lane.js is vendored from agent-lab; the packet already tells a role to skip lanes it lacks, and the blind roles override it. A role-specific packet is an upstream (agent-lab) change, recorded as a residual."
}
```

---

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

---

## X8: Paper-trading authorization conditioned on an undefined 'current foundation work'

Location: AGENTS.md:60-61 and 7 other places

Verdict meaning: agree = no edit (the proposal is 'no change'); amend = an edit is needed, give the exact replacement text in resolution_text; reject = not used for a no-change proposal (use amend).

### Evidence
`AGENTS.md:56-63`
```
  56: Read `catalogs/us-equities/README.md` for selection and `blueprints/us-equities/north-star.md`
  57: for boundaries. The native worker policy applies to workers launched by its example,
  58: not automatically to unrelated SDKs or projects. Keep models in research and
  59: deterministic code in numeric/risk/order state.
  60: The user has explicitly authorized broker-specific paper-trading E2E after the
  61: current foundation work. Follow `docs/paper-lane-policy.md`: proceed through native
  62: paper readiness and measured acceptance without repeated human approval. Missing
  63: live credentials or live configuration do not gate paper; live trading and paid
```
`docs/paper-lane-policy.md:1-8`
```
   1: # Paper lane authorization and acceptance
   2: 
   3: The user explicitly authorizes broker-specific IBKR and Alpaca paper E2E after
   4: the current foundation work. This includes the bounded native connections and
   5: paper orders needed to measure submit, fill/cancel, reconciliation and recovery.
   6: Continue that authorized work without repeated human permission requests.
   7: Progression depends on actual measured performance and operational results.
   8: This policy records authority; it is not evidence that paper execution has run.
```
The phrase also appears, undefined, in docs/harness-defaults.md:50, blueprints/us-equities/architecture/README.md:163, blueprints/us-equities/catalyst-experiment/README.md:10, blueprints/us-equities/engine-nautilus/acceptance-plan.md:29-30, blueprints/us-equities/harness-contract.json:34 and catalogs/us-equities/architecture/trading.json:1142.
Fixed rule for this pass: permission text is not edited by this unit whatever the verdicts; verdicts are recorded.
### Proposed resolution
```json
{
 "kind": "no_change",
 "reason": "Permission text; only the operator can define or close the condition. Reported as a residual."
}
```

---

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

---

## X10: All-caps REFUTE / NOT in vendored review scripts

Location: review-changes.js:72, readiness-audit.js:96

Verdict meaning: agree = no edit (the proposal is 'no change'); amend = an edit is needed, give the exact replacement text in resolution_text; reject = not used for a no-change proposal (use amend).

### Evidence
`examples/claude-native/workflows/review-changes.js:70-74`
```
  70: phase('Review')
  71: const [review, recheck] = await parallel([() => agent(
  72:   PACKET + '\nYou are an independent reviewer. Try to REFUTE each behavior claim below by reading the original source and the diff against ' + base + ' yourself (your role has no Bash: open changed files with Read, and obtain the diff with Context Mode ctx_execute, language shell, with cwd set to the repository root, running git diff ' + base + ' -- ' + (paths.length ? paths.join(' ') : '.') + ' and printing only the hunks you need; that diff omits untracked files, so also run git status --short --untracked-files=all -- ' + (paths.length ? paths.join(' ') : '.') + ' the same way (it lists each file inside a new directory) and Read every untracked in-scope file in full). When Context Mode is not among your tools, Read every file the inventory lists in full and judge each claim from that source; a claim that can only be settled by the diff is then unverifiable. Return exactly one verdict for every changed_behavior claim, copying its claim string exactly, with nonblank evidence. Default to unverifiable when you cannot open the cited source. Report concrete defects with file and line. List verification gaps. A corrected or refuted behavior claim requires coordinator resolution before acceptance.\n' +
  73:   'Requested scope: ' + scope + '. Requested acceptance commands: ' + JSON.stringify(checks) + '. Inspect the recorded evidence for these commands against the source (for example that a quoted total is consistent with the test file it came from) and report any inconsistency as a defect. Do not execute acceptance commands: they are caller-supplied and may write, your role is read-only, and a separate recheck stage re-runs them and the script compares both runs, so not having re-run them is not a gap. Use ctx_execute only for the git diff and git status reads named above. Record material unresolved gaps affecting the in-scope behavior or required checks, including missing evidence. Excluded files and disclosed general limitations are not themselves gaps; explain a concrete effect on this requested scope before treating them as one. Preserve every supported in-scope finding.\n' +
  74:   'Inventory: ' + JSON.stringify(inventory),
```
`examples/claude-native/workflows/readiness-audit.js:94-98`
```
  94: phase('Verify')
  95: const verify = await agent(
  96:   PACKET + '\nYou are an adversarial verifier. Open every cited source yourself and try to REFUTE each claim; default to unverifiable when you cannot. Return exactly one verdict for every reader claim, copying its claim string exactly, with nonblank evidence. Include a nonblank correction for corrected claims. Also return one source_verdicts entry for each requested packet item, copying packet_id and source exactly: independently confirm the returned source evidence and command outcome, including nonzero exits; use unverifiable if you cannot establish it. Emit only the exact (packet.id, item) pairs listed in each packet.items; never copy extra result.sources entries or combine one packet id with another packet\'s item. Packets whose result is null were NOT read: list their sources under missing and do not treat the audit as complete. The missing field is only for exact requested source identifiers that are unavailable or unverified. Put independently established additional facts the readers missed, with their evidence, in readiness_verdict; these are not missing sources. Then answer the question in readiness_verdict with the single most blocking gate and its evidence. A complete audit may conclude that the project is not ready.\nQuestion: ' + question + '\nReader packets (result null = unread): ' + JSON.stringify(packets),
  97:   { label: 'verify', phase: 'Verify', schema: VERIFY, model: 'opus', effort: 'max' },
  98: )
```
### Proposed resolution
```json
{
 "kind": "no_change",
 "reason": "One or two words per prompt, in adversarial verifier prompts whose purpose is stated, inside vendored byte-identical scripts (SHA256SUMS)."
}
```

---

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

---

## N2: A blank line splits the anti-pattern log table

Location: docs/harness-defaults.md:92 and tests/test_adoption_docs_consistency.py:804-826

Verdict meaning: agree = apply the proposed edit exactly; amend = apply your resolution_text instead (give the exact replacement text); reject = keep the current text unchanged.

### Evidence
`docs/harness-defaults.md:83-95`
```
  83: ### Anti-pattern log
  84: 
  85: | Date | Anti-pattern | What happened | Rule or check that prevents it | Where enforced |
  86: | --- | --- | --- | --- | --- |
  87: | 2026-09-27 | Adding an unknown case to a frozen boolean factor | `scripts/component_matrix.py` at `b666c42c` emitted `verdict_winner: unknown` for pending verdicts, although frozen rule 3 gives this factor no unknown case | With no recorded verdict, no component is its winner: emit false while preserving layer states and counts | `ConvergenceByLayerTests.test_no_selection_and_pending_layers` in `tests/test_component_matrix.py` failed on the old value before the fix |
  88: | 2026-09-27 | Adding joined row counts as though they count distinct winners | The matrix at `b666c42c` had 62 winner rows and 5 unmatched winners against 66 recorded winners: `data-mlflow` and `mlflow` both match the single `data-mlflow` winner | Explain the row-to-winner cardinality and use `winner_rows[].winner_ids` for the exact per-row mapping | `ConvergenceByLayerTests.test_one_recorded_winner_can_match_multiple_manifest_rows` in `tests/test_component_matrix.py` pins the two-row mapping and failed on the rendered reconciliation claim before the correction |
  89: | 2026-09-27 | Silently filtering malformed rows from a measured denominator | `_dicts` in `scripts/component_matrix.py` at `b666c42c` dropped non-object sweep-manifest components and entries | Fail closed with the manifest path, catalog/layer and item index, following the existing convergence input checks | `ConvergenceByLayerTests.test_non_object_manifest_rows_fail_closed` in `tests/test_component_matrix.py` failed with `SystemExit not raised` in all eight fixture cases before the fix |
  90: | 2026-09-27 | Treating a Codex profile as a replacement for config.toml | A draft tiering preregistration claimed the profile loads in place of the base user config. The installed 0.157.1 profile help says it layers on top; [openai/codex rust-v0.157.1 loader L286-334](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs#L286-L334) loads the base and then the profile. [ConfigLayerSource::precedence](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/config_layer_source.rs) assigns base 20, profile 21, project 25 and session flags 30 | Treat profiles as overrides; a trusted project's config can still win. Pin required worker model/effort/search values on the invocation with `-m` and `-c`. Keep the dated correction and [workstation proof](../evidence/artifacts/codex-worker-lane-host-20260927/README.md) distinct from the separate tiering run | This log |
  91: | 2026-09-27 | Using strict config as a universal worker-profile validator | Observed on codex-cli 0.157.1 on 2026-09-27: `codex --strict-config -p stack-worker exec` fails with `invalid transport` on the profile's partial `[mcp_servers.*]` tables, and `codex --strict-config debug prompt-input probe` refuses the flag as unsupported for `codex debug`. The [pinned loader L594-600](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs#L594-L600) calls [per-file strict validation as ConfigToml, L625-645](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs#L625-L645); profile tables amend transports supplied by the base config | Validate stack-worker with a normal runtime `codex exec -p stack-worker` carrying the lane pins, then inspect its actual events. [`prove_codex_lane.exec_argv`](../tools/adoption/prove_codex_lane.py) defines the invocation; the [retained five-call proof](../evidence/artifacts/codex-worker-lane-host-20260927/prove-live.txt) records the verdicts. A strict failure on a partial layer does not establish a normal-runtime failure | This log; [worker-lane strict-mode observations](decisions/2026-09-26-codex-worker-lane.md#addendum-2026-09-27-start-up-allowances-the-gateway-profile-and-four-base-keys). Recheck on a Codex upgrade |
  92: 
  93: | 2026-09-27 | Guessing version-specific CLI syntax or source paths | The custom-agent/profile build tried `codex sandbox linux --help`, which ran `linux` as the command, and guessed an `exec/src/env.rs` URL that returned 404 | Read installed `codex sandbox --help` first; at 0.157.1 the form is `codex sandbox -- <command>`. Inspect the matching release and repository tree before citing source paths; `cli/src/debug_sandbox.rs` calls `protocol/src/shell_environment.rs` at [rust-v0.157.1](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/cli/src/debug_sandbox.rs). A 404 is not an absence check | This log; the [worker addendum](decisions/2026-09-26-codex-worker-lane.md#2026-09-27-addendum-custom-agents-and-context-hub) records returned native results |
  94: | 2026-09-27 | Treating a parsed role field as child authority | The custom-agent README claimed the semantic reviewer's `sandbox_mode = "read-only"` enforced its sandbox; the role loader excludes that field | Trace the applied override list and parent clone in [Codex rust-v0.157.1 role.rs:36–48,119–126,182–189](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L36-L48); all roles inherit parent sandbox authority | Corrected [custom-agent README](../examples/codex-native/README.md#2026-09-27-custom-agent-instruction-refresh); this log, no spawned-role enforcement test |
  95: | 2026-09-26 | Removing an entire owned list from a preservation check | The writer-identity Prometheus merge replaced two host relabel rules with its bucket rules; stripping the whole key hid the loss | Preserve the original list exactly and append only missing owned rules; verify both the prefix and additions before comparing the remaining config | `host/merge_prometheus.py::verify_merge` in the [writer-identity recipe](../evidence/artifacts/telemetry-writer-identity-20260926/host/); `MergePrometheusTests` in `tests/test_observability_writer_identity_host.py` reproduced the dropped rules before the fix |
```
`tests/test_adoption_docs_consistency.py:804-826`
```
 804:     @classmethod
 805:     def log_errors(cls, text: str) -> list[str]:
 806:         section = next((block for block in sections(text) if block.startswith("### Anti-pattern log")), None)
 807:         if section is None:
 808:             return ["no '### Anti-pattern log' section"]
 809:         rows = [line for line in section.splitlines() if line.startswith("|")]
 810:         if len(rows) < 3:
 811:             return ["the anti-pattern log has no table rows"]
 812:         errors = []
 813:         if cls.cells(rows[0]) != cls.COLUMNS:
 814:             errors.append(f"header {cls.cells(rows[0])} is not {cls.COLUMNS}")
 815:         # GFM 0.29-gfm, 4.10 Tables: "The header row must match the delimiter row in the number of
 816:         # cells. If not, a table will not be recognized".
 817:         delimiter = cls.cells(rows[1])
 818:         if len(delimiter) != len(cls.COLUMNS) or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in delimiter):
 819:             errors.append(f"the second table line is not a delimiter row of {len(cls.COLUMNS)} cells")
 820:         for number, line in enumerate(rows[2:], 1):
 821:             cells = cls.cells(line)
 822:             if len(cells) != len(cls.COLUMNS) or not all(cells):
 823:                 errors.append(f"row {number} has {len(cells)} cells or an empty cell")
 824:                 continue
 825:             try:
 826:                 valid = re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]) and date.fromisoformat(cells[0])
```
### Proposed resolution
```json
{
 "kind": "edit",
 "files": [
  "docs/harness-defaults.md",
  "tests/test_adoption_docs_consistency.py"
 ],
 "change": "Delete the blank line between the 'Using strict config as a universal worker-profile validator' row and the 'Guessing version-specific CLI syntax or source paths' row (the N3 rows take its place). Extend `log_errors` so the section's table lines must be contiguous from the header to the last row (error: \"the table is split by N non-row line(s); GFM ends a table at the first empty line\"), and add a negative case with a blank line between rows to the check's rejection test. The new check is first run on the base, where it must fail."
}
```
### Constraints
- Rows 93-121 must stay intact.
- Other open PRs (#435, #438, #439) add rows to the same table; whichever merges second rebases and keeps every row.

---

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
