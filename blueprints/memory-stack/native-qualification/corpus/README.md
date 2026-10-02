# Synthetic qualification corpus

This package has 12 development cases and 60 sealed authored holdout cases. It
contains fictional operational records, not real user histories. It qualifies
local integration behavior only; see [the preregistration](../PREREGISTRATION.md)
for exposure limits and the broader gates.

Development inputs are `dev/cases.jsonl` and `dev/sources.json`. The source registry
is a JSON array; its paths are relative to that registry's directory. The gold
records and registry support fields are **scorer-only**. Only source Markdown
documents and the query `input` may enter a backend/model. Ingest all documents in
the selected split; the case's `source_ids` describe oracle scope, not a retrieval
filter. Registry facts must never be presented as backend evidence.

Each case contains `case_id`, `scenario_id`, `split`, `category`, `input`,
`query_time`, `source_ids`, `expected` and `provenance`. `expected` has
`answer_type`, `required_facts`, `forbidden_facts`, `citation_source_ids` and
`abstention_reason`. A fact is `{fact_id, value, source_ids}` and its value is a JSON
scalar. All listed required citation sources must be supplied. Forbidden facts
may represent unsupported fabricated values and need not be supported by their
listed sources. An abstention has no required facts, an explicit reason and one
or more source citations. Source IDs and timestamps are visible in the Markdown;
`supported_facts` and `supports_abstention` are only in the private scorer registry.

The model answer contract is:

```json
{
  "answer": {
    "answer_type": "answer",
    "facts": {"fact_key": "JSON scalar"},
    "as_of": "ISO-8601 query_time",
    "abstention_reason": null
  },
  "citations": [
    {"fact_id": "fact_key", "source_id": "source-id", "source_sha256": "64 hex characters"}
  ]
}
```

The model emits only citation `fact_id` and `source_id`. The adapter attaches
`source_sha256` from the original retrieved source manifest after generation;
do not ask a model to calculate SHA-256. Retrieved evidence must retain its source
ID, and the prompt must include this answer schema and allowed reason enum.

For abstention, use `answer_type="abstain"`, an empty `facts` mapping and the exact
supported `abstention_reason`. Use citation `fact_id="$abstention"`. Allowed reasons
in this fixture are `missing_evidence`, `false_premise`, `future_evidence`,
`unresolved_conflict`, `scope_mismatch` and `redacted_value`. Cite the original
document hash; a transformed or backend-generated text hash does not establish
original source provenance. The evaluator's per-run result envelope adds arm,
mode and runtime metadata to this answer; it is not part of query evidence.

## Sealed holdout release

`holdout.sealed.tar.gz.b64` (ASCII base64 encoding of a tar.gz archive) contains `cases.jsonl`, `sources.json` and source Markdown
files. `holdout-seal.json` and the parent `corpus-manifest.json` give the archive
and member SHA-256 hashes, counts and exposure state. The archive is deterministic:
lexically sorted paths, fixed gzip/tar timestamps and normalized member ownership.
It is not encrypted. The author is exposed; coordinator and tuning-executor
exposure need attestation. Do not describe this as unseen because it is compressed.

1. During tuning, load only `dev/`. Exclude the archive and authoring tool arguments
   from tuning-executor access, search, logs and context. Do not inspect member
   contents, queries, golds or detailed holdout failures.
2. Before release, hash the encoded archive and verify its decoded archive-byte hash
   without decoding tar members, compare with the
   manifest, and complete the configuration-freeze receipt and exposure attestations.
   If technical isolation is unproved, retain the exploratory synthetic label.
3. The designated evaluator alone base64-decodes and releases the archive into a unique per-run
   directory. Reject absolute member paths, `..`, links and non-regular members;
   require the exact sealed member inventory before extraction. Verify each member
   hash before loading. Keep gold and source registry out of model inputs.
4. Give every arm the same original Markdown bytes with source IDs/hash provenance.
   Score against the independently loaded gold after responses are fixed. Record
   actual loading/release time, freeze digest and `holdout_exposed` in run metadata.
5. Any premature content read sets the relevant exposure flag true permanently
   for that trial. It is not repaired by resealing identical data. Any source or
   oracle edit creates a new freeze ID, seal and exploratory experiment.

No trial has been run by creating these artifacts. The validation receipt proves
only counts, references, disjointness, timestamps and byte hashes. A real externally
authored holdout remains necessary for broader claims unless technical non-exposure
of the tuning executor is independently established.
