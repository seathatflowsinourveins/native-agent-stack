# Recorded upstream results

These are selected results from actual executions. Commands involving the original project's indexes require equivalent explicit setup on another host. The [native recipes](../recipes/README.md) provide installation and portable reproduction steps; the [evidence index](../manifests/evidence.json) maps results to their receipts.

| Upstream operation | Actual result | Scope |
| --- | --- | --- |
| SocratiCode `codebase_search`, limit 1 | `linux-usage-report.cjs`, lines 2–39, score `0.6429` | Both native clients; also direct in the current Desktop task |
| ai-memory `memory_read_page` | Correct accepted deployment decision and four disabled features | Both native clients; direct Desktop read also observed |
| QMD `search` then `get` | Relevant native RAG guide, search score `0.86`, requested source lines returned | Current Desktop task; Claude separately searched the same guide |
| codebase-memory `search_graph` / `trace_path` | `collect`, lines 91–127; four direct callees: `installation`, `sourcesFor`, `runParser`, `overlaps` | Static graph, not a runtime call trace |
| `agent-browser` open/snapshot/fill/click/get/close | `Hello, Publication Codex Desktop!`; all exits `0`; screenshot visually inspected | Public HTML fixture, isolated owned session; Claude separately returned `Hello, Publication Claude!` |
| `shellcheck fixtures/example.sh` | Exit `0` | Public fixture |
| `markitdown fixtures/greeting.html` | Exit `0`, expected heading present | Public fixture |
| `ast-grep run --lang javascript … --stdin` | Exit `0`, `8` function matches | Public source fixture; exact pattern in receipt/recipe |
| `difft --exit-code --color never fixtures/before.py fixtures/after.py` | Exit `1`, meaning differences found | Expected upstream status, not a failed comparison |
| TOON encode then strict decode | Both exits `0`; recovered JSON semantically equal | Public records fixture |
| Repomix with two explicit included files | Exit `0`; both selected paths present | Public records and shell fixtures |
| `wt list --format json` | Exit `0`, `3` worktrees | Publication worktrees at capture time |
| Local embedding request | `2048` finite values; norm `1.0000000207936353` | Pinned Nemotron model, actual GPU inference |
| Automatic code watcher | Add `3.008 s`, update `3.007 s`, delete `3.006 s` | Persistent store observed without a tool-triggered refresh |

## Exact retained-text measurement

The included public artifacts were counted with upstream `gpt-tokenizer@3.4.0`, `o200k_base`:

```text
full source:       2730 tokens
retrieved result:   491 tokens
removed:          2239 tokens
reduction:        82.01465201465201%
```

The original source before personal path anonymization measured `2731 → 491`. Neither comparison measures whole-provider savings: prompts, schemas, coordination, retries and the rest of the task are outside this artifact comparison.

## Native client usage and unresolved boundaries

The successful native RAG task reported Codex input `64361`, including cached input `41472`, and output `241`. Claude reported ordinary input `8`, cache creation `24236`, cache read `117011`, and output `543`. These native accounting conventions differ; they are usage receipts, not a paired efficiency experiment.

The additional Claude document/graph/browser task completed with `9` tool calls and `51` successful hook responses. Its final `126` words exceeded the requested `120`, so full instruction adherence is not claimed. The corresponding native Codex CLI attempt returned `usage_limit_exceeded` before tools; usage was unavailable. Current Desktop execution is recorded separately.

vLLM `0.29.0` installed and passed version/help checks but failed actual WSL GPU initialization with `RuntimeError: UVA is not available`. The working `0.25.0` service was restored and a direct semantic query then passed. Optional live HUD, outer Claude-to-Codex slash-command invocation and native promptfoo evaluation retain their unexecuted boundaries.
