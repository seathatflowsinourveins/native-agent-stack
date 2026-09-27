# RTK coverage study: sanitized publication (2026-09-27)

This publishes the aggregate results of the **2026-09-26 historical study**
requested by the full-save plan, PR-EV / section 4.1. Publication is not a new
replay, model run, installation or host qualification. The measured window is
2026-09-24T03:50:41Z through 2026-09-26T18:38Z.

## Records

| File | Evidence class | What it shows | What it does not establish |
| --- | --- | --- | --- |
| [tables.txt](tables.txt) | Historical local measurement; local replay/integration | Recorded decisions for 59,041 calls, replay totals for two RTK revisions and a no-config control, and aggregate classifications for 611 sampled misses. | New execution, provider token savings, or the later M-R1 eligible-part gate. |
| [frame-summary.txt](frame-summary.txt) | Historical local measurement | Native discover classifications grouped by recorded hook decision: 15,623 missed and 25,954 covered supported parts. | That each part in a rewritten call was rewritten; an eligible-command denominator; any private command or transcript. |
| [exactness.out](exactness.out) | Historical synthetic fixtures; local integration | Captured native-versus-RTK stdout sizes, digests, exit statuses, branch/log differences and dry-run hook decisions for T1–T7. | Unchanged upstream test-suite acceptance, a rerun on this host, or lossless behavior for arbitrary commands. |
| [METHOD.md](METHOD.md) | Method/provenance and dated interpretation erratum | Sampling, versions, evidence boundaries, sanitization, source fingerprints and primary upstream references. | Access to the private sample or independent regeneration of the historical population. |

The `ask` bucket records the historical hook rewrite decision. The 62.4%
discover ratio is **not M-R1**: discover carries a whole-call decision into its
command-part classification. The dated erratum in METHOD.md records this
interpretation limit while preserving the original aggregate numbers.

The publisher checked the source tags and relevant implementation on
2026-09-27, and checked the local installed client's version/help. No private
sample commands, source transcripts, hook database rows or credential stores
were published or reread for a new population study. The unfiltered
`unsupported top` list was removed because its grouping keys contained private
sample fragments. The fixture's local recall handle was replaced with
`<omitted>`; its captured counts, digests, exit statuses and synthetic filenames
remain unchanged.

## Sources

- [rtk-ai/rtk v0.50.0](https://github.com/rtk-ai/rtk/tree/v0.50.0), commit
  `1d87b8e719ce0a50c223cd93ca64dd16921f9aec`: native
  [hook check](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs),
  [hook decision](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs),
  [discover](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/mod.rs) and
  [registry](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs).
- [rtk-ai/rtk dev-0.51.0-rc.467](https://github.com/rtk-ai/rtk/tree/dev-0.51.0-rc.467),
  commit `a89a31494670fcec8ffa20d939dd94c64bd998fb`: historical comparison
  revision, never a claim of stable adoption.
- Repository [acceptance evidence policy](../../../docs/acceptance-evidence-policy.md)
  and the records-table pattern in
  [RTK exclusion evidence](../rtk-exclude-widen-20260926/README.md).

Offline publication checks are in
[test_token_full_save_evidence.py](../../../tests/test_token_full_save_evidence.py).
They validate the receipts, not native RTK execution or the confidential corpus.
