---
status: proposed
date: 2026-10-07
decision-makers: [command-center]
review_by: 2027-01-05
---

# Additive requirement text and identity bindings

The legacy saturation requirement digest covers `next_action` and
`decision_ref`, not the requirement text or its layer identity. Two different
requirements can therefore share that digest. This record prepares a versioned
binding without changing historical scopes, hashes or qualification outcomes.
It is not a start-gating decision.

## Context and drivers

Research-state rows do not contain the catalog's actual requirement text. The
binding must join the canonical layer by catalog and layer ID and retain its
exact text. A missing or duplicate identity is an error, not a reason to reuse
another layer's text. The trading owner separately corrects the four research
layers whose wording is inappropriate; this migration edits none of those rows.

The ledger's append-only check requires an unchanged root policy/schema and an
unchanged historical prefix. Replacing old digests with today's text would
misrepresent what earlier workers evaluated and break recorded field bindings.

## Proposed binding

Add an optional `requirement_binding` snapshot with version 2, catalog/layer
identity, exact requirement text, `requirement_hash` and `legacy_hash`.
The new digest uses the repository's existing canonical JSON serialization and
SHA256 over exactly `{binding_version: 2, identity: {catalog, layer_id},
requirement_text}`. Text is retained without whitespace normalization. The old digest remains the
legacy value; the existing `requirement_sha256` field and algorithm remain
compatible with previously frozen inputs and discovery returns.

The existing `--scope` output adds a `requirement_bindings` map beside its
unchanged `requirement_sha256` map. A future result may carry an explicit
per-layer snapshot. The ledger's root schema version, policy, historical chain
and original records stay unchanged. The catalog's root identity supplies a
layer's catalog when that field is absent; a conflicting explicit identity is
rejected.

The new snapshot is frozen before evaluation and validated against the original
retained discovery/source data. Append does not reconstruct a strong binding
from current text for an older run. New field digests include the optional
binding when present; absent bindings retain the exact earlier digest formula.
Both original and expanded field verification remain in place.

Historical records remain byte-unchanged and verify through the legacy path.
Legacy clean counts are labelled as legacy scope, not as proof that requirement
text was bound. Report metadata distinguishes current and captured snapshots;
current versioned metadata cannot retroactively qualify legacy or mixed counts.
The skills modality keeps its original lifecycle/requirement/overturn formula;
any versioned skills snapshot is additional rather than a replacement.

## Producer boundary and open item

The declaration API, future append/check and report paths are in this migration.
Actual model-run producers must explicitly carry the same snapshot through
`build_inputs.py`, `convert.py` and `build_args.py` before a future sweep claims
text-bound evidence. Those live harness paths need owner custody coordination;
the migration does not silently claim their activation or run a new sweep.
The command center reviews the change, and readiness-runner records its dated
addendum. No old observation or decided text is rewritten.

## Alternatives considered

- Recompute existing records or replace the legacy formula: rejected because
  historical inputs and field hashes must remain unchanged.
- Hash only the current text without its identity: rejected because unrelated
  layers can legitimately share wording and still represent different scopes.
- Add a digest that is never carried or validated: insufficient. The snapshot
  needs explicit freeze, reference, verification and producer propagation.
- Introduce another ledger, runner or dependency: unnecessary; extend the
  maintained canonical serialization, checker and append-only schema.

## Validation and overturn comparison

Tests must distinguish different text and identity despite equal legacy
digests, reject malformed/tampered versioned snapshots, preserve frozen scope
after current text changes, and verify every existing record through the legacy
path with the original chain intact. These are synthetic/structural checks,
not a new research result or upstream acceptance.

Reopen if the versioned payload omits another meaningful scope input, cannot
represent a supported requirement modality, or cannot pass through the native
producer without losing original and expanded source verification. Compare
exact frozen-source recovery and deterministic counterexamples, preserving
every prior scope and failed outcome.

## SOTA sources

- `seathatflowsinourveins/native-agent-stack@bed695bef593aa5a846611bb6cb4cf8ee2286760:scripts/saturation_ledger.py:122-132,524-531,575-580,1139-1162,1341-1346,1626-1708`: existing canonical field hashes, legacy requirement binding, original-source verification and append-only constraints.
- At that pin, `catalogs/saturation/ledger.schema.json:77-85`, `catalogs/saturation/README.md:29-95`, `catalogs/landscape/foundation.json:7-10` and `catalogs/landscape/us-equities.json:7-11`: native schema, historical evidence semantics and canonical requirement identities/text.
- At that pin, `tools/sota-convergence/landscape-sweep/build_inputs.py:393,638-645`, `convert.py:369,378,577` and `build_args.py:544`: explicit frozen-input and producer propagation seams.
- At that pin, `tests/test_saturation_ledger.py:443,743,764,962`: historical-prefix, frozen-scope and owner-boundary regression seams.
