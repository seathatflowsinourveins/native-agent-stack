# Decision: the Codex layer lane and adjudication judge default to effort max (2026-09-29)

**Decided by:** session `native-agent-stack-76` on host `nativestack-5975wx-20260925`, on a hand-off from `native-agent-stack-79` routed through
`ecosystem-roadmap-2026`, implementing the owner's standing rule that GPT-6 lanes run at `max` (never `ultra`); the [official Codex reasoning-effort configuration](https://developers.openai.com/codex/config-reference/) describes the setting mechanism, and the dated repository decision is recorded in
[`2026-09-27-model-currency.md`](2026-09-27-model-currency.md), [`2026-09-26-codex-worker-lane.md`](2026-09-26-codex-worker-lane.md) and
[`recipes/README.md`](../../recipes/README.md).

**The defect.** [`tools/sota-convergence/codex_lane.py`](../../tools/sota-convergence/codex_lane.py) set `DEFAULT_EFFORT = "high"`,
`tools/sota-convergence/adjudicate.py codex` set `--effort` to `high`, and `recipes/sota-convergence-practice.md` step 4 and the
`tools/sota-convergence/README.md` blind-wave example passed `--effort high`. A caller who followed them ran the layer lane and the judge below the
recorded owner rule: the model-currency record has judgment at `gpt-6-astra` and `model_reasoning_effort=max` (row for Codex CLI 0.157.1), and the worker-lane
record and recipe also select `max` for GPT-6 steps. This is the repository's declared default, not a vendor claim of superior measured quality. The 2026-09-22 verdict wave ran
at `high` (`docs/grand-catalog-handbook.md`), which stays a dated fact about that wave.

**Decision.**

- `DEFAULT_EFFORT` in `codex_lane.py` and the `--effort` default of `adjudicate.py codex` become `"max"`; both `--effort` helps say so; the recipe and
  the README example pass `max`.
- Five tests in `tests/test_codex_lane.py` that asserted the old lane default (three default-run `model` assertions, the dry-run command, one resume
  fixture) assert `max`. Two resume tests (`--model` rerun, stale-provenance rerun) built their fixture at `high`, so after the flip the effort
  mismatch alone would have forced the rerun and hidden the rule under test; their fixtures now use `codex_lane.DEFAULT_EFFORT`. Removing the model
  rule, the provenance rule or the effort rule from `existing_output_is_valid` each fails its own test (run on a scratch copy, then restored). The tests
  that pass an explicit effort to exercise the changed-effort rerun are unchanged.
- `tools/sota-convergence/lane-provenance.json` gains one append-only entry in the `codex` list (new `codex_lane.py` bytes) and one in the
  `adjudication` list (new `codex_lane.py` and `adjudicate.py` bytes), as `tests/test_verdict_lane_vendoring.py` requires. No existing entry changes.
- `codex_lane.py` is a `TRUST_PATHS` file of `scripts/verdict_review_gate.py`, so this travels alone: no verdict row, wave or sealed artifact changes
  (`verdict_review_gate.py --base origin/main --head HEAD`: "no verdict rows changed").

**Evidence (measured 2026-09-29 on this host, Codex CLI 0.157.1).**

- On unmodified `origin/main` with the default `TMPDIR`, `python3 -m unittest tests.test_codex_lane` failed 49 of 76 (the figure in the hand-off).
  The failing tests refuse a temporary directory that lies inside a git work tree (`--export ... is inside the git repository /tmp`), because an empty
  `/tmp/.git` exists on this host (a `config.worktree` file of 0 bytes, created the evening of 2026-09-28; an earlier session attributed it to a Codex
  workspace-write sandbox, which this record does not re-derive). With `TMPDIR` outside `/tmp` the same suite passes 76 of 76 on unmodified
  `origin/main`, and 5 fail after the flip alone. So the flip needed five test updates, not 49.
- On the final tree, with `TMPDIR` outside `/tmp`: `test_codex_lane` 76, `test_verdict_lane_vendoring` 14, `test_adjudicate` 116,
  `test_verdict_review_gate` 167, `test_landscape` 95 and `test_record_verdicts` 125 tests, all OK; `python3 scripts/validate.py` passes; the registered
  `codex_lane_py_sha256` and `adjudicate_py_sha256` equal the sha256 of the files in the tree. The full suite result is in the pull request.

