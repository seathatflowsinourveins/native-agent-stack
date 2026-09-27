# A17: the confirmatory rerun R1 is superseded by S3 (PROPOSED, 2026-09-27)

**Status: proposed, not in effect.** It takes effect only when the user confirms it at the freeze of the S3 preregistration (`blueprints/memory-layer-s3/PREREGISTRATION.md`, sections 9 and 12, PR #390). Until then nothing runs under either protocol.

This amendment continues the memory-stack protocol's own lineage:
- A1–A16.3 live in the frozen [`PREREGISTRATION.md`](PREREGISTRATION.md) (v3, #380) and [`v4/PREREGISTRATION.md`](v4/PREREGISTRATION.md) (v4, #386).
- Frozen text is never edited, so A17 is a new file.

## What A17 was to be

VelaNext was retired, so the confirmatory rerun R1 needed another host and a new amendment naming it before any run (`docs/decisions/2026-09-25-retire-vela-velanext.md:36-44`). The workstation `nativestack-5975wx-20260925` took R1 as A17 (`docs/decisions/2026-09-25-workstation-sota-refresh.md:542-546`; issue #274). No A17 text was ever written before this file, and no session held a draft (checked on 2026-09-27 with the sessions that had owned it).

## The amendment

1. **Host.** R1's host would have been the workstation `nativestack-5975wx-20260925`.
2. **R1 is not run under A1–A16.3.** The durable-memory decision on both hosts is instead made by the S3 head-to-head preregistration, which names its own reference, arms, statistics and decision rule.
3. **No look is spent.** No confirmatory arm of A1–A16.3 has run on any host. No C3′, C4′, C4 or D2h result exists (`docs/decisions/2026-09-25-retire-vela-velanext.md:43-44`; `catalogs/foundation/memory-stack-20260925.json:1318`; `docs/decisions/2026-09-27-mac-single-writer-staged.md:48`). This amendment therefore selects nothing after seeing results.
4. **Carried into S3:**
   - The user's 2026-09-25 decision to use official ai-memory **v2.4.0** as the control (issue #274; `docs/decisions/2026-09-25-workstation-sota-refresh.md:228`) becomes S3's reference, as C4′ with C3′ as a diagnostic.
   - This protocol's C3, C4 and D2h configurations define S3's C3′, C4′ and agentmemory arm (v4 `lme_harness.py:759-784,1562-1575,1618-1619`).
   - The user's 2026-09-27 decision that the memory layer is chosen on merit and the winner supersedes ai-memory (PR #383) is S3's decision.
5. **Not carried into S3:**
   - this protocol's family α values (0.0333, 0.0167), its +5 pp/−2 pp rule and its one-look-per-family rule;
   - the v4 = v3 reproduction gate;
   - the VelaNext-only drivers and summarizer.

   S3's statistics, gates and new isolated runner replace them.
6. **Descriptive record.** The historical Mac C3 (0.570, build `19b6429`) and all earlier Mac results stay descriptive, as A15.2 already requires.
7. **Frozen files stay frozen.** The v3 and v4 files remain the provenance and adapter source S3 reads. They are never edited and never run on a shared host (v4 `README.md:21-24,86-93`).
