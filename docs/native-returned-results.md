# Native command results attached to the report

The local [Native returned results tab](http://127.0.0.1:17500/token-savings.html#native)
now gives the selected Codex, Claude and dashboard checks their own visible
records, execution dates, original returned text and downloadable attachments.
The full JSON export includes those bytes; downloads do not depend on inaccessible
filesystem links. The page is a local evidence viewer, not an upstream agent
dashboard or proof that every catalog component ran.

The [dated receipt](../evidence/receipts/native-returned-results-20260921.json)
links the [native client returns](../evidence/artifacts/native-returned-results-20260921/native-clients.json)
and [dashboard observations](../evidence/artifacts/native-returned-results-20260921/dashboards.json).
Both clients completed the five selected calls. Each RTK result measured 537 to
178 tokens for the retained Git output; each native counter separately increased
by 17 estimated saved tokens. Thirteen adopted dashboard views showed useful
data, with QMD inventory checked separately. The native children's Serena URL
expired; the current Desktop connection subsequently returned its own working
dashboard. Both the failed URL check and the recovery remain in the report.

## What executes

This acceptance uses existing native authentication, models, project configuration
and tools. A fresh native Codex child and a fresh native Claude child each perform
the bounded read-only task. They are launched by the current Desktop task but are
separate sessions. The Desktop connection's direct Context Mode report is attached
separately. Native usage includes the clients' actual instructions and tool calls;
it excludes the Desktop coordinator and other workers.

The upstream interfaces are
[Codex JSONL execution](https://learn.chatgpt.com/docs/non-interactive-mode) and
[Claude programmatic output](https://code.claude.com/docs/en/headless):

```sh
codex exec -C "$SELECTED_PROJECT" --json --color never \
  -o "$PRIVATE_CAPTURE/codex-final.txt" - < "$FROZEN_PROMPT" \
  > "$PRIVATE_CAPTURE/codex-stream.jsonl" 2> "$PRIVATE_CAPTURE/codex-stderr.txt"

claude -p --output-format stream-json --verbose --include-hook-events \
  --max-turns 12 --permission-prompts none < "$FROZEN_PROMPT" \
  > "$PRIVATE_CAPTURE/claude-stream.jsonl" 2> "$PRIVATE_CAPTURE/claude-stderr.txt"
```

Run in the selected native account scope, from the adopted project. Each actual
invocation in the receipt has its own bounded deadline, full argv and returned
exit. These examples are not instructions to repeat provider tasks at startup.

The frozen task requests actual `rtk git log -6`, scoped QMD search, Context Mode
file extraction and statistics, and Serena's supported `open_dashboard` call.
The captured tool result is the evidence; the model's final description cannot
substitute for a missing invocation. A returned dashboard URL alone does not
establish that its process survives the native client's exit.

## What savings mean

Native RTK before/after reports and exact retained output comparisons answer
different questions. A selected `git log` comparison can measure the size of
those returned artifacts under `gpt-tokenizer/o200k_base`; it does not measure a
counterfactual provider session. Global and project counters overlap. Context
Mode's original text is retained even when its session labels or illustrative
dollar narrative do not match the invocation's independently measured duration.

Do not sum runtime snapshots, provider cache subsets, historical artifact
comparisons or estimates. Missing lifetime counters remain unavailable. The
[native dashboard guide](native-dashboard-data.md) maps official component UIs,
native generated artifacts and the local Grafana integration separately.

## Portable attachment workflow

Use the [portable reporter](../tools/token-report/README.md) with an explicitly
selected private `returned_results_json` manifest. It verifies declared byte sizes
and SHA-256 values before copying and embedding attachments. A mismatch makes the
import fail visibly; the renderer does not fall back to an earlier successful run.
Files and commands named in the manifest are data: the importer executes nothing.

Keep original session streams and local reports private. Review selected outputs
before attaching them: native results can include local paths or private content.
Public GitHub receipts use explicit normalized projections and original hashes.
Another PC must collect its own native results and select its own paths.
