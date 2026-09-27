# Token-lanes measured gaps, 2026-09-27

Evidence class: **local measurement of native transcripts**, retained from the
coordinator's `scratchpad/units/w3/lanes-facts.md` report dated 2026-09-27
(approximately 12:45Z). This unit transcribes its counts; it did not rerun the
workflows or inspect their prompts/tool inputs. Run names below are aliases;
workflow identifiers, personal paths and transcript contents are omitted.
The earlier [README](README.md) and `receipt.json` remain historical evidence.

## Population and carrier state

| Run alias | Agents | Carrier state reported by coordinator |
| --- | ---: | --- |
| Coordinator wave 1 | 12 | Children started before installation; no block |
| Coordinator wave 2 | 12 | Children started before installation; no block |
| Landscape sweep peer smoke 2 | 5 | Original block active; installed 08:26:32Z from `main` at `5f3a7c21` |

The differing workloads and populations prevent a causal before/after comparison.
Smoke 2 used the original carrier, before this measured-gap revision.

## M4: remote fetch routing, smoke 2

| Agent role | Model | WebFetch | WebSearch | ctx_fetch_and_index | ctxExec | Skill |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| discover | opus | 5 | 4 | 0 | 17 | 4 |
| refute-facts | sonnet | 10 | 0 | 0 | 0 | 3 |
| refute-fit | opus | 0 | 0 | 0 | 17 | 2 |
| gpt6-discover and gpt6-refute-fit wrappers (combined) | sonnet | 0 | 0 | 0 | 0 | 0 |

Remote fetch routing: **0 / (15 + 0) = 0/15 through ctx_fetch_and_index**.
WebSearch is discovery and is excluded from that denominator. The tool-profile
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

These are descriptive counters inspired by preregistration #381: M3's target is
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

| Source relative to scratchpad | Retained record | SHA-256 (source and copy) |
| --- | --- | --- |
| `units/profile_workflow_tools.py` | [profile_workflow_tools.py.txt](profile_workflow_tools.py.txt) | `273688e95dd3136a28c400e8ce67a0e6cbb2e6bcc4c5dd91f9e40effd10d03e3` |
| `units/containment_m3.py` | [containment_m3.py.txt](containment_m3.py.txt) | `e2ddebe66bc75b9ca8f0b9137d2d2867330ae52bfb12c754014e7230f01e748c` |

`containment_m3.py` counts each `tool_result` once. String bodies are measured as
UTF-8; other bodies use UTF-8 JSON with `ensure_ascii=False`. Oversized means
strictly greater than 5,120 bytes. This differs from context-mode 1.0.169's
5,000-byte `intent` indexing threshold. Raw byte totals, full per-carrier tables
and provider usage were not supplied in the facts report and are not inferred.
Private native transcripts are required to independently reproduce the counts;
the public records alone support inspection of the method and reported results.

## Upstream contracts and claim boundary

- [mksglu/context-mode 1.0.169, commit `589d8214d56740a28b5f7bf63167743d586b0b40`, `src/server.ts` L3423-3478](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L3423-L3478): indexed HTTP page fetches, `requests` batches, `concurrency` and retrieval through `ctx_search`.
- [The same revision, L1728-1740](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1728-L1740): shell-only `cwd` and `intent` indexing/preview output; [L1979-1980](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/src/server.ts#L1979-L1980) defines the threshold. These agree with the connected tool schema.
- [Claude Code WebFetch tool contract](https://code.claude.com/docs/en/tools-reference#webfetch-tool-behavior), read 2026-09-27: model-mediated extraction, consistent with the supplied installed 2.1.283 description. The installed CLI independently returned `2.1.283 (Claude Code)`; a version check is not a model run.

The [dated decision addendum](../../../docs/decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-measured-fetch-and-containment-gaps)
defines the correction and remeasurement gates. Local subprocess/install tests
are separate integration evidence, not unchanged upstream tests, live provider
execution, savings, or proof that the revised routing will be followed.
