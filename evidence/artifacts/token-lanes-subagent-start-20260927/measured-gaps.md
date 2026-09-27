# Token-lanes measured gaps, 2026-09-27

Evidence class: **local measurement of native transcripts**, retained from the
coordinator's `scratchpad/units/w3/lanes-facts.md` report dated 2026-09-27
(approximately 12:45Z). This unit transcribes its counts; it did not rerun the
workflows or inspect their prompts/tool inputs. Run names below are aliases;
workflow identifiers, personal paths and transcript contents are omitted.
The earlier [README](README.md) and `receipt.json` remain historical evidence.

Repair-round erratum, 2026-09-27: the fetch count below is outside #381's M4
population and lacks per-child fetch-tool exposure evidence. The provenance
header and cwd contract are corrected below; all original counts and retained
counter bytes are unchanged. Later coordinator observations are separate inputs.

## Population and carrier state

| Run alias | Agents | Carrier state reported by coordinator |
| --- | ---: | --- |
| Coordinator wave 1 | 12 | Children started before installation; no block |
| Coordinator wave 2 | 12 | Children started before installation; no block |
| Landscape sweep peer smoke 2 | 5 | Original block active; installed 08:26:32Z from `main` at `5f3a7c21` |

The differing workloads and populations prevent a causal before/after comparison.
Smoke 2 used the original carrier, before this measured-gap revision.

## M4-style remote fetch count, smoke 2 (outside the preregistered population)

