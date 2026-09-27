# Mac child/worker E2E: readiness-audit (2026-09-27)

Host: `mac-coordinator-64gb-20260925` (macOS arm64, Apple M5 Pro, 18 cores, 64 GB unified memory).
Machine-readable record: [`receipt.json`](receipt.json), the workflow's own per-child usage report
(`examples/claude-native/workflows/child-usage.mjs`-shaped).

This is **one bounded run** of the installed `readiness-audit` workflow, exercised as this issue's
Mac child/worker E2E (issue #276, step 5). It is evidence that the workflow's child/worker fan-out
completes and produces a verified result on this host; it is not a general acceptance of the
`readiness-audit` skill, a benchmark of its accuracy, or a claim that every run behaves identically.

## Question

Does the installed `readiness-audit` workflow (Sonnet readers extract source-cited claims from named
documents and commands, then an Opus verifier adversarially checks each one) run to completion on
this Mac's child/worker path, and what does its own verification pass report?

## Method

One `readiness-audit` invocation, dispatched as a workflow with two phases:

- **Read** (4 Sonnet 5 children, `source-scout`): `read:docs-1`, `read:docs-2` and `read:docs-3` each
  read a slice of the named project documents and extracted source-cited claims; `read:commands-4`
  ran the named read-only commands and extracted claims from their output.
- **Verify** (1 Opus 5.5 child, `workflow-subagent`): adversarially re-checked every extracted claim
  against the original documents and command output, and recorded a verdict per claim.

`receipt.json` is this run's own per-child usage report (`transcript_dir` sanitized to a placeholder
project/session path): every child's `requested_model`, `resolved_models`, `complete` flag and raw
provider usage.

## Results

- **5/5 agents completed** (4 Sonnet readers + 1 Opus verifier), each with `complete: true` and no
  `issues` in `receipt.json`.
- The verifier's pass over the readers' output: **88 claims**, **83 confirmed**, **4 corrected**,
  **1 unverifiable**, **0 refuted**.

No claim was refuted; the 4 corrections and 1 unverifiable claim are the verifier doing its job, not
a failure of this run. The full per-claim verdicts are in this run's own transcript, not reproduced
here; `receipt.json` carries the usage side of the same run.

### Per-model usage (provider-returned, from `receipt.json`)

| Model | Children | Output tokens | Cache-read tokens | Cache-creation tokens | Input tokens |
| --- | --- | --- | --- | --- | --- |
| claude-sonnet-5 | 4 | 117,409 | 828,201 | 182,596 | 56 |
| claude-opus-5-5 | 1 | 115,305 | 5,046,273 | 209,353 | 84 |

Per `docs/token-practice.md`'s "count once" rule, these four columns are kept separate (cache-read,
cache-creation and fresh input are distinct provider counters); they are not summed into a combined
"total tokens" figure here. No child requested a model other than the one it resolved to, and no
child hit a web-search cap (`web_search.calls: 0` throughout).

## Limitations

- One run, one question shape (readiness/status claims over named project records). It does not
  establish a pass rate, and a different document set or command list would exercise different
  content.
- The claim tally (88/83/4/1/0) is this run's own verifier output; this README reports it rather
  than re-deriving it, since re-verifying 88 claims independently is outside this receipt's scope.
- `receipt.json`'s `transcript_dir` is sanitized to a placeholder; the real path stayed under this
  host's own `~/.claude/projects/`, not shared elsewhere.
- This is a workflow/child-worker exercise, not a host-receipt for a `manifests/stack.json` or
  landscape-catalog component, so it does not use `scripts/host_receipts.py` and carries no
  `evidence_class` or `platform_status` claim.

## Reproduce

The `readiness-audit` skill (`args = {docs, commands, question}`) is listed among this host's
installed skills. `receipt.json`'s `children[].label`, `agent_type` and `lanes` show each child's
role and tool-call shape; the workflow itself is `examples/claude-native/workflows/` per
`docs/token-session-handbook.md`.
