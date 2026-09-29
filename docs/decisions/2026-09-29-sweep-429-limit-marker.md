# Decision: the landscape-sweep runner treats an HTTP 429 without a usage-limit body as a limit (2026-09-29)

**Decided by:** session `native-agent-stack-76` on host `nativestack-5975wx-20260925`, after the 2026-09-29 sweep run
(#506) and an independent read-only review of this change, within the user's standing instruction to keep the
foundation layers current and to resolve the reopened layers.

**The defect.** [`tools/sota-convergence/landscape-sweep/codex_job.py`](../../tools/sota-convergence/landscape-sweep/codex_job.py)
wrote `<work-dir>/LIMIT` only for Codex's "hit your usage limit" report. On 2026-09-29 the pooled route answered HTTP 429
with no usage-limit body, Codex printed `exceeded retry limit, last status: 429 Too Many Requests` and exited 1, and nine
of the twelve follow-up GPT-6 jobs ended so within one or two seconds each
([`gpt6-job-outcomes.json`](../../evidence/artifacts/landscape-sweep-20260929-attempts/gpt6-job-outcomes.json)). No
marker was written, so the coordinator had no signal to stop: the Workflow finished its Claude follow-up stages (the
round cost $88 at Claude list price, [`spend-scan-wf_08a5b367-311.json`](../../evidence/artifacts/landscape-sweep-20260929-attempts/spend-scan-wf_08a5b367-311.json))
and six layers stayed reopened, each missing its GPT-6 vote.

**Decision.** The runner treats that report as a limit: the job ends with exit 3, `LIMIT` holds a reason and no reset
time, and later starts are refused. Only the 429 status counts (the pattern names it). A usage-limit report keeps its
empty marker and wins within one source. One 429 stops the sweep.

**Upstream facts** (openai/codex at `rust-v0.157.1`, read through `gh api` on 2026-09-29):

- `codex-rs/model-provider-info/src/lib.rs:442-448` builds every provider's retry policy with `retry_429: false`, and
  `codex-rs/codex-client/src/retry.rs:22-30` retries an HTTP status only when that flag or `retry_5xx` allows it.
- `codex-rs/codex-api/src/api_bridge.rs:159-207` maps a 429 whose body is not `usage_limit_reached`,
  `usage_not_included` or a quota error to `CodexErr::RetryLimit(RetryLimitReachedError { status, request_id })`; that
  is the only place the error is built (a code search of the repository finds it in `api_bridge.rs`, `error.rs` and
  `error_tests.rs`).
- `codex-rs/protocol/src/error.rs:398` lists `RetryLimit` among the terminal errors of `retry_delay`, and
  `codex-rs/core/src/responses_retry.rs:64-66` returns the error when there is no delay; `error.rs:650` is the Display
  text the runner matches.

So the report appears at the first 429, whether the pool is exhausted or briefly rate limited, and nothing in it tells the
two apart. The independent review found the first wording of this change ("after Codex's retries", "exhaustion") wrong on
this point; the code, the LIMIT reason, the README and the tests now say what Codex does.

**Evidence.** `tests.test_landscape_sweep_harness` (the new tests fail on the previous `codex_job.py`: a mutation check),
the ten failed jobs of the run (nine follow-up jobs and a probe after the run: one distinct error text, none with a
completed turn), and the run's cost by round and role, all listed in the pull request.

**Alternatives.**

- Keep the previous behaviour (rejected: the measured cost above, and six layers reopened with no stop signal).
- Stop only after two 429s (rejected for now: it needs state shared by the parallel jobs and lets the jobs already in
  flight run first; a false stop costs one look at the pool and a `start` that reruns the failed job, a missed stop
  costs a Claude round).
- Read the pool in the runner to tell exhaustion from a brief limit (rejected: a pooled route has no generic meter, and
  the native meter is already the optional quota gate).

**Consequence.** A brief rate limit on a native login also stops the sweep; the operator reads the pool
(`scripts/codex_quota.py`, or the gateway) and removes `LIMIT` when it has capacity, and the failed job runs again at its
next `start`. `result` reports `limit: true` for such a job and for its archived attempts, which `sweep.js` and
`convert.py` copy without acting on it.

**Residual.** `convert.py` keeps each GPT-6 job's status but not its error text, so `returns.json` cannot show why a job
failed; the job-outcome record was read from the private work directory. Carrying an error kind through `convert.py` is
a follow-up. The marker also only helps when the coordinator watches for it while the Workflow runs.

**Overturn.** A sweep in which one transient 429 stopped a run that would have completed and the pool showed capacity
(move to the two-job threshold), an upstream change that retries a 429 or puts the gateway's body in the report, or the
Gate B settlement of the GPT-6 route.
