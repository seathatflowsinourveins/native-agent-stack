# Memory owner KEEP and consolidated recall — 2026-10-07

This is a **new successor record**, not an edit to the historical decisions or
acceptance receipt. It records the October6 command-center KEEP ruling,
subsequent long-prompt diagnosis and its one authorized rerun. It supersedes
the older product-selection, released-prefix and MiniLM rollback guidance
only where stated below. Observed values and failed attempts remain unchanged.

## Linked historical records

- [September25 workstation decision](2026-09-25-workstation-sota-refresh.md)
  and [September27 model-currency decision](2026-09-27-model-currency.md)
  remain byte-identical to repository commit
  `0d5e6506434fab598dee861c749a22e628beb75a`.
- [Original October6 embedder decision](2026-10-06-ai-memory-nemotron-embedder.md)
  and [original receipt description](../../evidence/artifacts/ai-memory-embedder-switch-20261006/README.md)
  remain byte-identical to their initial published versions at
  `0eaba2a5d972d875e0f03852d272ba6e16ad03f0`.
- The immutable sanitized [acceptance receipt](../../evidence/artifacts/ai-memory-embedder-switch-20261006/receipt.json)
  retains SHA256
  `8624a287a3df356e4ddabfdd0975ad4b93ca85d83ad57e9bbd36edc6df64339b`.
  Its331/331 initial re-embedding,335/335 acceptance coverage,29 usable targets
  and latency/prefix results are original executor observations, not a new run.
- Earlier branch commits preserve the superseded same-file addendum proposal;
  this successor record relocates that proposal without rewriting Git history.
  Current-instruction corrections live in the adoption recipe. No receipt,
  native transcript or historical decision value is replaced.

## Released prefix support

