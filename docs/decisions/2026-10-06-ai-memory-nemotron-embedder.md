# ai-memory's accepted Nemotron embedder — 2026-10-06

NativeStack2604's interim ai-memory2.5.2 now uses the supported
OpenAI-compatible Nemotron-3-Embed-8B route, with exact `query: ` and
`passage: ` prefixes and4096 dimensions. The command-center executor accepted
the switch at2026-10-06T16:45:58Z. The [sanitized native receipt](../../evidence/artifacts/ai-memory-embedder-switch-20261006/receipt.json)
is published unchanged; the private run, questions and conversations are not.
The action serves reliable cross-client memory for north-star R&D.

This decides the interim embedder, not the durable-memory product. D3r4 and
its registered amendments alone decide the memory owner; candidate execution
belongs to the designated executor in throwaway StackMeasure2604.

## Evidence and its boundaries

| Gate | Actual executor result |
| --- | --- |
| Recovery | Exact restoration of the native backup |
| Initial embedding migration | 331/331 pages,0 failures/errors,78.632s |
| Acceptance census | 335/335 latest pages carry the current identity;0 incomplete scopes and failure rows |
| Fixed retrieval set | 29 usable targets; hit@5 29/29→29/29; hit@1 23→27 |
| Dense participation | Vector stream active29/29; no degrade lines in the recorded comparison |
| Exact instruction prefixes | Both prefixes proven; cosine difference≤2e-6 |
| Latency on that set | p50 184→54ms; p95 341→173ms |
| Cross-client Gate3 | PARTIAL, non-blocking: Codex→Claude PASS; Claude→Codex not run after switch |

The set has29 targets, not30:24 of58 stable pages were lifecycle-only and
five more were duplicate/count-only. promptfoo0.123.1 MCP output is a
JSON-encoded array of content blocks; the assertions unwrapped its text
content before parsing hits. Scorer errors use `failureReason == 2`, separately
from failed assertions. These corrections are part of the retained receipt.

Codex→Claude passed late after the Claude login changed, with recall and
control-clean true and the vector stream. The Claude→Codex post-switch source
session did not run because of429; missing Claude-side prompt capture had
already failed in the baseline and job10. Its repair is a separate owner-applied
client change followed by fresh-marker Gate3, not a passed direction here.
The receipt also records that the strict fact-text control was false in every
run; do not relabel its association-based control as that stricter result.

The manager-level service environment check was blocked by the project's
secret guard and remains untested. Unit-scoped metadata does not substitute
for it. Native executor evidence, local publication validation and pinned
source review are different classes; no model run or upstream test was
performed merely to publish this record.

## Sources and supported profile

