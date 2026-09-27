# GPT-6 family tiering: the frozen run's results (2026-09-27)

- Preregistration: [`gpt6-family-tiering-20260926`](../../../blueprints/convergence-practice/gpt6-family-tiering-20260926/README.md),
  frozen on 2026-09-26 before any provider call. `plan.json` SHA-256 `455e38df43e6bcc9e6e89c5e9399657f93a0a8cebcbf779c1d22c28afe370532`.
- Host: `nativestack-5975wx-20260925`. Run: 2026-09-27, 07:09:02Z to 07:28:28Z, one run per arm, from a separate
  worktree at `origin/main` `50b9579f6722`.
- Machine-readable records: [`decision.json`](decision.json) (the `analyze.py` output, copied unchanged) and
  [`run-record.json`](run-record.json).

**Evidence class: live provider execution.** This is the preregistration's "later run" class: the hosted GPT-6
models ran on this host through the native Codex sign-in, one run per arm. Token counts are Codex's own
`turn.completed` counters. Wall times are shared-host, shared-account observations. The rerun of `analyze.py` and
the cross-check of the call records re-verify the analysis and the bookkeeping, not the provider's behaviour. No
upstream test and no synthetic fixture is part of this result.

## Decision

`final: true`, outcome `route_mechanical_extraction`: **S1, `gpt-6-sol` at `medium` effort.**

- All six arms were routable under the frozen rule.
- Ranked by mean billed tokens per filing, the candidates are S1, S0, L1, L0 and A1. The first four are below A0's
  1,852.3; A1 is above it.
- S1 is the cheapest: 1,620.0 billed tokens per filing, 12.5% below A0. Its micro-F1 is 0.9935 against A0's 0.9942,
  with a paired-bootstrap 95% lower bound of −0.0037 (the margin is −0.02). JSON-valid is 1.000, and all 25 batches
  completed.

### Scope of the decision

- **Covered:** mechanical, deterministically scored 8-K item extraction. That is the frozen task: li26's 360
  filings of 2020-03-02 in the 25 frozen batches of up to 15 filings, with filer-declared header `ITEMS` as labels
  and li26's scorers and 16,000-character cap. The calls went through the frozen, tool-free `codex exec` command on
  `codex-cli 0.157.1`, on this host, one run per arm on one day.
- **Untested:** generalization to any other stage. That includes other extraction tasks or labels, other batch
  sizes, days or Codex versions, stages that let the model use tools, and every review, research, synthesis or other
  judgment stage.
