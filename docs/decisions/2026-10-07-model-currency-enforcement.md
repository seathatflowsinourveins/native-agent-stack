# Model currency enforcement — 2026-10-07

## Decision

Keep the current-model record in `catalogs/foundation/model-currency.json` and
enforce the owner's 42-day release / seven-day landscape rule through the
existing offline `scripts/validate.py`. Extend the existing daily currency
proposal script and timer template, using supported primary metadata interfaces.
Include the two-day advance landscape refresh. Ship empty pending rows; the
command center's refresh fills the inventory and owns switches and host apply.

This serves the north-star foundation: research and simulation should use
explicitly current or recently reviewed model selections. It does not alter a
trading gate, instruction file, deployed model, installer or host configuration.

The row and date semantics, supported lines, proposal location and unknown
conditions are described in [the current guide](../model-currency.md). A
package-bound row follows its latest recorded shipping package and keeps the
original weight identity. Validation tests consistency, not the truth of a
release assertion or completeness of an inventory.

## Sources and demonstrated gap

- `huggingface/huggingface_hub@v2.1.1`, commit
  `bd4a76030582d118e28dc9ad6c7a5911ea76176b`: [native models-info CLI](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/cli/models.py#L223-L237),
  [default main revision](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/constants.py#L60),
  [model metadata semantics](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/hf_api.py#L799-L819),
  and [implicit-token early return](https://github.com/huggingface/huggingface_hub/blob/bd4a76030582d118e28dc9ad6c7a5911ea76176b/src/huggingface_hub/utils/_headers.py#L147-L151).
  Installed 2.1.1 help/source and unchanged pinned source were checked; no
  upstream client is rebuilt, forked or replaced.
- [GitHub latest-release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release),
  read 2026-10-07: latest published full-release metadata is a discovery lead.
  Different tags require the existing version-order comparison and owner review.
- [PyPI project JSON API](https://docs.pypi.org/api/json/#get-a-project), read
  2026-10-07: the registry supplies latest project metadata and artifact upload
  dates. Yanking and metadata are separate from engineering acceptance.
- `systemd/systemd@v259.5`, commit `b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a`,
  [service command failure prefix](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml#L1443):
  the existing timer's oneshot adds a read-only pre-step; the `-` prefix permits
  the offline notice after a failed pre-step. Native unit verification checks
  syntax, not timer execution or installation.
- `native-agent-stack@3d7d4a4b2640c8583d8855670111ef5d023d3e03`:
  `scripts/freshness_propose.py:861,942`, `scripts/validate.py:144,484`,
  `adoption/templates/systemd/stack-currency.service:16-26`,
  `docs/acceptance-evidence-policy.md:24-38` and `docs/lanes.md:94-115`.
  This reuses the current proposal, validation, evidence and timer seams.

The vendor supplies metadata retrieval. It does not implement this repository's
owner-defined age limits, package/model join, landscape exception or evidence
publication rule. Those small deterministic checks are local integration glue;
the tests are synthetic/local integration, not an unchanged upstream harness.

## Alternatives and overturn conditions

Manual reminders do not enforce the age rule. A new validator executable would
duplicate the publication gate. An automatic model switch would cross the
selection and host-application boundary without model qualification. Treating
Hub `last_modified` as a release date could renew an old model on a documentation
edit. These alternatives are not adopted.

A maintained upstream that implements the dated policy and package join can
replace the local glue after equivalent negative controls pass. Broader Hub
branch support requires native branch-versus-tag verification; the scaffold
accepts the upstream default `main` as its moving line. Vendor-page, hosted
model, non-Hub registry and cross-family/repository discovery require primary
source adapters or explicit source review before coverage can be claimed.

The completeness review identified package-bound line precedence, stray
nonbinding package metadata, immutable Hub refs and refresh timing before the
42-day transition as ways a daily check could miss or crash a review. The
implementation and focused negative controls cover
those cases. The next landscape sweep must cover the unsupported modalities,
model-family replacements and complete host inventory. Unknown stays unknown.

## Evidence and limitations

The new fixtures exercise stale/fresh boundaries, sourced exceptions, package
joins, malformed dates/URLs, actual validator CLI integration, primary-source
failure/budget paths, revision versus release differences and append-only
proposal writes. [The scoped receipt](../../evidence/artifacts/model-currency-enforcement-20261007/checks.json)
records actual commands and outcomes. No model weights, inference, new package,
real model selection or host timer activation is part of this unit.
The timer's 900-second whole-unit timeout and large-inventory behavior remain
unaccepted; ordinary pre-step failure handling does not prove timeout recovery.

## Addendum (2026-10-07): fixture scratch correction

The scoped receipt calls the original unit fixture's cache directory ignored.
That property was wrong: `.cache/` was not ignored at the frozen base. The three
owned, regenerable unit copies were moved unchanged to `.runtime/`, which
`git check-ignore` confirms is ignored by the base's `.gitignore:6`. No host unit
was installed, enabled or changed. The proposal test's temporary directory now
uses the same existing ignored `.runtime/` carrier; its rerun returned 0,
23 tests in 0.039s, OK. The original receipt/result stays unchanged and this
addendum corrects only its scratch-location classification. Raw logs remain in
private coordination state. This also corrects the worktree scratch convention
for subsequent checks.

## Amendment (2026-10-07): ruled partial fill and current carriers

The command center's model refresh was ruled at 2026-10-07T01:35Z. Its verified
source-record SHA-256 is `44679fd1d26dfec36b3b57cdbde2df4290d1b068118562cb8811bf3eb7cd6941`.
The current catalog now declares 20 strict artifact/model-consumer rows and seven
primary package snapshots. It stays pending: [the new source-review record](../../evidence/artifacts/model-currency-enforcement-20261007/fill-source-review.json)
preserves date/revision bases, corrections and eight unresolved groups. The
original scaffold receipt and decided policy above remain unchanged.

The five frontier selections retain canonical IDs. The CC reports the separate
Sonnet 5.5 background-slot override applied at 01:46Z; this wave changes no live
client configuration and asserts no new background-usage smoke. Local KEEP
exceptions use the ruling's UTC date, October 7, and sourced alternatives/overturn
conditions. Planned QMD retirement is not actual retirement: its interim vector
model needs a scoped exception or an applied cutover before a strict row can be
claimed. Unpinned bundled loaders, mismatched enclosing versions and uncovered
roles remain pending; no invented date, SHA or landscape check fills them.

Current independent embedding carriers name Nemotron-3-Embed-8B, 4096 dimensions
and exact query/document prefixes. Claude's template names NativeStack2604's
21633/28231 services; parameterized Codex/OpenHands templates keep host inputs.
OpenHands' disabled entries and container-visible proxy contract are unchanged.
The ai-memory example explicitly requires 2.5.2 prefix support; component pins,
qualification receipts and installer alignment stay with their owners. The
generated install script needs its maintained generator/owner fold, not a manual
script edit. Its unresolved source-generation boundary is not counted complete.

Sources: `akitaonrails/ai-memory@v2.5.2/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83`,
[top-level prefix configuration](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L454-L502)
and [factory wiring](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-llm/src/factory.rs#L262-L269);
`giancarloerra/SocratiCode@f6191f076a42405f0d5508139f3a8b505cfef93a`,
[embedding configuration](https://github.com/giancarloerra/SocratiCode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/src/services/embedding-config.ts#L62-L69);
and [the pinned NVIDIA card](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16/blob/d1f2f25730bbd775b99b29185134bc86653bf2d1/README.md).
The card's 32768-token capacity, declared server's 8192 bound and SocratiCode's
4096 input limit are distinct consumer constraints.

The Claude SDK example's former implicit DVA Opus 5 candidate is superseded.
It now requires an explicit advertised Claude-family model. Opus-role work uses
the existing native Claude Code route with Opus 5.5; changing the gateway model
string alone would retain the gateway transport. No new transport wrapper is
introduced. The September 27 decision's dormant #359 binding remains historical;
its next use selects GPT-6.1 Sol unless the existing preregistered comparison at
that decision's line 469 establishes a different choice. Historical experiment
results and trading carriers are preserved; trading amendments are routed to 5f.

Source boundaries: OmniRoute at `c1e30b7676975feb298b49eff6ff58923c04b89e`
and `8ad6b1c46eaea49ab6b6e9929817c08a90c5067b` has the same
[Devin Opus 5 catalog](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/config/providers/registry/devin/catalog.ts#L48-L76).
This verifies that catalog, not every gateway or the actual serving identity.
Installed Claude Code 2.1.292 version/help supports the proposed native model and
effort flags; its [changelog](https://github.com/anthropics/claude-code/blob/v2.1.292/CHANGELOG.md#L1226-L1228)
and [vendor release notes](https://platform.claude.com/docs/en/release-notes/overview)
date the selected frontier models. The unchanged pinned SDK passes model/env
options through its [subprocess transport](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L622-L626).
OpenAI's [model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
and [September 29 changelog](https://developers.openai.com/api/docs/changelog)
confirm GPT-6.1 Sol's exact ID/date; native account and gateway availability are
separate from currency. These primary pages were re-read October 7.

The CC selected a persistent MinerU user unit as the model-source carrier.
[Its recipe](../../recipes/mineru-local-service.md) runs the shipped foreground
module with the supported local-source environment override and the CC alert
handler. Activation, native status and a fresh-shell PDF smoke are CC window
items. The embedded engine's CPU guard remains unqualified: its explicit
99-GPU-layer argument is not overridden by the separate external wrapper's
environment variable. The template supplies source only and does not claim
CPU-only acceptance or a native running-source getter.
