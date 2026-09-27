# OmniRoute feature resolution: records (2026-09-27)

This directory holds the research records behind [`docs/decisions/2026-09-27-omniroute-feature-resolution.md`](../../../docs/decisions/2026-09-27-omniroute-feature-resolution.md).
The build under review is `release/v3.8.51` `a58000c7` + #14904 + #13788 (BUILD_SHA `dd6e9607e`), served on the workstation at `127.0.0.1:20128`.

Paths are masked: the home directory appears as `~` and the session scratchpad as `$SCRATCH`. Emails and UUIDs are removed. No packet, call-log row, credential or transcript is kept.

## Files and their evidence class

| File | Class | What it is |
|---|---|---|
| `omniroute-feature-verdict.json` | deterministic merge (final) | all records merged by `scripts/build_verdict.py.txt`, with no model call: 55 features with state, config, A/B design, hold reason, overturn, sources, lineage and the measured top actions |
| `omniroute-feature-verdict.interim.json` | deterministic merge | the version the page of `token-efficiency-evidence-cards` was published from: the same states, 5 top actions |
| `records/claude-dives-round1.json` | model research (Claude Opus 5.5) | 32 proposals: C00–C20, K01–K05, R01–R04, D01, D03 |
| `records/gpt6-dive-H1…H7.json` | model research (GPT-6 astra, max) | 23 proposals: D02, D04–D12, S01–S07, L01–L04, O01, O02 |
| `records/gpt6-refutations-G1-G5.json`, `records/gpt6-refute-RH*.json` | adversarial model review (GPT-6 astra, max) | upheld, corrected or refuted, with material findings and citations; RH6 and RH7 ran as `-r2` after a Codex quiet window |
| `gpt6-job-usage.json` | provider usage (Codex CLI report) | per-job usage, model, effort and timing of every GPT-6 job on the lane; jobs stopped before codex started are marked |
| `phase0-attempt1-child-usage.json` | provider usage (Claude) | the failed first attempt: per-child usage and tool lanes from `examples/claude-native/workflows/child-usage.mjs` |
| `probes/probe-max*.jsonl` | live gateway probe | chat/completions with and without `-max` and tools; the effort read-back is quoted in the decision record |
| `gateway-snapshot-redacted.json` | live read (GET) | the gateway's settings, feature flags, cache, compression and telemetry routes at settings revision 16, redacted; each feature-flag entry's `key` field is renamed `flag`, because the secret scanner's generic-api-key rule fires on long flag names |
| `own-reports-before.json` | live read (GET, whitelist) | aggregates from the gateway's own reports: cache, cache-health, compression analytics, usage summary, version, settings |
| `scripts/*.txt` | tools | `snap.py` (redacted snapshot), `capture_own_reports.py` (whitelist capture), `build_packets.py` (evidence packets), `build_verdict.py` (deterministic merge), `probe_max.py`, `stage_records.py` (this staging) |
| `prompts/` | inputs | the shared context, every job prompt and every strict output schema |

## How to re-verify

1. **Packets.** Re-derive the evidence packets:

   ```
   python3 scripts/build_packets.py.txt <dives.json> '<groups json>' <outdir>
   ```

   Run it against a checkout of the build tree (`a58000c7` plus the two PR heads), then compare the cited lines.
2. **Merge.** Re-run the deterministic merge:

   ```
   python3 scripts/build_verdict.py.txt <records dir> <lane dir> out.json
   ```

   The states must equal `omniroute-feature-verdict.interim.json`.
3. **Live reads.** Re-run `scripts/capture_own_reports.py.txt` and `scripts/probe_max.py.txt` against a live gateway. Each rerun is a new observation, not a replay.