- **Unchanged:** judgment roles stay on `gpt-6-astra` at `max` effort. This change routes nothing and edits no
  stage's command. A later routing change names `gpt-6-sol` and `medium` in each qualifying mechanical stage's own
  command. Rollback restores `-m gpt-6-astra -c model_reasoning_effort="max"` there (the `rollback` field of the
  preregistration's `experiment.json`).

## Quality per arm

From `decision.json`, over all 360 filings.

| Arm | Model | Effort | Micro-F1 | Macro-F1 | Exact match | JSON-valid | Bootstrap vs A0: 95% lower (point) | Calls |
|---|---|---|---|---|---|---|---|---|
| A0 | `gpt-6-astra` | max | 0.9942 | 0.9970 | 0.9750 | 1.000 | control | 25 ok |
| A1 | `gpt-6-astra` | medium | 0.9942 | 0.9970 | 0.9750 | 1.000 | 0.0000 (0.0000) | 25 ok |
| S0 | `gpt-6-sol` | max | 0.9948 | 0.9975 | 0.9778 | 1.000 | −0.0013 (+0.0006) | 25 ok |
| S1 | `gpt-6-sol` | medium | 0.9935 | 0.9938 | 0.9750 | 1.000 | −0.0037 (−0.0006) | 25 ok |
| L0 | `gpt-6-luna` | max | 0.9923 | 0.9900 | 0.9722 | 1.000 | −0.0060 (−0.0019) | 25 ok |
| L1 | `gpt-6-luna` | medium | 0.9878 | 0.9718 | 0.9667 | 1.000 | −0.0147 (−0.0064) | 25 ok, 1 failed (`tool_use`) |

- A1's paired-bootstrap interval is exactly zero: its micro-F1 equals A0's in all 10,000 resamples.
- Macro-F1 covers the 12 codes with at least five labelled filings. S1's per-code F1 differs from A0's by more than
  0.001 on two codes: lower on 2.01 (0.957 against 1.000) and higher on 8.01 (0.989 against 0.983). L1 is lower on
  seven of the twelve codes, down to 0.880 on 2.01.

## Tokens and time per arm

Means per filing are each arm's totals over every call, divided by 360. Billed tokens are input minus cached input
plus output. Codex's output already includes reasoning ([`docs/token-practice.md`](../../../docs/token-practice.md)).

| Arm | Billed | vs A0 | Input | Cached input | Output incl. reasoning | Reasoning | Median ok call (s) | Arm elapsed (s) |
|---|---|---|---|---|---|---|---|---|
| A0 | 1,852.3 | – | 1,856.3 | 72.5 | 68.5 | 42.6 | 27.4 | 282.7 |
| A1 | 1,883.1 | +1.7% | 1,856.2 | 0.0 | 26.9 | 1.1 | 15.7 | 132.9 |
| S0 | 1,656.9 | −10.5% | 1,825.1 | 234.0 | 65.7 | 39.9 | 15.8 | 186.0 |
| S1 | 1,620.0 | −12.5% | 1,825.0 | 241.8 | 36.7 | 10.8 | 13.0 | 149.6 |
| L0 | 1,791.4 | −3.3% | 1,812.7 | 147.2 | 125.9 | 100.0 | 28.7 | 318.3 |
| L1 | 1,732.7 | −6.5% | 1,947.8 | 244.6 | 29.5 | 2.7 | 10.1 | 95.8 |

Every call reported usage, so every arm's usage is complete. No call reported cached input above input or reasoning
above output. Together the six arms made 151 calls: 4,004,329 input tokens (338,432 of them cached) and 127,155
output tokens (70,942 of them reasoning), or 3,793,052 billed tokens. Each call is counted once.

### Reading the cost numbers

- The frozen cost credits cached input, and cache hits are the provider's. The plan does not control them, and they
  varied by arm. A1 used the same model and the same prompts as A0 but got no cached input in 25 calls. It therefore
  ranks above A0 on billed tokens, although its input plus output (1,883.1 per filing) is below A0's (1,924.8).
- S1 is 232.3 billed tokens per filing below A0. Of that, 169.2 is more cached input, 31.8 is less output and 31.3
  is less input. Without the cache credit, counting input plus output per filing, S1 is still the lowest of the six
  arms: 1,861.8 against A0's 1,924.8 (−3.3%). This view is arithmetic on the decision's own aggregates. It is not
  the frozen rule and does not change the decision.
- L1's input per filing includes the failed attempt's 48,639 input tokens, because the plan counts every call that
  reported usage.
- Wall time only breaks cost ties, and the decision needed none.

## Calls and the one retry

- There were 151 calls: 150 `ok` and 1 `failed` (`tool_use`). No call was `limit`, `unavailable`, `interrupted`,
  `abandoned` or timed out. Every call reported usage and left a session record, and no item type outside the plan
  appeared.
- L1, batch `b016`, attempt 1 exited 0 with a valid reply. Its session record held one `custom_tool_call` and its
  output, while the `--json` stream showed only an `agent_message`. That is the signature of the isolation probe's
  scripted code-mode `exec` cells ([`results.json`](../../../blueprints/convergence-practice/gpt6-family-tiering-20260926/isolation-probe/results.json),
  cases `isolated-code-mode` and `isolated-plain-luna`). The tool's name and arguments were not read.
- The plan's session-record check failed that call as `tool_use`, so its reply was not scored. Its usage counts in
  L1's totals, and the batch's single retry (attempt 2) was `ok`. The `--json` stream alone would have passed this
  call, and the session-record check exists for exactly this case.

## Run record

- **Checkout and checks.** The coordinator ran from a separate worktree at `origin/main` `50b9579f6722`.
  `run_arm.py verify-frozen` printed `frozen inputs verified`. `run_arm.py layout` printed 25 batches, 360 filings
  and `layout_sha256` `1db33e0f5f9c6328eab7c691e69c175b6084bedfe16a96e81fecacf33cf10d15`, with `matches_plan: true`.
- **Launch.** At 2026-09-27T07:09:02Z the coordinator started a transient `systemd --user` unit running README step
  2's loop (A0 A1 S0 S1 L0 L1, stopping on the first non-zero exit), with the native Codex sign-in. Every arm exited
  0 on its first run, and the loop ended at 07:28:28Z.

| Arm | Started (UTC) | Finished (UTC) | Elapsed (s) | Calls | Exit |
|---|---|---|---|---|---|
| A0 | 07:09:02.343 | 07:13:45.011 | 282.668 | 25 | 0 |
| A1 | 07:13:45.162 | 07:15:58.107 | 132.945 | 25 | 0 |
| S0 | 07:15:58.337 | 07:19:04.315 | 185.978 | 25 | 0 |
| S1 | 07:19:04.469 | 07:21:34.100 | 149.631 | 25 | 0 |
| L0 | 07:21:34.249 | 07:26:52.507 | 318.257 | 25 | 0 |
| L1 | 07:26:52.650 | 07:28:28.460 | 95.810 | 26 | 0 |

- **Versions.** Every arm's run record and identity show `codex-cli 0.157.1`. The run does not store the Python
  version; the rerun of `analyze.py` used Python 3.13.15. Only model slugs were recorded, with no provider-side model
  revision.
- **Deviation: the slot lock directory.** README step 2 names the host's shared Codex slot directory. The
  coordinator reported that none existed at launch and that the landscape sweep's GPT-6 lane runs through OmniRoute
  with its own work-dir locks. At this checkout, the sweep runner's slot pool defaults to its own `<work-dir>/locks`
  (`tools/sota-convergence/landscape-sweep/codex_job.py`, docstring and `settings()`). The coordinator created a
  dedicated owner-only directory holding `slot-1` to `slot-3` and passed it as `--lock-dir`.
  - The cap of three bounded the tiering's own calls: slots 1, 2 and 3 took 51, 49 and 51 calls, and each arm's
    summed slot wait was at most 0.002 s. It was not shared with other Codex jobs on the host.
  - Token counts are per-call counters, and scoring reads each call's own reply, so neither depends on the pool.
    Only wall time could, and the decision used none.
- **Quota context.** The coordinator ran `scripts/codex_quota.py --json` at launch: the `codex` bucket's weekly
  window was at 3% used, on plan type `pro`. That is the only reading. No per-arm readings were taken, so `analyze.py`
  ran without `--quota-context` and the decision's `quota_context` is `null`. Other sessions share the account, so
  the percentage is context only and never enters the rule.

## Re-verification

Checks made for this record:

1. `run_arm.py verify-frozen` on this change's checkout printed `frozen inputs verified`. The only preregistration
   file this change edits is its README, which no frozen hash covers.
2. `run_arm.py layout` printed the aggregates of the coordinator's pre-run check (25 batches, 360 filings, the same
   `layout_sha256`, `matches_plan: true`) and the preregistration's prompt sizes (12,088 to 106,870 bytes, 2,016,724
   in total).
