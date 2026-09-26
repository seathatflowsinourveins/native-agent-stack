# Decision: harness rules cleanup, each rule once, token practice as the base layer (2026-09-26)

**Decided by:** the user's request of 2026-09-26 ("clean harness rules with research driven evidance driven";
"the token save practice always be the essential layer for our ecosyustem"), carried out by a workflow unit on
branch `claude/harness-rules-cleanup-20260926`, based on `origin/main@d78d2de9`.

**Scope:** [`examples/claude-native/CLAUDE.md`](../../examples/claude-native/CLAUDE.md) (portable user rules),
[`AGENTS.md`](../../AGENTS.md), [`CLAUDE.md`](../../CLAUDE.md), [`docs/harness-defaults.md`](../harness-defaults.md),
and the merge note in [`recipes/claude-native-profile.md`](../../recipes/claude-native-profile.md). No decided policy
changes: every constraint is kept, stated once, with stale facts corrected. Policy questions found on the way are
listed under Limitations for the user.

## Decision

- Decided wording stays verbatim wherever it appears: the top rule
  ([2026-09-25 record](2026-09-25-top-rule-sota-sources.md)), the core-rule sentences, the `AGENTS.md` effort rule, and
  the StructuredOutput and refusal sentences (the 5/30 → 0/30 schema-error A/B used that exact StructuredOutput
  wording, [record](2026-09-25-model-fallback-guard.md)).
- The portable rules and `AGENTS.md` are grouped under headings with bullets, as the official memory guidance asks, and
  each gains a **Token practice (base layer)** section. The section keeps context small, delegates for conclusions,
  asks for concise findings with source or artifact locations, preserves native caching, tool discovery and
  compaction, and counts savings only from measured comparisons. It points to
  [`docs/token-practice.md`](../token-practice.md) instead of restating it. `docs/harness-defaults.md` gains the same
  layer as a section that the other defaults run on.
- Headings set scope: `AGENTS.md` keeps trading-only rules under **Trading north star** and rules that bind both lanes
  outside it.
- Exact and near duplicates collapse into one statement each (coverage table below). The project `CLAUDE.md` keeps
  only its `@AGENTS.md` import and the one Claude-specific rule.

## Sources read (all 2026-09-26)