**Alternatives.** Keep `high` and require every caller to pass `--effort max` (rejected: the recipe and the README showed `high`, which is how the gap
arose, and a forgotten flag silently changes the model setting); make the lane read the effort from the stack-worker profile (rejected here: a larger
change to a trusted file, and the profile is a Codex-home file the lane deliberately does not read).

**Consequence.**

- A lane return is reused only at the same `--model` and `--effort` (README "codex_lane resume"), so returns made earlier at `high` are not resumed
  by a default run.
- The effect is wider than the effort value. The new bytes change the lane provenance, which resume compares field for field
  (`existing_output_is_valid`; `adjudicate.py` resume). `record_verdicts.py` also refuses a Codex return or adjudication whose provenance names
  other lane code than this checkout's ("the return was produced by other codex lane code"), and `assemble` refuses judgments that ran under
  different provenance. So any lane return or judgment produced with the previous bytes, at any effort, must be recorded from a checkout that still has
  those bytes or be rerun; an in-flight wave should finish before this merges or restart after it.
- The 12 us-equities layers and any later verdict wave run after this merges.

**Residual: call duration at max.** `DEFAULT_TIMEOUT` stays 900 s in both files, and a timed-out call is retried once by the lane. Nothing measures the
layer lane's own duration at `max`. For scale only: the 2026-09-29 landscape sweep, a different lane (`landscape-sweep/codex_job.py`, timeout 3000 s,
web-enabled discovery and fit votes), finished 52 GPT-6 `max` jobs in a median of 652 s, p90 837 s and a maximum of 977 s, and 3 of the 52 ran longer
than 900 s. A layer that hits the limit is rerun with `--timeout`; if layer calls at `max` regularly exceed 900 s, raise the default in a follow-up
with that measurement.

**Overturn.** A measured comparison on this repository's layer verdicts showing `max` no better than `high` at higher cost (the M7-style sweep of
[`2026-09-28-community-sweep.md`](2026-09-28-community-sweep.md)), a Codex release that changes what `max` sends for `gpt-6-astra`, or a user change of
the standing rule.

## Amendment (2026-09-30)

The owner amended the standing rule on 2026-09-30 to permit staged Ultra for suitable lanes;
its stager chooses per the current GPT worker
standard. The landscape-sweep harness default stays max. Blind or isolated review lanes must stay at max,
because ultra auto-delegates through proactive multi-agent mode (openai/codex `rust-v0.159.2`, `ff6aec96948b`,
`codex-rs/core/src/session/multi_agents.rs:77-103`). This amendment supersedes the blanket prohibition above;
the original record and its dated measurements remain unchanged.

Staged ultra does not send an ultra effort on root requests. It resolves to the catalog's
`multi_agent_reasoning_effort`, else max for an ultra-capable catalog model
(`codex-rs/protocol/src/openai_models/reasoning_effort.rs:12-35`, `codex-rs/core/src/client.rs:863-872`).
Astra and Sol 6.1 resolve to xhigh (`codex-rs/models-manager/models.json:22,196`) while retaining proactive
delegation. The harness records staged `effort` and resolved `request_effort` together. Ultra usage is labeled
`primary_thread_only`; the retained primary-thread counters do not prove complete delegated usage
(`codex-rs/exec/src/lib.rs:1636-1638`, `codex-rs/exec/src/event_processor_with_jsonl_output.rs:509-511,533-535`).

An ultra lane defaults to an idle budget of 4200 seconds (3600 plus 600) and a total budget of 14400 seconds only
when those values are absent from staged settings. Initial staging with an ultra idle budget of 3600 seconds or
less is refused before state changes: the upstream default multi-agent wait cap is 3600 seconds
(`codex-rs/core/src/config/mod.rs:257`, `codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs:53-64`).
If lane configuration raises that cap, its idle budget must also cover it. The sweep's 8 × 540-second wrapper
cannot accommodate the ultra default; ad-hoc longer lanes require a matching caller wait. Non-ultra lanes
default to 4000 seconds, and all automatic attempts share that budget. These harness limits and the 300-second
retry floor implement bounded lifecycle recovery rather than measuring quality at ultra.

Correction and verification path: the prior draft's 7200-second sweep budget exceeded its 4320-second wrapper;
its reconnect override removed upstream outage recovery; and its ultra label omitted the resolved xhigh request
effort. Verified against working-tree source at the pin above: local `sweep.js:92`, upstream
`codex-rs/core/src/responses_retry.rs:71-96`, and the reasoning resolver/catalog/client locators above.
The local synthetic harness tests cover these repairs; they are not new upstream or live-model acceptance.
