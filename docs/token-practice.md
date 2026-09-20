# Token practice and measured native results

Recorded September 20, 2026. Read this guide on demand when selecting a context
lane, interpreting native counters, or designing a measured comparison.

The current selection has **56 component records**. The broader catalog has
**505 repository identities: 342 public stars and 163 beyond stars, with 1,054
typed references**. The earlier audit retains its 52-component scope, and the
full-catalog TOON receipt retains the 502-repository input actually measured.
These are bounded catalog counts, not a universal ranking, 56 successful full
E2E runs, or savings from every repository. Supporting runtimes and historical
alternative installations retain separate scope.

## Default practice

Carry out authorized work directly. Keep the plan and verification proportional
to the change; reuse passing evidence when its inputs and scope still match.
Do not turn a bounded fix or setup into repeated intake, planning approvals,
catalog audits or restarts. An optional component is activated when the task needs
it. Repair a failed connection individually while continuing independent work.

RTK global awareness belongs in each actual native client home. Use the
[upstream installation recipe](../recipes/README.md#native-context-mode-and-hooks)
once per profile, then prove use through returned native task results. Stable
Codex uses explicit RTK commands; native Claude supports Bash rewriting. An
installed executable without its instruction reference is incomplete awareness.

1. Retrieve what the current decision needs: exact code with rg/Serena,
   structural patterns with ast-grep, conceptual code with SocratiCode, selected
   Markdown with scoped QMD, and durable decisions with scoped ai-memory.
2. Choose one suitable lane per artifact. RTK formats supported command output;
   Context Mode processes or retrieves bounded results; TOON suits some
   structured data only when the measured representation helps; Repomix outlines selected source; the local Headroom guard
   retains the original. Do not stack transformations to increase a counter.
3. Preserve raw output, errors, input identity and source for recovery. Read
   original implementation before correctness decisions. Lossy retrieval and
   compression can omit necessary information.
4. Preserve native caching, compaction, tool discovery, accounts and model
   behavior. Shared PATH is not host acceptance. Do not add hooks or schedulers,
   override providers, or rerun model trials during ordinary startup.
5. Count once at the proper boundary. Missing measurements are unknown.
   Never add cumulative snapshots, cache subsets, provider usage and artifact
   differences, or multiply a measured difference by repository count.

## Four accepted native coding trials

All four trials passed shared visible tests, hidden acceptance, file-scope and
workflow checks on fixture revision c0bb7561a9c88a98ceaa06d6fcc153f35f55dd69.
Each client ran baseline first, then explicit Context Mode use in a fresh workspace.

| Native client/model | Baseline tokens | Candidate tokens | Observed difference | Wall seconds, baseline → candidate |
| --- | ---: | ---: | ---: | ---: |
| Codex / GPT-6 Astra | 135,217 | 119,998 | 15,219 fewer (11.26%) | 56.129 → 50.207 |
| Claude Code / Claude Opus 5 | 292,561 | 368,121 | 75,560 more (25.83%) | 27.465 → 34.056 |

The candidate made two Context Mode calls in Codex and three in Claude; neither
baseline used it. Native caches were retained and their warmth was uncontrolled.
Plugin tool availability was not fully controlled. One fixed-order pair per
client does not isolate a causal Context Mode effect, establish a repeatable
saving rate, compare model quality generally, or measure the entire stack.

Codex total is input plus output; cached input and reasoning are subsets.
Claude total is ordinary input plus cache creation plus cache reads plus output;
thinking is included in output. Final cumulative task counters exclude the
coordinator, reviewers, audit tooling and report. Billed cost is unknown.
See the [native-pair receipt](../evidence/receipts/token-practice-native-pairs-20260920.json).

## Ten exact retained-artifact comparisons

Counts use gpt-tokenizer 3.4.0 with o200k_base. They describe complete retained
UTF-8 artifacts at the stated boundary, not whole-task or billed usage.

| Native operation | Before | After | Tokens removed | Information boundary |
| --- | ---: | ---: | ---: | --- |
| RTK Git log | 537 | 178 | 359 | Formatting at a fixed six-commit input |
| TOON components | 1,664 | 1,307 | 357 | Structured serialization with native strict decode |
| ast-grep selection | 1,818 | 674 | 1,144 | Selected expression versus complete source |
| QMD source window | 2,672 | 815 | 1,857 | Selected lines versus complete indexed document |
| SocratiCode retrieval | 2,731 | 491 | 2,240 | Selected result versus complete source |
| Repomix outline | 3,697 | 663 | 3,034 | Lossy outline versus complete pack |
| EdgarTools HTML | 10,322 | 1,249 | 9,073 | Offline upstream HTML fixture to Markdown |
| agent-browser snapshot | 67 | 38 | 29 | Interactive controls versus full accessibility view |
| MarkItDown HTML | 10,322 | 1,360 | 8,962 | Exact stored HTML input to Markdown |
| Syft inventory table | 471,760 | 465 | 471,295 | Package columns; other SBOM metadata omitted |

Do not sum the rows. Several share a source or supporting services. Crediting
the SocratiCode difference again to Qdrant, vLLM or MCPorter would count the same
effect repeatedly. Syft package name/version/type columns were checked for equality,
but its table does not retain the complete SBOM. The corrected MarkItDown baseline
uses the exact stored input; the earlier one-byte mismatch is not the accepted pair.

The [artifact receipt](../evidence/receipts/token-practice-artifacts-20260920.json)
publishes counts, byte sizes and hashes. Original host artifacts remain private;
CI does not independently recount those private pairs. Existing public fixture
recounts in [the evidence guide](evidence.md) retain their separate counts.

## A separate full-catalog TOON counterexample

A later conversion used all 502 repository identities. Native TOON 4.1.1
reported approximately 84,907 JSON tokens → 71,770 TOON tokens: 13,137 fewer
(15.5%) under its tokenx 1.3.0 heuristic. Its strict decode round trip passed.
The exact o200k_base comparison instead counted **59,792 compact-JSON tokens →
66,815 TOON tokens: 7,023 more**. The source representations and estimators
are different, so the native estimate is not an exact saving result.

The guard selected the original compact JSON. Keep JSON when conversion
increases the relevant measured input. This is one additional comparison,
separate from the ten retained-artifact pairs above. The [full-catalog receipt](../evidence/receipts/token-practice-catalog-toon-20260920.json)
retains sanitized upstream output, methods and artifact identities; it does not
establish provider savings.

## Native counters and their limits

The [dated native-counter receipt](../evidence/receipts/token-practice-native-counters-20260920.json)
retains returned RTK and Headroom fields, TOON comparison methods and separate
Desktop WSL, native Claude and native Codex Context Mode runtime scopes.

| Upstream command/tool | Native scope | Interpretation |
| --- | --- | --- |
| rtk gain --format json | Retained command-history estimates | Installed 0.49.0 defaults history_days to 90; this is not a forever ledger or provider accounting. |
| rtk gain --project --format json | Same history, selected project | A subset of the all-history view, not another total to add. |
| toon input.json --stats -o output.toon | One conversion | TOON 4.1.1 uses tokenx 1.3.0 estimates here; no native cross-run savings ledger. Exact o200k_base recount is separate. |
| Context Mode ctx_stats | Connection/session and reported lifetime estimates | Session estimates differ from lifetime event-count × 256-token heuristics; neither is exact provider usage. A new Inspector connection has its own session. |
| headroom savings --json | Native usage ledger report | In 0.37.0, the field named lifetime is capped by a 30-day report lookback. Offline guard results do not populate it automatically. |

The reviewed RTK retained-history snapshot reported 46 commands, 11,509 input,
9,852 output and 1,657 estimated saved tokens (14.3974%). Its project view
reported 11 commands, 3,949 input, 3,749 output and 200 estimated saved.
These are dated upstream estimates, not maintained live counters.

The reviewed Headroom ledger returned zero calls and zero tokens in its capped
reporting window. Its separate local guard passed seven fixtures. A zero ledger
does not establish zero guard activity, zero provider usage or zero possible
benefit. Heuristic counters and illustrative API prices are not subscription bills.

### Why the Context Mode lifetime dollar line can be small

In installed Context Mode 1.0.169, the text footer estimates session tokens as
`round((kept-out bytes + cache bytes saved) / 4)`. Its lifetime dollar line prices
`retained events × 256 + current session estimated tokens`. The persisted status
JSON instead reports `retained events × 256` without the session term. The
renderer's fallback is $5 per million input tokens, with an environment override;
this is an illustrative value, not avoided provider billing or subscription cost.

The native database caps 1,000 events per session. Startup removes sessions older
than seven days. Consequently, "lifetime" means retained runtime history and can
decrease. Native Codex, native Claude and Desktop data stores have separate scope.
A small dollar quote without its runtime and capture date cannot establish whole-PC
or per-repository savings. Inspect the installed `src/session/analytics.ts`
(`renderBottomLine`, session token estimate and price fallback), `src/server.ts`
(persisted status), `src/session/db.ts` and both SessionStart hooks when upgrading.

The local report preserves metadata-only event identities, timestamps and project
attribution, plus immutable upstream reports. It excludes prompts and event
content, deduplicates observed events, and never adds these archived event
estimates to overlapping native counters. Missing historical events cannot be
reconstructed. A command output comparison is not an actual-use lifetime total.

Adoption must distinguish enabled hook configuration, observed retained source
labels and completed task acceptance. Native Claude's RTK Bash rewrite is
configured; current Codex practice uses explicit RTK commands. A stale trust entry
for an absent hook file does not activate it. Per-client hook inventories should
respect disabled-hook flags and retain unobserved lifecycle paths.

Only RTK, Context Mode and Headroom expose verified native savings-history
reports in the selected stack. TOON has per-conversion statistics; usage and
telemetry tools report consumption or state. Keep every catalog repository's
adoption and baseline availability explicit, with unknown values left null.
Run role-specific acceptance where applicable; guidance and research catalog
entries are not implied executable deployments. Preserve failed quality gates
when importing new matched-task or retrieval evaluations.

## Coverage and future acceptance

### Supplemental native adoption on September 20

The [supplemental receipt](../evidence/receipts/upstream-native-tools-20260920.json)
adds three installed upstream tools to the current catalog. Beads 1.3.0 completed
23 native operations and ten checks, including persistent claims, dependency
blocking/unblocking and closing all three fixture issues. skills-ref 0.1.0 at
commit `69ef37e9424c0a7ea9dd2293b559e43ec8176379` validated a selected skill,
returned its expected properties and rendered its complete prompt metadata.
otel-tui 0.7.5 accepted one OTLP trace over loopback HTTP and displayed its service,
single span and 10 ms latency; its owned process then closed successfully.

Use the [upstream native recipes](../recipes/README.md#supplemental-native-task-and-inspection-tools)
from either client's ordinary native shell. Beads is available for tasks that
need a persistent dependency queue; initialize only the selected project with
agent-instruction and hook generation skipped. skills-ref is explicitly a
reference/demo validator and does not certify native client extensions. otel-tui
is an on-demand local viewer with no persistent producer configuration implied.
The three tools do not expose verified lifetime token-savings counters; their
installation and functional results are not evidence of provider savings.

The separate [ai-memory 2.3.2 maintenance receipt](../evidence/receipts/native-ai-memory-maintenance-20260920.json)
records an official checksum-verified update after a private upstream backup.
The running service executable, supported native status, scoped search and direct
MCP status passed. Existing hooks, client configuration and project scope were
preserved. Earlier model-task and 52-component study receipts remain unchanged;
these additions did not repeat provider trials or rewrite historical baselines.

The [coverage receipt](../evidence/receipts/token-practice-coverage-20260920.json)
preserves all 52 classifications and 70 captured operations: 66 expected process
checks passed and four failed attempts remain. This is not 52 full-stack passes.

Coverage comprises ten artifact-pair entries, three native-task-pair entries,
19 bounded functional entries, ten current queries, one configuration check,
five historical-only entries, one host-blocked component and three guidance
repositories. Dependency effects overlap even where component classifications differ.

The original audit recorded Linux Playwright ENOENT failures; the then-available
Windows installation was a different host scope. A later separately scoped Linux
acceptance used @playwright/cli 0.1.21, existing Chrome 153 and a loopback HTTP
fixture: seven native commands passed and returned Hello, Playwright!. The earlier
file-URL attempt was blocked. This does not establish default-browser download
or arbitrary-site acceptance. OTel environment and Dagu environment-filter failures have
separately recorded successful corrections. Configuration checks, current alert,
backup and cache queries, renderer fixtures and native model workflows close
different gates. Guidance repositories are not executable tools.

The [later six-component follow-up](../evidence/receipts/token-practice-gap-followup-20260920.json)
retains 31 operations: 28 accepted checks and three failed attempts. In addition
to Playwright, it confirms a one-session AgentsView retrieval, offline ccusage
parsing, a synthetic HUD renderer and full public-paper retrieval with OpenResearch.
These close only their stated gates; live HUD interaction and archive auto-discovery
remain unestablished. The original 70-operation coverage receipt remains unchanged.

Its read-only bridge backend task used 44,908 input + 124 output = 45,032 native
tokens in 11.225 seconds. Cached input of 22,016 is already inside input. This is
additional usage, with no matched saving baseline or outer Claude interaction.
The separate UTC usage parser returned 2,573,385 combined tokens, including its
819,530 Codex subset. Do not add the subset, this trial or earlier task totals to
that overlapping report. Tracked source remained unchanged; native MCP startup
created untracked metadata, and owned temporary services were stopped.

For another experiment, freeze a useful task and acceptance rubric, retain exact
inputs and outputs, record native versions, commands, failures and cache conditions,
and compare final task usage including retries. Repeat or balance run order
before treating a difference as reliable. Keep model trials explicitly scoped;
normal future-session work uses selected retrieval rather than a full audit.

Use the existing [update protocol](../adoption/update.md) and native
[recipes](../recipes/README.md). Append dated sanitized receipts with reciprocal
component links, then refresh the existing catalog generator and integrity map.
Do not publish private transcripts, credentials, environment values or host paths.