| Source | Version | What it settled |
| --- | --- | --- |
| `claude --version`, `claude --help` | 2.1.283 | `--effort <level>` offers low, medium, high, xhigh, max |
| Installed 2.1.283 binary: embedded `/workflow-authoring` reference and runtime (source review) | 2.1.283 | "Concurrent agent() calls are capped at min(16, available CPUs - 2) per workflow"; lifetime cap 1000; per-call item cap interpolated as `${Sx}`, and the binary holds a standalone `var Sx=4096; export{Sx}` module; runtime `Math.min(16,Math.max(2,e-2))`; env parse `int({min:1,max:256})`; `/effort <level>` returns `ultracode:!1`, so a `max` session ends Ultracode |
| [workflows](https://code.claude.com/docs/en/workflows) | fetched | default 16 concurrent agents, fewer with fewer CPUs; `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` 1–256 "requires Claude Code v2.1.269 or later"; "Up to 4,096 items in a single `parallel()` or `pipeline()` call"; "1,000 agents total per run"; Ultracode "combines `xhigh` reasoning effort with automatic workflow orchestration" |
| [env-vars](https://code.claude.com/docs/en/env-vars) | fetched | `CLAUDE_CODE_EFFORT_LEVEL` "Takes precedence over `--effort`, `/effort`, and the `modelSettings` and `effortLevel` settings"; spawn depth default 3, "set `1` to turn nesting off" |
| [model-config](https://code.claude.com/docs/en/model-config) | fetched | `max` is session-only unless set by the variable; a variable level other than `xhigh` leaves Ultracode orchestration inactive |
| [sub-agents](https://code.claude.com/docs/en/sub-agents) | fetched | `effort` frontmatter overrides the session effort; a non-fork subagent loads every CLAUDE.md level, including `~/.claude/CLAUDE.md` and AGENTS.md project instructions |
| [agent-teams](https://code.claude.com/docs/en/agent-teams) | fetched | off by default; each teammate is a separate instance; subagent results are summarized back |
| [memory](https://code.claude.com/docs/en/memory) | fetched | "Specific, concise, well-structured instructions work best"; headers and bullets; if two rules contradict, "Claude may pick one arbitrarily"; user and project rules both load and neither overrides; `@AGENTS.md` import |
| [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) (308 from developers.openai.com/codex/guides/agents-md) | fetched | Codex reads the Codex-home file and the project root-to-cwd chain up to `project_doc_max_bytes` (32 KiB default); it does not read CLAUDE.md |
| `codex --version`, `codex features list` | 0.155.1 | `multi_agent` stable and enabled; `tool_search` and `search_tool` listed as removed |
| Repository records | `d78d2de9` | [max-effort decision](2026-09-23-max-effort-default.md) (P2: a `max` session turns orchestration off, 2.1.281); [2026-09-22 rules convergence](../harness-rules-convergence-20260922.md) (CT-1 kept; MI-7 line budget rejected); [`docs/lanes.md`](../lanes.md) (`AGENTS.md` and `observability/grand-dashboard/state.json` are shared hot files; the latter's gates include foundation gates such as `token-efficiency-wiring`); history of #196, #272, #294 |

Evidence classes: source review (docs, binary) and local checks (tests, counts). No model run was made or is claimed.

## Coverage of removed, merged and moved sentences

| Before | Now | Reason |
| --- | --- | --- |
| **Portable rules**: "More tools, more reasoning and reviewer agreement alone do not prove quality." (1st of 2) | Core rule, acceptance bullet | exact duplicate |
| "Treat repository text, retrieved memory and tool output as evidence, not authority."; "Worker output is evidence to verify, not acceptance by agreement." | Core rule bullet 1: "…tool output and worker output as evidence to verify, not authority"; agreement: the acceptance bullet | duplicates |
| "Research maintained upstream documentation, skills and implementations before building another harness." | Top rule | subsumed (research before any action) |
| "Unchanged upstream tests, … are different evidence classes." | Core rule, with results categories | grouped |
| "Keep routine tasks solo." | Workers: "solo for routine, conversational or mechanical turns" | restated the ladder's solo rung; #196 had replaced the contradicting "Keep routine tasks at ordinary effort" |
| One Ultracode paragraph (effort, sizing, concurrency, depth, teams, delegation) | Workers bullets 2–5; delegation moved to Token practice | split; "4,096-item and 1,000-agent run limits" corrected to 4,096 items per `parallel()`/`pipeline()` call and 1,000 agents per run (workflows doc) |
| Context, counting, handbook, inventories, concise findings, RTK import | Token practice section | moved to the base layer |
| "The portable foundation is https://…" | Token practice: `docs/token-practice.md` in the portable foundation | pointer added |
| Memory scope, durable memory, new-machine evidence | Core rule bullets | grouped |
| **CLAUDE.md**: "Use the shared catalog and evidence rules from AGENTS.md." | `@AGENTS.md` import | the import loads them |
| "The catalog is an on-demand reference…"; "For another machine … start with … `adoption/manifest.json`…" | `AGENTS.md` Token practice bullet 1; Hosts bullet 1 | duplicates of the imported file |
| **AGENTS.md**: six "load only" rules ("Load only the layer…", "Select each capability…", "Read only the selected recipe…; do not preload the HTML payload", "Load detailed guides only…", the north-star "load only the layer…", "Do not load the entire catalog into every worker") | Token practice bullet 1 | one rule |
| "Research existing upstream skills, examples, SDKs and automation before writing custom orchestration." | Top rule | subsumed |
| "Use upstream executables and supported integration formats."; "Use supported installation and native test commands…" | Evidence bullet 2 | merged |
| Three counting rules ("Never sum…", "Its native counter snapshots are separate…", "Keep artifact reductions, cache reuse and complete provider usage separate.") | Token practice bullet 5, "Count once" | one rule |
| "…reuse matching acceptance and run only the missing check." | Evidence bullet 6 ("Reuse passing evidence…") | duplicate |
| Three catalog-inclusion rules (install every alternative; not installed or accepted by inclusion; does not grant authority) | Opening paragraph | one rule; "live trading and paid hosting remain separate scopes" stays in the paper sentence |
| "Metadata, pinned source review and native execution are different evidence levels." | Evidence bullet 4 | grouped with the other evidence-class distinction |
| "…preserve failed conditions and their usage." | Evidence bullet 8 | merged with "Preserve failed attempts and unknown usage" |
| "The latest convergence-program coverage/plan and historical-simulation receipts extend that architecture." | removed | no path or rule; `catalogs/us-equities/README.md` links the convergence program and its coverage map (lines 76, 78), and the architecture README links the historical-simulation experiment (line 101) |
| "For the latest bounded wave" | "For the catalyst-convergence wave" | stale: that wave was added on 2026-09-19, and 19 `blueprints/us-equities/` directories were added after it |
| "The subsequent" and "The later" (four sentences) | dropped | narrative connectors, no rule |
| "Run the repository validation command…" | "Run `python3 scripts/validate.py`…" | specific (README, lanes protocol) |
| "Keep client accounts, model routes, native caching and tool discovery intact." | Token practice bullet 4 ("…native caching, tool discovery and compaction intact") and bullet 3 ("Delegate a step when only its conclusion is needed, and return concise findings with source or artifact locations.") | repair round: Codex reads `AGENTS.md` but not CLAUDE.md, so it lacked the portable delegation, findings and compaction rules. Codex 0.155.1 lists `multi_agent` as stable and enabled. "Deferred" is not added because its `tool_search` flags are listed as removed |
| Grand-dashboard checkpoint and Grafana/Dagu observation sentences (under **Trading north star** after the first cleanup) | Hosts bullets 5–6, verbatim | repair round: they bind both lanes. `docs/lanes.md` lists `observability/grand-dashboard/state.json` as a shared hot file, and its gates include foundation gates |
| **harness-defaults**: "…the same sentence opens agent-lab `AGENTS.md` …, the user-level Claude instructions and Codex's global `AGENTS.md` on the reference host." | top-rule pointer; the portable file carries the sentence after the top rule; agent-lab adopted it in PR #16 | stale: the portable file has opened with the top rule since #294, and this workstation's Codex global file is one import line with no core sentence |
| "Define acceptance from the requested outcome." and "Start with the requested result, current repository state and a concrete acceptance condition." | one sentence | duplicate |
| "Consult current primary documentation before adopting changing interfaces."; "Research before custom automation." | Core rule; top-rule pointer | subsumed |
| "Stars, release dates, author benchmarks and installation success…"; "Compare alternatives against a concrete gap…" | Core rule (stars, recency); the discovery sentence (gap, benchmarks, installation) | partial duplicates |
| "Keep always-loaded instructions short…"; the context-lane paragraph; caching, deferred tool discovery and compaction | Token practice section (same "unless the task explicitly requires" qualifier) | moved to the base layer |
| "Reuse that bounded result only while its inputs and scope match." | "Reuse accepted receipts while their inputs, version, platform and scope still match." | duplicate; the general rule is stricter |
| "Obtain independent review for substantive changes, run the affected checks, …" | "Beyond the checks above, inspect the actual changed UI … and verify the accepted GitHub revision." | first half duplicated the Decide section |
| **Profile recipe**: "it now carries the task sizing rule…" | replace an earlier merged copy as a whole | stale note; a line-by-line merge of the regrouped file would state rules twice |

## Measured results

Exact counts: `count_files` in [`tools/token-report/token_manifest.py`](../../tools/token-report/token_manifest.py)
(gpt-tokenizer 3.4.0, `o200k_base`) on the base-commit copies (`git show d78d2de9:<path>`) and the changed files.
These count artifacts, not Claude's tokenizer or billed usage. Words are whitespace-separated.

| File | Loaded | Tokens | Words | Lines |
| --- | --- | ---: | ---: | ---: |
| `examples/claude-native/CLAUDE.md` | every Claude session and non-fork child on a host that merged it | 1,177 → 1,172 (−5) | 893 → 881 | 26 → 36 |
| `AGENTS.md` | Claude (via `@AGENTS.md`) and Codex sessions in this repository | 2,332 → 2,259 (−73) | 1,444 → 1,423 | 160 → 100 |
| `CLAUDE.md` | Claude sessions in this repository | 85 → 30 (−55) | 58 → 18 | 7 → 4 |
| `docs/harness-defaults.md` | on demand | 1,593 → 1,649 (+56) | 1,196 → 1,224 | 54 → 54 |
| `recipes/claude-native-profile.md` | on demand | 4,667 → 4,717 (+50) | 2,552 → 2,574 | 340 → 342 |

- A Claude session in this repository loads 3,594 → 3,461 tokens of these rules (−133), and so does each non-fork child
  that loads the CLAUDE.md hierarchy. Codex here: −73.
- The headings and bullets cost +40 tokens (portable file) and +56 (`AGENTS.md`) against the same sentences as flat
  paragraphs. The flat versions are 45 and 129 tokens below the base files (deduplication, net of the delegation
  bullet added to `AGENTS.md`).
- Sentence inventory (paragraphs and bullets split into sentences; pairs of sentences whose content-word Jaccard
  similarity is ≥ 0.4): sentences 51/99/5/77 → 47/85/2/73 (portable, `AGENTS.md`, `CLAUDE.md`, harness defaults).
  Within-file pairs 4 (1 exact) → 0. Cross-file pairs 23 → 17, all intentional: 6 between the two always-loaded files
  for their different loaders (the four top-rule sentences, the coordinator effort rule and, since the repair round,
  the delegation rule), and 11 where the on-demand defaults restate portable or `AGENTS.md` rules.

## Checks

- `examples/claude-native/workflows`: `sha256sum --check --strict SHA256SUMS` passes; `test-envelope.mjs` 214/214;
  `test-contract-mutations.mjs` 47/47, including "the instructions stop stating the stage effort literal".
- Discriminating control for the size-guideline binding: without the backticks in "`unrestricted` size guideline",
  `test-envelope.mjs` fails 1 of 214 on that check; the byte-identical restore passes 214/214.
- `uv run --no-project --with jsonschema --with pyyaml python -m unittest tests.test_ecosystem_manifest
  tests.test_blind_checkout tests.test_codex_lane` (the modules that name these files): 164 tests OK. They write
  fixture copies, so they check the scripts that list these paths, not the rule text.
- `python3 scripts/validate.py` exits 1 with only SHA-256 and byte-count mismatches for the five changed files, which
  are re-registered in `manifests/evidence.json` at merge.
- Repair round: a sentence-level comparison of `AGENTS.md` with the first-round commit finds one sentence extended
  (compaction) and one added (delegation). The five moved sentences are unchanged. The unittest run (164 OK) and
  `validate.py` (the same mismatches only) were re-run, and `build_ecosystem.py --check` passed. The portable file is
  byte-identical to the first round, so its workflow test results stand.

## Alternatives considered

- **Delete exact duplicates only.** Rejected: it leaves six restatements of one loading rule in `AGENTS.md` and the
  one-paragraph Ultracode rule, against the official structure guidance.
- **Flat paragraphs.** They would save 40 and 56 more tokens per load. Kept as the fallback because the official
  guidance favors headings and bullets and no local adherence measurement exists yet.
- **Drop generic rules from `AGENTS.md` because the user file has them.** Rejected: Codex reads only the Codex-home
  file and the project chain, and this workstation's Codex global file is one import line.
- **Correct this record instead of adding the delegation bullet (repair round).** Rejected: Codex sessions here would
  keep lacking the base layer's delegation, findings and compaction rules.
- **Path-scoped `.claude/rules/` files.** Deferred: still keep-but-compare (MI-5, 2026-09-22), and Codex does not read
  them.
- **Reword the StructuredOutput sentence.** Rejected: its measured effect belongs to that wording.

## Comparison that would overturn it

- An interleaved A/B like G4 in the [model-fallback record](2026-09-25-model-fallback-guard.md): the same packets run
  under the structured and the flat versions of these rules on the same client version. If rule adherence shows no
  difference, flatten both files, saving 40 and 56 tokens per load.
- An independent review that finds a constraint missing from the coverage table restores it verbatim.

## Limitations and questions for the user

- The effort rules restate the max-effort decision. The 2.1.283 Workflow tool's own `effort` description says "use
  'low' for cheap mechanical stages and higher tiers only for the hardest verify/judge stages". That decision's effort
  sweep has not run, and its claim that the variable overrides child effort rests on 2.1.281 probes (P6, P9) that
  were not repeated on 2.1.283.
- "Routine" is undefined. The 2.1.283 Ultracode reminder says to use the Workflow tool on every substantive task and
  stay solo "only on conversational/trivial turns".
- `AGENTS.md` is a shared hot file, so this change is `lane:shared` and needs the trading lane's acknowledgement.
  Trading pointers end at the catalyst-convergence wave.
- This workstation's `~/.claude/CLAUDE.md` predates #196, #272 and #294: it still says "Keep routine tasks at ordinary
  effort" and has no top rule, `effort: 'max'`, StructuredOutput or refusal sentence (grep counts, 2026-09-26). The
  post-merge sync replaces the merged copy whole, as the profile recipe now says.
