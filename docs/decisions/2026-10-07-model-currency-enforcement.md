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
