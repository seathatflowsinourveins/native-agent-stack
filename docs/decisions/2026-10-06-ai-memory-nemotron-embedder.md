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

## Addendum (2026-10-06): KEEP and upstream re-drive

The command-center ruling `task-ns2604-coop-20261006T204552Z`, section 1,
keeps ai-memory 2.5.2 on Nemotron as the memory of record. It supersedes the
earlier D3r4 and paired-comparison selection gates above. No local campaign
is resumed, and StackMeasure2604 is excluded from all lane work. Selection
uses upstream evidence, a clean supported release, one real integration
smoke per consuming client and organic native counters.

Hindsight v0.10.2, commit
`5fc4ce20917b916240cef27c212c387a177f115b`, is the named challenger:
[maintainer release](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.2).
Re-drive on its next clean release after 0.10.2, or new externally inspectable
evidence on coding-agent memory or source-record recovery. The maintained
[memory re-drive record](../memory-landscape-maintenance.md#october-6-upstream-keep-and-re-drive)
owns that trigger. This ruling does not convert the 29-target integration
comparison into a memory-product vote.

The strict no-canary-text flag remains false. It is not a defect: the scorer
flags any canary fact among top hits for a never-written control query, while
a small vector corpus can return nearby canary pages. `control_clean` checks
the marker/fact association and is the actual leak control. The previously
recorded pass in both directions refers to that control, not text absence.

## Addendum (2026-10-06): long-prompt failure and consolidation rerun

The single fresh source at 21:48Z and receiver at 21:54Z exited 0, but the
Gate 3 scorer returned `recall_pass=false`, `control_clean=true`. The capture
gate timed out at 300 s with no fact-preserving latest page. Full prompt
capture remained intact. The failed native receipt remains private and
unchanged, SHA256
`beba568b2cb04e2666372db300b7209d27a1c0ec13085b5a459491adb4688b92`.

At ai-memory v2.5.2, the deterministic session page renders the capped
80-character observation title; the stored body is separate. The compiled
query result suppresses raw-observation fallback whenever compiled hits
exist, even if those pages omit the requested fact. Sources:
[sanitize.rs:344](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-core/src/sanitize.rs#L344),
[synth.rs:398](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-hooks/src/synth.rs#L398),
and [raw fallback at server.rs:2740](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-mcp/src/server.rs#L2740).
No configurable title bound was found at those call sites. Native
`memory_read_session_observations` can inspect full captured bodies without
an LLM; it was not substituted for the Gate 3 receiver:
[server.rs:4158](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-mcp/src/server.rs#L4158).

Consolidation was disabled with no provider/model and no queued jobs. After
the operator supplied the provider/model choice, the documented
OpenAI-compatible route and SessionEnd consolidation were configured through
an additive, backed-up service override. The existing mixed TOML and unit
environment were left unread and untouched. The approved route uses
`cx/gpt-6.1-sol-max` on the 21128 gateway. Supported configuration
and enqueue/worker behavior are in
[config.rs:948](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L948),
[config.rs:1616](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L1616),
[router.rs:2686](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-hooks/src/router.rs#L2686),
and [serve.rs:757](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/serve.rs#L757).

The one authorized rerun retained the long-prompt design: 191 characters,
with the fact starting at zero-based character 77. Its source consolidation
job completed in one attempt before the fresh native receiver. At
2026-10-06T23:47:19Z the receipt records `recall_pass=true`,
`control_clean=true`, strict text-absence false, two `memory_query` calls and
one `memory_read_page` call. No manual consolidation call or canary page
write was used. The retained private rerun receipt is SHA256
`772f222f0107cffcc48b3b328b527bcfb4a65101d027d11006c2dc87959d32ed`.
This is one steered native integration rerun, not organic use or an upstream
test. Both the failed and passing attempts and their native usage remain
retained; the acceptance-time receipt stays unchanged.

The CC subsequently records MiniLM cleanup in its dated manifest
`deletion-manifest-minilm-20261006T235252Z.json`. That later S14 operation is
separate from the original embedder receipt and the optional purge of 227
superseded database rows. The CC owns the Gate 3 ruling and deletion; this
lane performed no MiniLM deletion. Private backups remain governed by their
retention record.
