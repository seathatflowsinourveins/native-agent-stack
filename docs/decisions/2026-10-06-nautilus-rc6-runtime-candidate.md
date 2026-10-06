---
status: proposed
date: 2026-10-06
decision-makers: [5f, command center]
consulted: [ns2604-coop, grand-catalog, readiness-runner]
informed: [trading lane]
review_by: 2027-01-04
---

# Qualify the clean rc6 runtime candidate without changing the destination

## Context and Problem Statement

The selected destination remains NautilusTrader 2.0.0rc5. The vendor's clean
rc6 prerelease includes the routed-account risk-engine fix for #4946. Its fee
API requires explicit venue models. Candidate execution must preserve the
retained research method, isolate the parallel rc5 runtime and distinguish
offline runtime observations from historical-case and broker qualification.

## Decision Drivers

- Use the maintainer's released wheel and supported installation/example.
- Retain uv 0.12.17, CPython 3.12.3 and the October 6 04:00Z cutoff.
- Preserve immutable inputs, economic oracles and preregistration predicates.
- Keep the canonical pin and C1–C4 order decision with 5f.

## Considered Options

1. Retain rc5 and its recorded acceptance; it does not contain the #4946 fix.
2. Qualify the vendor rc6 candidate in an isolated HOME and submit the observations.
3. Patch or rebuild a development tree; a clean released candidate already exists.

## Decision Outcome

Prepare option 2 for review, using the vendor wheel and unchanged rc6 quickstart.
This record does not select a destination pin. The explicit clean-release
cooldown exception is recorded in the October3 decision cited below; elapsed
time alone does not establish quality or acceptance.

The native co-op executor ran installation and acceptance on NativeStack2604
with HOME overridden after mise and Docker's documented rootless endpoint.
Installation exited 0; all 24 offline recipe checks returned PASS. The four input
files were byte-identical before/after. The earlier Codex-tool attempt exited64
because distribution metadata was absent; it remains a separate observation.
The [receipt](../../evidence/receipts/nautilus-rc6-runtime-2604-20261006.json)
retains command scope, times, hashes and individual evidence classes. Independent
publication review remains pending. Local probes and source review do not
become unchanged upstream tests or broker acceptance.

The official quickstart's executable delta is the fee-model import and explicit
zero rates. Its Python prerequisite prose also changes to 3.12–3.14; the retained
3.12.3 interpreter stays within that range. Only A14's runtime version/source/hash
cells change; HOME-derived paths, isolation, sync vector, other direct pins,
image/adapter pins and the cutoff remain unchanged.

The J2 contract identifies SPY one_zero, AAPL baseline and AAPL fee_slippage_stress
at ecfa11276. Their retained inputs and launcher mount route remain unavailable.
Their strict rc5 guards and SPY's sealed null-fee mapping also need 5f's binding
ruling before an rc6 rerun. A17 retains those files unchanged; a concrete
candidate proposal belongs only in the PR description. No case result is inferred
from the runtime checks. Open issues #5007, #5057 and #5060 remain recorded.

## Consequences

The isolated 1.4G HOME stays for 5f's review; task TMPDIR is removed. Native
runtime observations are reusable only while their input hashes match. A
changed runtime input requires a new scoped qualification. A changed sealed
case binding requires the owner's ruling and independent review, not a relaxed
comparator. The candidate remains provisional until those reviews; the selected
runtime-target, historical receipts and paper permissions are unchanged.

## Validation and Reconsideration

Lock resolution/check and all 12 recipe consistency tests passed. The receipt
retains the 24 returned native check rows and the failed attempt. Repository
validation checks consistency only. Reconsider the candidate if vendor defects,
native failures, case/oracle differences or 5f's risk/order checks reject it;
retain rc5 until an explicit destination decision is recorded.

## Sources

- [Vendor rc6 release](https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc6),
  `nautechsystems/nautilus_trader@7b766f8825b2539c5b2ac1375e9d97b41c509edb:RELEASES.md:73,145–148,259`.
- [Fix ancestry comparison](https://github.com/nautechsystems/nautilus_trader/compare/ed6fc8bf47fd37dda97d63b9b2df160719ee2bac...v2.0.0rc6);
  samefix...v2.0.0rc5 isdiverged. Taggedquickstart: `docs/getting_started/quickstart.py:131,221`.
- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:blueprints/us-equities/runtime-2604/install-trading-2604.sh:91–101,164,223–231`;
  `accept-trading-2604.sh:14,21`; `sync-trading-2604.sh:8–21`.
- The samepin's `docs/acceptance-evidence-policy.md:26–33`;
  `docs/decisions/2026-10-03-omniroute-3851-pin.md:14–17`;
  `engine-nautilus/acceptance-plan.md:53–95,128–178` under the trading blueprint.
- [Docker rootless client setting](https://docs.docker.com/engine/security/rootless/).
- Private A14/A15/A16/A17 and native run `coord:j4-rc6-hostrun-20261006T000057Z/`;
  proof hashes are retained in the public sanitized artifact.
- [MADR 4.0.0 template](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md).