The evaluation-only decision and v2.4.x observations above remain historical.
Prefix support shipped in v2.5.0 and is supported by v2.5.2, commit
`7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83`:
[v2.5.0 config.rs:489](https://github.com/akitaonrails/ai-memory/blob/v2.5.0/crates/ai-memory-cli/src/config.rs#L489),
[v2.5.2 config.rs:461](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L461),
and [query/document application](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-llm/src/embedding.rs#L465).
The `local` provider's MiniLM default and the OpenAI-compatible prefix route
are distinct supported profiles. The
[October 6 NativeStack2604 decision](2026-10-06-ai-memory-nemotron-embedder.md)
records acceptance of the 8B route and its original native evidence. The
subsequent KEEP ruling is recorded separately below. It supersedes the earlier evaluation-only installation guidance;
no unreleased build or local memory-selection campaign is required now.

## KEEP and upstream re-drive

The command-center ruling `task-ns2604-coop-20261006T204552Z`, section 1,
keeps ai-memory 2.5.2 on Nemotron as the memory of record. It supersedes the
earlier D3r4 and paired-comparison selection gates in the linked original record. No local campaign
is resumed, and StackMeasure2604 is excluded from all lane work. Selection
uses upstream evidence, a clean supported release, one real integration
smoke per consuming client and organic native counters.

Hindsight v0.10.2, commit
`5fc4ce20917b916240cef27c212c387a177f115b`, is the named challenger:
[maintainer release](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.2).
Re-drive on its next clean release after 0.10.2, or new externally inspectable
evidence on coding-agent memory or source-record recovery. This dated record owns that trigger; living adoption recipes link here. This ruling does not convert the 29-target integration
comparison into a memory-product vote.

The strict no-canary-text flag remains false. It is not a defect: the scorer
flags any canary fact among top hits for a never-written control query, while
a small vector corpus can return nearby canary pages. `control_clean` checks
the marker/fact association and is the actual leak control. The previously
recorded pass in both directions refers to that control, not text absence.

## Long-prompt failure and consolidation rerun

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

## Recorded cleanup boundary

CC status235312Z accepted the rerun and records removal of three former MiniLM
model files at2026-10-06T23:52:52Z. Its manifest
`deletion-manifest-minilm-20261006T235252Z.json` retains SHA256
`0070add553649e97bd6a59b27ac00592773398ffaaa3559f48fe40dc75cad7e7`
and91,335,235bytes. This is recorded CC execution, not an independent
OS-wide holder proof by this lane, a database-row purge or backup deletion.
The lane deleted nothing. Backups stay subject to their recorded retention.
The owner's final architecture and supersession register gate further
cleanup; the CC executes every deletion and unregistration.

## Dated correction log

These seven observations were prepared on October6 and are recorded here
as new rows rather than inserted into an existing historical log. Their
original evidence classes and untested boundaries remain explicit.

| Date | Anti-pattern | What happened | Rule or check that prevents it | Where enforced |
| --- | --- | --- | --- | --- |
| 2026-10-06 | Force-adding a host-owned capture marker as a portable repository file | The C10 preparation proposed force-adding the ignored root marker; the repository explicitly forbids committing that host opt-in. The proposal was corrected before staging or publication. | Commit the portable example and placement instructions; leave the root marker untracked and enrollment to the operator. | [Repository policy@0eaba2a5:71–73](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0eaba2a5d972d875e0f03852d272ba6e16ad03f0/.gitignore#L71); [ai-memory2.5.2 marker scope](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/docs/marker-file.md#L68) |
| 2026-10-06 | Assuming a requested known-answer count is the usable corpus count | The ai-memory switch had29 usable targets, not30: lifecycle-only, duplicate and count-only pages were excluded. | Derive the count from the frozen usable target manifest before applying thresholds; retain exclusions. | [Native switch receipt and decision](2026-10-06-ai-memory-nemotron-embedder.md#evidence-and-its-boundaries) |
| 2026-10-06 | Parsing MCP content blocks as a direct hits object | promptfoo0.123.1 serializes MCP content arrays; JSON.parse(output).hits read the wrong envelope. | Unwrap the text content block, then parse and validate hits against exact targets. | [promptfoo@34f74d34 MCP client:486–508](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/providers/mcp/client.ts#L486); the retained switch assertions |
| 2026-10-06 | Requesting manager-wide environment instead of the scoped unit | The switch's show-environment probe was blocked by the secret guard and remains untested. | Use systemctl --user show -p Environment UNIT for scoped inspection, filter approved non-secret metadata and never dump credential values; preserve the untested manager boundary. | [Switch receipt deviations](../../evidence/artifacts/ai-memory-embedder-switch-20261006/receipt.json); native secret guard remains enabled |
| 2026-10-06 | Feeding environment-sensitive inline Python through a guarded here-document | Inline Python here-documents tripped the executor's environment-dump guard. | Put the bounded script in durable owned state and inspect only allowed fields; never bypass the guard. | CC executor handoff,2026-10-06; [accepted switch decision](2026-10-06-ai-memory-nemotron-embedder.md#evidence-and-its-boundaries) |
| 2026-10-06 | Counting failed assertions as scorer execution errors | An error count must use promptfoo failureReason ==2; failed assertions are a separate outcome. | Count the actual returned error discriminator and retain failure versus execution-error classes separately. | [promptfoo@34f74d34 ResultFailureReason](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/types/index.ts#L376); [switch known_answer.test_errors](../../evidence/artifacts/ai-memory-embedder-switch-20261006/receipt.json) |
| 2026-10-06 | Wrapping a cited document without checking its line-bound references | PR800 added three lines before the cited ANTHROPIC_DEFAULT_SONNET_MODEL location; documentation checks passed but the citation-specific CI test failed. | Check the citation contract for each changed source document; preserve valid locators or update their owning records, and keep fallback qualification pending until proved. | [Repository citation contract@0d5e6506:2054–2060](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/tests/test_upstream_surface_watch.py#L2054); [actual failed CI assertion](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37509622651/job/112427730163) |