ai-memory v2.5.2 tag `af8c6820`, commit
`7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83`, ships the exact prefix route:
[config keys and preserved spaces](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L461),
[factory wiring](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-llm/src/factory.rs#L262),
[query/document prefix application](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-llm/src/embedding.rs#L465).
Prefix keys are also present in
[v2.5.0 config.rs:489–503](https://github.com/akitaonrails/ai-memory/blob/v2.5.0/crates/ai-memory-cli/src/config.rs#L489).

The served model is `nvidia/Nemotron-3-Embed-8B-BF16`, HF revision
`d1f2f25730bbd775b99b29185134bc86653bf2d1`.
Its [pinned model card](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16/blob/d1f2f25730bbd775b99b29185134bc86653bf2d1/README.md)
specifies the literal prefixes and4096-dimensional output. The document
prefix contributes to stored model identity; the accepted identity is
`nvidia/Nemotron-3-Embed-8B-BF16+dp1-707ad539ebca7d87`.

The GPU profile is documented beside the portable MiniLM default in
[the config example](../../examples/ai-memory-config.toml.example) and
[the recipe](../../recipes/README.md#project-memory). Top-level embedding keys
must precede the first TOML table. The native background interval is900s.
Startup also backfills every scope independently of that periodic setting:
[serve.rs:1920–1947](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/serve.rs#L1920).
Configure and inventory the owned store before restarting; a project-only
admin request does not contain this startup job.

For assertions, promptfoo0.123.1 at
`34f74d34e140b5e17d23770dfb2340057b1936b8` calls the MCP tool and
[serializes content arrays](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/mcp/client.ts#L486).
The [native ai-memory explanation](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-mcp/src/server.rs#L2837)
and expected hit's vector rank/contribution establish dense participation;
a successful lexical fallback alone does not. Stored-score provenance is in
[reader.rs:686](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-store/src/reader.rs#L686).

## Alternatives and overturn condition

The [primary LMEB scores API](https://mteb-leaderboard-backend.hf.space/v1/benchmarks/LMEB/scores)
was re-read on2026-10-06. Its reported `meanTask` values are external benchmark
evidence, not runs of these alternatives on this host or a memory-product vote.

| Alternative | Rechecked LMEB meanTask | Disposition |
| --- | --- | --- |
| Nemotron-3-Embed-8B-BF16 | 0.6436 | Accepted supported GPU integration and native task gates |
| Nemotron-3-Embed-1B-BF16 | 0.6150 | Model fallback requiring its own integration qualification |
| Qwen3-Embedding-8B | 0.5594 | Maintained alternative, not run in this switch |
| Octen-Embedding-8B | No matching row in the queried API | Excluded by the plan; no native qualification claimed |
| all-MiniLM-L6-v2 | 0.4377 | Portable CPU default and operational fallback |

Overturn this embedder choice when a maintained challenger wins a frozen
paired native comparison through the supported harness: same usable page
targets and scope, exact publisher preprocessing, successful recovery and
complete body/abstract vector coverage, no hit@5 loss, improved retrieval
quality at@1 or a repeatable latency/resource advantage without quality loss.
Freeze the comparison and its gates before running it, retain all failures
and usage, and require cross-client capture/recall after the existing capture
defect is repaired. A model-card score, tool exposure or version check alone
does not overturn this native integration. The broader memory-owner
measurement remains D3r4's separate decision.

Backups remain private until at least2026-10-13. The optional workspace-wide
force-embed purge of227 superseded MiniLM rows is deferred to waveB; it was
not part of this publication and must preserve recovery and scope boundaries.

## Capture repair and pending config consistency

After this acceptance the CC applied ai-memory2.5.2's own Claude hook
installer with explicit `--capture-prompts`; its readback now includes
UserPromptSubmit and preserves every unrelated hook. Fresh-marker
Claude→Codex Gate3 subsequently passed at17:47–17:50Z through a fresh Claude
source under the shared lock and a fresh native Codex receiver on the default
tier. One prompt observation and one current-identity embedded page were
present before the receiver ran. Native tool results showed recall_pass and
association-based control_clean true; the expected hit had vector rank1.
The strict no-canary-fact-text control remained false, so this does not assert
that stronger condition. Only the assigned scratch scope was used; raw source,
receiver and marker/fact evidence remain private. The immutable receipt above
retains its acceptance-time PARTIAL result rather than being rewritten after
that repair. This follow-up is actual native execution with a synthetic canary,
separate from the29-target retrieval comparison and any upstream test.

Passive native spool-status samples after the prompts decreased30→18→10
pending, with oldest age11169→2660→708ms and zero reported retries. This
shows drain progress, not an observed globally empty queue. Native status
did not report acknowledgement counts; those remain unknown and are not
manufactured from pending deltas. Prompt storage and receiver recall are
independent evidence that this canary landed.

The CC will separately apply this top-level consistency setting:

```toml
server_url = "http://127.0.0.1:29374"
```

It names the thin client's endpoint, not the server's bind address or
embedding endpoint. It is pending because applying it changes the accepted
config hash. The earlier49374 log lead was withdrawn: a generic startup
log prints the configured client default before command-specific backfill
URL selection; it did not prove requests went to the wrong listener.
Sources: [config.rs:267/1655](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L267),
[backfill endpoint override](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/backfill.rs#L156).