3. `analyze.py`, rerun at 07:42:10Z from a second worktree at `50b9579f6722`, produced a byte-identical decision
   (SHA-256 `555ed71c29a8a33070d9a185b65d69986e31a7955f1ed49b944224414b2a40ea`).
4. Summed from each attempt's `call.json`, per-arm usage equals the decision's totals for all six arms, and the
   outcome counts agree with the decision's.

To repeat the analysis on this host later, the private state directory and li26's acquisition must still exist:

```sh
LI26_ACQ=~/.local/state/native-agent-stack/local-inference-latest-20260926/sec/acq-20260926
python3 blueprints/convergence-practice/gpt6-family-tiering-20260926/run_arm.py verify-frozen
OUT="$(mktemp -d)/decision.json"
python3 blueprints/convergence-practice/gpt6-family-tiering-20260926/analyze.py --acquisition "$LI26_ACQ" --out "$OUT"
cmp "$OUT" evidence/artifacts/gpt6-family-tiering-20260927/decision.json
```

`analyze.py` only reads the state directory and writes only `--out`, which must not exist yet. The preregistration
allows removing the state directory once its aggregates are recorded. Keeping it keeps this rerun possible; the
records here do not depend on it.

## Privacy boundary, as observed

- Replies, events, stderr, Codex session records and per-call records stay in the private state directory. The
  runner's 314 directories are 0700 and its 629 files 0600. Inside each call's 0700 `codex-home`, Codex created its
  own files with its default modes, reachable only through the owner-only directories above them.
- All 151 credential links were removed after their calls, and no call left anything in its scratch directory.
- Published here: `decision.json` holds aggregates only (`no_document_text: true`, repository-relative paths, no
  filing text, reply text or accession numbers). `run-record.json` holds run metadata and aggregates. Neither
  contains a prompt, a prompt hash, an event or a session record.

## What this does not establish

- Any stage other than mechanical extraction with a deterministic scorer, or any stage that lets the model use
  tools.
- General or cross-task quality, frontier parity, or accuracy against hand-checked labels.
- Provider cost in money, a quota share attributable to one arm, or the token savings of a whole task.
- Stability. There is one run per arm on one day, and `codex exec` exposes no temperature or seed, so the bootstrap
  covers filing sampling, not run-to-run variation. Cache hits are the provider's and may differ on another run.
- Isolated latency. The calls shared a host, an account and provider load.

The preregistration's `experiment.json` remains the planned convergence record, and its test pins it that way.
Recording the observed convergence record is a later change.

## Records

| File | Role |
|---|---|
| [`README.md`](README.md) | This summary: decision, scope, per-arm quality, tokens and time, the retry, the run record, re-verification, privacy and limits |
| [`decision.json`](decision.json) | The frozen `analyze.py` decision, copied unchanged (SHA-256 `555ed71c…`); a rerun reproduced it byte for byte |
| [`run-record.json`](run-record.json) | The run record: provenance, checkout and pre-run checks, launch and loop exits, per-arm times, call aggregates, the retried batch, usage totals, versions, the lock-directory deviation, quota context, the analysis rerun and the privacy check |