[#381's preregistration](../token-adoption-e2e-20260926/preregistration.json),
`thresholds.M4`, applies to stack-researcher and Codex B, including nested and
unclassifiable remote fetches, with routed rate >=0.9. The discover/refute-facts
roles below are outside that population; this is not a #381 evaluation.

| Agent role | Model | WebFetch | WebSearch | ctx_fetch_and_index | ctxExec | Skill |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| discover | opus | 5 | 4 | 0 | 17 | 4 |
| refute-facts | sonnet | 10 | 0 | 0 | 0 | 3 |
| refute-fit | opus | 0 | 0 | 0 | 17 | 2 |
| gpt6-discover and gpt6-refute-fit wrappers (combined) | sonnet | 0 | 0 | 0 | 0 | 0 |

Descriptive M4-style tool count: **0 / (15 + 0) = 0/15 through ctx_fetch_and_index**.
Whether `ctx_fetch_and_index` was exposed to any of these children is unknown;
the baseline did not record it. WebFetch calls prove that tool was exposed to
discover and refute-facts; exposure for the remaining children is also unknown.
This count is not an access-qualified routing/compliance score. WebSearch is
discovery and is excluded from the descriptive denominator. The tool-profile
counter's `ctxExec` column aggregates `ctx_execute`, `ctx_execute_file` and
`ctx_batch_execute`; it is not a provider-usage counter. The original block had
no web-fetch rule. The coordinator also reported the two Sonnet wrappers'
verbatim `codex_call.sh` copy check as **2/2**; their task/return text is not retained.

## M3/M5: context containment

| Run alias | Tool results | Results over 5,120 bytes | Share of result bytes from those results | ctx_execute results over 5,120 bytes |
| --- | ---: | ---: | ---: | ---: |
| Coordinator wave 1 (no block) | 1,452 | 198 (13.6%) | 61.4% | 40/119 (34%) |
| Coordinator wave 2 (no block) | 1,589 | 314 (19.8%) | 70.7% | 78/214 (36%) |
| Landscape sweep peer smoke 2 (block) | 126 | 30 (23.8%) | 74.7% | 16/34 (47%) |

These are descriptive counters inspired by [preregistration #381](../token-adoption-e2e-20260926/preregistration.json): M3's target is
at most 20% of result bytes from results over 5 KB; M5's target is at most 10% of
context-mode results over 5 KB. The displayed M5 column is specifically
`ctx_execute`, not all context-mode tools. M3 counts here retain `Read` results,
including legitimate read-before-edit exceptions; they are not an
exception-adjudicated M3 score. `Read`, `Bash` and `ctx_execute` were the largest
carriers of oversized-result bytes in the supplied report. This is not a new E2E
run or an accepted pass/fail evaluation of #381.

## Counter records and reproducibility

The two `.txt` files are unchanged copies of the coordinator's Python counters,
retained as source records rather than installed executables. They read native
`tool_use`/`tool_result` blocks and print counts, labels and byte shares. Metadata
labels and directory basenames must still be sanitized before publishing a new
run. The retained tables contain no raw prompts or tool inputs.

| Source relative to scratchpad | Retained record | SHA-256 of the retained copy (equal to the source when copied) |
| --- | --- | --- |
| `units/profile_workflow_tools.py` | [profile_workflow_tools.py.txt](profile_workflow_tools.py.txt) | `273688e95dd3136a28c400e8ce67a0e6cbb2e6bcc4c5dd91f9e40effd10d03e3` |
| `units/containment_m3.py` | [containment_m3.py.txt](containment_m3.py.txt) | `e2ddebe66bc75b9ca8f0b9137d2d2867330ae52bfb12c754014e7230f01e748c` |

Dated provenance correction, 2026-09-27: the tables came from these retained
revisions, before the tool-profile source's later ctxSrch edit; its current hash
need not match the retained copy. The containment source still matches its copy.

`containment_m3.py` counts each `tool_result` once. String bodies are measured as
UTF-8; other bodies use UTF-8 JSON with `ensure_ascii=False`. Oversized means
strictly greater than 5,120 bytes. This differs from context-mode 1.0.169's
5,000-byte `intent` indexing threshold. Raw byte totals, full per-carrier tables
and provider usage were not supplied in the facts report and are not inferred.
Private native transcripts are required to independently reproduce the counts;
the public records alone support inspection of the method and reported results.

## Upstream contracts and claim boundary

- [mksglu/context-mode 1.0.169, commit `589d8214d56740a28b5f7bf63167743d586b0b40`, `src/server.ts` L3423-3478](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L3423-L3478): indexed HTTP page fetches, `requests` batches, `concurrency` and retrieval through `ctx_search`.
- [The same revision's executor, L295-312](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/executor.ts#L295-L312) runs every language except Rust at the supplied `cwd` or server project root; writes persist. [Routing L939-941](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/core/routing.mjs#L939-L941) pins shell cwd on Claude. The schema description at server.ts:1731 is stale; the original bound-to-main-checkout warning is correct for non-shell child calls without cwd. [Rust L290-292](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/executor.ts#L290-L292) uses temp and needs absolute project paths.
- [`intent` indexing/preview contract, L1733-1740](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1733-L1740); [L1979-1980](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1979-L1980) defines the 5,000-byte threshold. [`ctx_search` schema L88-94](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/search/ctx-search-schema.ts#L88-L94) defaults to 3 results per query; the carrier's limit <=3 remains local policy.
- [Claude Code WebFetch tool contract](https://code.claude.com/docs/en/tools-reference#webfetch-tool-behavior), read 2026-09-27: model-mediated extraction, consistent with the supplied installed 2.1.283 description. The installed CLI independently returned `2.1.283 (Claude Code)`; a version check is not a model run.

## Repair-round observations, 2026-09-27

Evidence class: **coordinator-reported local measurement of native transcripts**,
from `units/w4/e2e-facts.md` (matrix observations 13:20-13:50Z) and the independent
repair review. This builder did not rerun those probes. The matrix scored 15
dispatch rows against 19 upstream calls and agreed with all 15 worker reports;
that agreement is not unchanged upstream acceptance or proof of access elsewhere.

- Claude Code 2.1.283 ToolSearch returned only tools granted to each agent;
  naming an unavailable tool still returned the remaining granted tools. The
  reviewer observed a bootstrap selection returning only the two Serena tools.
  Six of the seven shipped non-blind role definitions lacked
  `ctx_fetch_and_index`: evidence-reviewer, isolated-builder, security-reviewer,
  semantic-evidence-reviewer, source-scout and stack-verifier. Tool grants in a
  definition and exposure in a running child are distinct; neither fills in the
  missing smoke-2 exposure observations.
- In-process agent-team teammates reached only HTTP-transport MCP servers
  (ai-memory); stdio and plugin servers were missing in that matrix. An
  interactive lead independently reproduced the boundary: its own search found
  the requested tools, its teammate found only ai-memory. TOKEN LANES reached
  the teammates. This is a dated 2.1.283 observation, not a general client limit
  or a proposed workaround.
- The peer's separate smoke 3 reported 45/134 results over 5 KB, carrying 79.6%
  of result bytes; `ctx_search` was 11/20 and `ctx_execute` 27/52 over 5 KB. These
  supplied counts motivate specific queries with limit <=3; they are not an
  after-measurement of this repair, a controlled comparison, or a #381 score.

For the next sweep and coordinator-wave remeasure, retain a row for **each child**
with sanitized alias, role, carrier revision, `ctx_fetch_and_index` exposed
(yes/no/unknown), WebFetch exposed (yes/no/unknown), and the native tool-list or
ToolSearch evidence for both flags. Record fetch counts including nested and
unclassifiable fetches, containment counts and wrapper copy checks. Only fetches
by children with confirmed `ctx_fetch_and_index` exposure enter the routing
denominator; show absent/unknown exposure separately, not as non-compliance.
Keep the #381 population distinct. The smoke-2 access-qualified denominator is
unknown and cannot serve as a measured compliance baseline.

The [dated decision addendum](../../../docs/decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-measured-fetch-and-containment-gaps)
defines the correction and remeasurement gates. Local subprocess/install tests
are separate integration evidence, not unchanged upstream tests, live provider
execution, savings, or proof that the revised routing will be followed.
