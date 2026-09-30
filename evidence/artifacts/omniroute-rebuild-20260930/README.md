# OmniRoute rebuild on release/v3.8.51 2f42a9ac1 and token-save settings, 2026-09-30

Record of what runs on the two OmniRoute gateways of the NativeStack workstation after 2026-09-30T00:02Z and how it got
there. The decision, with alternatives and what would overturn it, is
[`docs/decisions/2026-09-30-omniroute-rebuild.md`](../../../docs/decisions/2026-09-30-omniroute-rebuild.md). Claims and
their evidence classes are in `receipt.json`; a claim carries the class or classes that apply and a claim resting on two names both:

- unchanged upstream checks (upstream's own scripts on our builds),
- our integration checks (smoke, targeted tests, failure classification, applier read-backs, probes),
- live model calls (one synthetic payload each), synthetic fixtures (one payload per line, not savings figures),
- source review and registry/API reads.

| File | What it is | Class |
| --- | --- | --- |
| `receipt.json` | structured record: units, switch, settings, claims, residuals | index |
| `qualification-extract.json` | build and check results, the two suites' failing names and the classification, probes, token counts | our checks and upstream checks |
| `host-readback-20260930.json` | route digests before the delta (`snapshot_gateways.py`), and after it the owner record (`gateway_record.py`: unit hashes, process identity, build ids, route digests; exec_main_start in UTC), all digests full length; the after record is the one the Gate A owner is said to have frozen | our check |
| `checks/` | `recorded-outputs.txt`: the applier's checks as printed during the apply, transcribed with the commands as typed, and two fresh read-only runs (the delta verifies; the owner record equals the published one on every path but `taken_utc`); `effective-plan-20260930.json`: the gateway's plan resolver on the live settings; `lite-whitespace-probe-20260930.json`: what the headerless lane does to code-bearing text; `real-codex-bodies-lane-probe-20260930.json`: the headerless and lossy lanes on eight real Codex request bodies (counts only) | our checks |
| `omniroute.service`, `omniroute-fw.service` | the installed unit files (they use `%h`, hold no secret; sha256 prefixes 899e4fdb06775216 and fbdace7eeec524e3) | installed state |
| `PLAN.md` | the planner's document for the nine-step plan (Opus, 2026-09-29); its headerless-lane result (`[ccr]`, output style) is the superseded first plan, not the state after the delta | plan |
| `plan.json.txt` | steps T01-T09 of the plan file as it stands: it was edited after the apply by a stopped workflow stage (its drafted T10-T15 are excluded and its `post_apply` key is dropped), so the write values cannot be tied to what ran; use the apply logs and `checks/` for what was checked | plan |
| `plan-delta.json.txt` | the applied T10 delta, exactly; its title says 'upstream defaults', which it is not: see the decision record's table for what departs from upstream's shipped state | plan |
| `apply-logs/` | values-free per-step records of the dry runs and applies (precondition and read-back results with ok flags) and the route digests around them | our check |
| `scripts/*.txt` | our integration scripts as they stand, not as they ran at 00:06Z (see Provenance): `gateway_apply.py` (contract v1 executor, the ALLOWED_PSD guard accepts the non-secret `$.cache` path), `switch_gateways.py`, `backup_stores.py`, `snapshot_gateways.py`, `post_apply_checks.py`, `test_gateway_apply.py` (20 offline tests), and the probes `preview_probe.py`, `codex_lane_probe.ts`, `real_bodies_probe.ts`, `gatewayPath.ts` (the S1 screen's mirror of chatCore's pre-translation step), `plan_table.ts`, `read_live_settings.py`, `blocknet.mjs`, `run.sh` (the harness that resolves the effective plan offline with the network blocked), `compare_record.py` and `installed_check.py` | our tools, not upstream |

**Provenance of the operation scripts.** T01-T09 (00:05:57Z-00:06:17Z) ran through `gateway_apply.py`, `plan.json` and `post_apply_checks.py` as they stood at
00:05:53Z; those versions are **not retained** (no script digest was logged). The published copies are later text: a design workflow's fix stage rewrote
`gateway_apply.py` at 00:33:23Z and edited it five times from 00:43:06Z to 00:43:19Z, rewrote `post_apply_checks.py` at 00:40:42Z and edited `plan.json` and
`test_gateway_apply.py` until 00:45:44Z. **T10, the delta (dry run 00:43:38Z, apply 00:43:52Z), ran through that unreviewed edit of the applier**; the offline module ran
on it at 00:46:17Z (20 tests, OK). `plan-delta.json` was built by the coordinator at 00:43:32Z from T09's step and the pi-practice session's
`delta-20260930-upstream-defaults.json`. The read-backs against the consuming gateway, not the scripts' text, are the evidence for T01-T10.

The owner record printed for the Gate A owner is [`tools/omniroute/gateway_record.py`](../../../tools/omniroute/gateway_record.py)
(read-only, schema `omniroute-gateway-record/2`), sha256
`d5cfcfbd61bcfcb1808270deab7e793d4021c8dd0c3079fe5ff71ee723ab46e6`. Internal connection and node identifiers are
shortened to eight hex characters. No credential value, host path or user name is stored.

Known limits: see `receipt.json` `residuals`. This record is one workstation's evidence, not another host's status.
