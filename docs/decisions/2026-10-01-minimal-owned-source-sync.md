# Minimal routing handoff through the instruction source owner

Decision date: 2026-10-01. Foundation lane; initial source base
`5597f9fae2c6148037a74b4e73d2c55fc11c9ff6`. This resolves one concrete source
integration gap that prevents the native engineering coordinator from receiving
the bounded-discovery/maintained-decision rule without duplicating its existing
profile. It changes no runtime selection or host service.

## Trigger and evidence boundary

The [sanitized Mac handoff](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384#issuecomment-5926166036)
reports that PR #568's full-block previews appended another 56/62-line pack to
generated personal directives lacking this repository's managed markers. The
owner did not apply that duplication. Our synthetic reproduction also appended
whole packs before this correction; it is fixture evidence, not Mac execution.

The subsequent owner handoff identifies the separate canonical producer as
`seathatflowsinourveins/agent-ecosystem`, clean local source
`753777ac8163332a3570888680893821439ee4ab`, and the generated notice pointing to
`config/directives` and `scripts/directives.py`. This is reported source-owner
provenance; this cloud task does not edit that repository or installed globals.
The exact producer revision is publicly readable. Independent source review of
its renderer, installer and catalog refresh confirms the source/consumer layout
and broad apply interface; it is not installed-host acceptance.

## Decision

Reuse `managed_block.py` and its native Markdown integration. Add a three-line
`adoption/templates/decision-routing.md` containing only the existing canonical
paragraph and its own markers. `decision-md --print` verifies it against the
Codex template and exports it without opening any target/client state. The
producer owner can integrate this fragment once in its shared directive source,
then render and install through that owner's guarded workflow.

Full-pack operations refuse the known generated notice. For an already-owned
nonblank Markdown instruction source, `decision-md` previews only this small
block, proposing to keep all original bytes outside it. It prints the target
SHA-256 and never writes, backs up or replaces a target. Source mutation belongs
to the producer owner's own guarded workflow. A hash check followed by replacement
cannot guarantee protection from a noncooperating writer; that new write path
was removed following review rather than claiming atomic compare-and-swap.
Conflicting copies (including wrapped paragraphs), damaged markers, unsafe targets
and a shadowing Codex override refuse. A current exact normalized paragraph is
already current. A later full-pack update
refuses a narrow block rather than introducing a duplicate.

This does not adopt a whole legacy pack from a heading or assume that a generated
file is ours to overwrite. The source fragment retains native caching,
compaction, schema-aware pinned retrieval and relevance/widening behavior.
Native client consumption remains the producer owner's readback/acceptance.

## Registry ownership and next boundary

The installed catalog's declared authority is `catalog/registry.json` for
decisions, `manifest.json` for host records and `acceptance.json` for runtime
evidence. Public producer source generates the lookup consumer; its
`catalog_revision` is the registry's content SHA-256. The reported `480e5b5`
prefix agrees with that dated producer's generated hash; prefix agreement does
not prove an entire installed file or exact producer revision.

The reviewed producer's `catalog_refresh.py --apply` invokes its full managed
installer, and preserves source decisions/import pins. It supplies no selective
installed-registry flag. Direct copies would leave its installation receipt
hashes stale. Registry reconciliation therefore belongs to that producer owner:
update source imports and retired-host routes, then qualify a receipt-aware
selective install. This task exports a minimal source fragment and documents
that boundary; it does not synthesize a replacement registry.

## Alternatives and reopening condition

- Appending full current packs: rejected by the reported and reproduced duplicate
  defaults/RTK behavior.
- Automatically adopting a legacy generated pack: rejected because an unrelated
  source owner controls its models, profiles and local text.
- Running broad bootstrap or catalog refresh: exceeds this source-only task and
  can touch unrelated managed files or older runtime pins.
- Minimal source fragment plus the owner's native compiler: selected, with
  export/preview only in this helper and writes owned by the producer.

Reopen if the producer's render drops/duplicates the paragraph, native readback
fails to consume it, or a source/format change invalidates the declared owner or
guard. A measured same-task failure of bounded selection also reopens the rule;
this structural integration does not claim retrieval superiority or token savings.

## Preserved production and failures

The owner's reported production remains official ai-memory 2.5.0 and Ollama
0.34.4, with Hindsight 0.10.2 isolated. The reported lifecycle has 20 passes and
two failures: a native rerank fallback after 20 seconds and invalid synthesis
JSON. A later isolated provider diagnostic returning parsed JSON twice does not
close the 20-second latency mismatch or the original lifecycle failure. No model,
effort, memory promotion or benchmark evaluator change follows from this task.

The 13-check benchmark proposal and its supplied patch digest remain a proposal;
no patch bytes or native execution are integrated here. Surviving-host
preregistration, service/miner ownership and other execution gates remain open.
The owner's QMD path repair, embedding refresh and exact-source read remain
separate host evidence; the lexical ranking miss and cleanup review remain visible.

## Sources and validation

- [Pinned ECC search-first](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/skills/search-first/SKILL.md), verified against the skills manifest SHA-256: reuse and extend the existing integration rather than adding a router or installer.
- [Codex rust-v0.159.3 global loader](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/codex-home/src/instructions/mod.rs#L41): override order and native whitespace.
- [Claude memory](https://code.claude.com/docs/en/memory) and [v2.1.286 changelog](https://github.com/anthropics/claude-code/blob/f5f60250a032caa72d1eb47f9ca5f29becc7066f/CHANGELOG.md): Markdown directives/comments/imports. Direct current memory-page access was denied; the existing cited native integration and tagged changelog were retained rather than claiming a fresh documentation fetch.
- [Producer directives.py at the verified source revision](https://github.com/seathatflowsinourveins/agent-ecosystem/blob/753777ac8163332a3570888680893821439ee4ab/scripts/directives.py): owned inputs, generated notice and render/check interface.
- [Producer install_local.py](https://github.com/seathatflowsinourveins/agent-ecosystem/blob/753777ac8163332a3570888680893821439ee4ab/scripts/install_local.py#L343): whole managed-set installation and receipt hashes.
- [Producer catalog_refresh.py](https://github.com/seathatflowsinourveins/agent-ecosystem/blob/753777ac8163332a3570888680893821439ee4ab/scripts/catalog_refresh.py#L370): broad apply, source-decision preservation.
- Existing `managed_block.py` supplies Markdown marker parsing and preview behavior; `apply_claude_settings.py` keeps its existing full-pack backup/replacement behavior unchanged. The full-profile bootstrap passes its existing `$HOME/.claude/CLAUDE.md` scope explicitly; it does not redirect just one step to a different custom store.

Existing/focused native unittest fixtures verify minimal export, legacy byte and
RTK preservation, zero writes during interference, idempotent preview, generated
output refusal, wrapped duplicate/damaged blocks, Codex shadowing and the explicit
full-profile caller scope. These are local
integration/structural checks. Manifest/catalog validation checks declared
consistency, not the truth of host reports. Independent review checks ownership,
missed formats and the producer boundary before publication.

## Subsequent runtime checkpoint

The [October1 sealed runtime/candidate follow-up](2026-10-01-mac-runtime-memory-candidates.md) records official2.5.2 and later scoped evidence. Earlier2.5.0 observations and original failures above remain historical evidence.
