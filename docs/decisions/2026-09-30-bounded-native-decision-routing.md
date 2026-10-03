# Decision: bounded discovery and maintained-decision routing (2026-09-30)

**Scope:** shared directives and a reported Mac deployment reconciliation,
initially based on `origin/main@3361b342`, integrated with `28cfb359` before merge.
This serves the north-star's cross-client memory
and retrieval work. This cloud session owns the canonical repository; the Mac
rollout owner retains global settings and services. No host state, global pins,
model defaults, quality gates or platform acceptance status change here.

## Evidence and decision

The [Mac owner's sanitized issue #384 comment](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384#issuecomment-5924277835)
was read through the GitHub API. It was posted at `2026-10-01T03:42:47Z`
(September 30 in America/New_York). This is **reported host evidence**, reviewed
here as `source_review`; private artifacts and native Mac execution were not
independently reverified by this cloud session.

The report retained a truncated initial discovery of 121,587 tokens and a
source-parser correction. Default top-two memory retrieval missed the current
decision; top-five placed it third. Explicit workspace/project,
`pin_first=true, limit=2`, returned the pinned decision first, followed by an
exact-path read. These observations support a bounded routing rule, not an
answer-quality or whole-task savings claim.

Adopt the existing native discovery and ai-memory query/read paths. Filter
metadata outside the model, initially return at most eight names, descriptions
and source locators, and load only selected schemas. Eight is a local context
budget, not a measured optimum or upstream API limit. Report known omissions
(otherwise mark counts unavailable), preserve
full-output recovery, and widen when the task needs it. Keep detailed guidance
in [token practice](../token-practice.md#bounded-metadata-discovery) and
[the memory lifecycle guide](../native-memory-rag-lifecycle.md#maintained-decision-routing),
with a short rule in the repository, portable Claude, Codex and scaffold sources.
Keep import-only Claude files and hook-carried lane packs as they are.

For maintained decisions, explicitly scope the query, prefer existing pins with
`pin_first=true, limit=2` when the installed schema supports it, then read the
returned exact path. A known path can be
read directly. Check dates, supersession and canonical sources before acting;
memory is evidence, never operating authority. Retry without pin priority when
irrelevant or stale pins crowd out the needed result. Upstream's `QueryArgs`
supports these fields; its single-project pin branch deduplicates and truncates
the combined list to the requested limit. `scopes`, `global` and `as_of` do not
apply pin priority. Native deferred tool discovery, grants, prompt caching and
compaction stay intact.

## Reported deployment boundaries

| Area | Reconciled status and remaining gate |
| --- | --- |
| Mac control | Official ai-memory 2.5.0 replaced local `19b6429`. The owner reports verified ARM archive/binary hashes, schema 66→70, preserved corpus/hooks/providers, integrity and native lifecycle acceptance. This is a control artifact upgrade, not a new memory winner or another host's acceptance. |
| Rollback | Official ai-memory 2.4.0 was tested on the pre-upgrade schema-66 snapshot. Restore the matching corpus and binary together; never open schema 70 with the old binary. Production rollback is prepared, not reported executed. |
| Clients | Darwin Claude 2.1.286 manifest checksum/codesign and Claude Fable 5.1 and Codex 0.159.3 Astra/ultra turns are reported. Scoped exact-path cross-client reads and automatic six-event capture passed. Darwin verification does not verify Linux or alter routing defaults. |
| Embeddings | Ollama 0.34.4 stays production. Staged 0.35.0 returned cosine 0.999985818, below the unchanged `>0.99999` gate. Baseline variation was equally large, so a candidate-specific regression is unproven; retrieval equivalence remains unqualified. |
| Memory selection | Hindsight 0.10.2 stays isolated. Historical `.821` agentmemory versus `.570` ai-memory is descriptive Mac evidence, not a Hindsight comparison. The `.570` belongs to local `19b6429`; the report does not establish the required official-2.5.0 control reproduction. |
| Confirmatory run | Vela/VelaNext is retired. Preregister the surviving host, current allocation, arms and pins before the paired 100-question C3/C4 run. Preserve significant ≥5 percentage-point improvement, A16 Holm α=0.0167, ≤5% C4 fallback and blind cross-family convergence before changing selection. |
| Windows/WSL | The clean packet passed 23 static/pin checks. Native execution, modules, services, OAuth/keyring and E2E remain pending the host's own signed-in session and initial OAuth. Linux Claude's detached signature remains unverified; authentication stores are never copied. |
| Capacity | No hardware purchase is justified. Qualify the combined working set, latency and throughput on the existing Mac/workstation. A dated 102.2-GiB WSL allocation is not the surviving host's current allocation. |

The [historical staged single-writer decision](2026-09-27-mac-single-writer-staged.md)
and memory experiment remain historical records. This artifact upgrade does not
close Stage 2's service ownership, capacity/parity or head-to-head gates. Global
installer, platform and landscape pins need their own supported-path qualification.

The report's QMD README TOC read proves transport/citation only. Headroom retained
1,813→1,813 tokens after a fatal diagnostic, giving zero savings; RTK interception
was unobserved. Keep those failures and costs. Semantic answer quality, complete
task usage and quality-preserving savings are unknown; cache receipts stay separate.

## Compaction follow-up (added 2026-10-01)

The [owner's separate continuity report](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384#issuecomment-5924447784),
posted `2026-10-01T03:58:50Z`, preserves a completed Astra/ultra production
compaction whose tool-free follow-up recalled stale instruction versions and
lost the measured Headroom result. Its semantic gate remains **failed**; the
original receipt and protocol were not rewritten.

A distinct follow-up on the same compacted thread made exactly two native
ai-memory calls: scoped `memory_query(pin_first=true, limit=2, answer=false)`,
then the maintained foundation page's exact-path read. It recovered official
ai-memory 2.5.0, production Ollama 0.34.4, isolated Hindsight 0.10.2 and
Headroom 1,813→1,813 tokens (zero savings). This supports explicit maintained-memory
rehydration, not retrieval-free recall or repaired compaction acceptance. Native
PreCompact dispatch completed; durable attribution to the assigned session is
not established. These remain reported host observations reviewed as
`source_review` here, with no private artifact re-verification.

Extend the short routing rule: after compaction/resume and before describing
deployed architecture, retrieve the verified project's latest maintained
decision. Use bounded pin priority when the installed schema supports it, and
read the exact page when snippets omit required facts; known paths can be read
directly. Disable optional answer synthesis for this lookup with `answer=false`
when supported. Keep native caching and compaction enabled, sources and original
failures visible, and every selection/parity gate open until its own acceptance.
Exactly two calls is the reported recovery's cost, not a hard limit for every
future task or a reason to omit required evidence.

The report also records a prepared 19-file WSL archive, SHA-256
`0da72a5a4afffffed625204cad703eead4be00e1d0c156ee9d90da3351fb285b`,
with 23 package checks and payload checksum/relative-link verification. It has
not been deployed or signed in on Windows/WSL. The user's final handoff separately
reports Mac HTML QA passing 36 checks across 37 feature rows, with no Windows
connection or cross-OS credential bridge. Those are package/UI observations,
not Windows execution or semantic compaction acceptance.

## Alternatives and overturn comparison

- **Full inventory discovery:** rejected for the observed truncation and context
  cost; full inventory remains available for recovery and justified broad research.
- **Default top-two for maintained decisions:** rejected for the reported miss.
  Ordinary scoped search remains appropriate for unpinned/general recall.
- **Duplicate always-loaded packs or a custom router:** rejected; the existing
  native discovery and supported query/read tools meet this information contract.
- **Promote a candidate or global version from the Mac report:** rejected until
  the relevant paired, platform and installation-path gates are satisfied.

A matched scoped comparison that misses necessary decisions with pin priority,
loses a required candidate under the metadata budget, or increases complete task
cost without preserving quality overturns the affected routing choice. Retain
failures, worker usage and native cache/compaction scopes in that comparison; do
not infer savings from smaller discovery output alone.

## Source-only synchronization (added 2026-10-01)

The Codex review found that unrelated pins can fill the two-result limit. The
always-loaded rule now checks relevance and retries without pin priority or
widens before reading an exact path. Detailed guidance alone did not ensure
that behavior on a host without this repository's guides loaded.

The Mac's reported Codex 0.159.3 cannot use the broader lane installer's strict
0.159.2 guard to refresh only instructions. Extend the existing stdlib
`managed_block.py` with `codex-md`, using its existing marker merge and
backup/atomic-write path. It updates only the canonical Codex block, preserves
operator text, refuses duplicate/damaged blocks and a nonblank override, and
never executes a client or opens configuration/authentication. Existing
`claude-md` provides the corresponding Claude operation. The
[supported source-only commands](../../adoption/update.md#refresh-only-native-instruction-blocks)
use a separate exact source checkout and existing QMD refresh after verifying
collection roots. They do not reinstall older platform pins or promote a
candidate. Native consumption remains the Mac owner's acceptance step.

Codex's maintained native global loader checks `AGENTS.override.md` before
`AGENTS.md`, using Rust whitespace. The new command matches that shadow guard;
it does not weaken the full lane installer's configuration/version checks.
Reusing the file-only helper was selected over a broad bootstrap, a copied
ad-hoc writer, or bypassing the full lane's version guard. An accepted native
client failing to load the synchronized block would reopen this integration.

Because root `AGENTS.md` operating text changes, this PR uses `lane:shared`
and records an independent trading-impact acknowledgement at the reviewed head.
That acknowledgement covers instruction impact, not trading runtime acceptance.

## Sources and verification

- [openai/codex rust-v0.159.3 (`01fc69f4`) native global instruction loader](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/codex-home/src/instructions/mod.rs#L41): override/default order and native whitespace; the project document budget begins later in `core/src/agents_md.rs`. Source-only writes reuse this repository's `managed_block.py` and `apply_claude_settings.py` integration path.
- [akitaonrails/ai-memory v2.5.0 (`a8757a05`) `crates/ai-memory-mcp/src/server.rs`](https://github.com/akitaonrails/ai-memory/blob/a8757a05a960f96a0ba510b6341bcd520cf80bb2/crates/ai-memory-mcp/src/server.rs#L565): `QueryArgs` and the pin-first branch at line 2862; `ReadPageArgs` at line 1465 returns the full exact page with related-page expansion off by default. The public release and [v2.4.0 release](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.0) are the report's artifact sources.
- [openai/codex rust-v0.159.3 `tool_search_spec.rs`](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/core/src/tools/handlers/tool_search_spec.rs) and [`tool_search.rs`](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/core/src/tools/handlers/tool_search.rs): native query/limit selection returns tools, not an omission count or cursor. Native configuration listings can contain environment/header values; return a safe metadata projection, not those values.
- [Claude native MCP tool search](https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search) and [Claude Code v2.1.286 `CHANGELOG.md`](https://github.com/anthropics/claude-code/blob/v2.1.286/CHANGELOG.md): deferred schemas and native cache behavior; no discovery replacement.
- [ECC `search-first` at `2b6e839`](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/skills/search-first/SKILL.md): coordinator availability preflight and reuse of existing supported paths. The initial guessed ai-memory repository returned 404; the existing release review supplied the correct `akitaonrails/ai-memory` source, then the tagged schema was checked.
- [Claude setup](https://code.claude.com/docs/en/setup) and [Codex native authentication](https://developers.openai.com/codex/auth): host-specific verification and native sign-in boundaries.

Existing standing-rule, template, scaffold and integrity checks validate directive
consistency. They are local integration/structural checks, not native memory
acceptance or a fresh Mac/Windows/model trial. The PR retains their exact commands
and results. Independent completeness review caught unsupported omission-count expectations,
the native Codex source path, pin-priority crowding, and the older portable
2.3.2 schema needing an ordinary scoped-query fallback. Those corrections feed
the next memory/discovery landscape sweep; that sweep must also check native
Windows execution and official-control quality reproduction, still absent here.
