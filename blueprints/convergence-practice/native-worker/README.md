# Native Claude child-worker acceptance

On September 20, 2026, native Claude Code **2.1.278** ran one foreground
`ecosystem-worker` child on a clean Ubuntu 24.04 WSL2 runtime. The invocation
used **Opus 5** through the existing native Max sign-in, with Ultracode requested.
The strongest configured default was preserved; no global model setting changed.

The [frozen plan](plan.json), [prompt](prompt.txt) and [seed](seed/TASK.md) preceded
the model call. The original dependency planner fails eight of twelve visible
tests. The child verified its base, repaired only `planner.py` in its native
worktree and passed all twelve unchanged tests. The native coordinator and the
outer coordinator independently reran the oracle. The primary checkout stayed
clean. [Observed checks](checks.json), [accepted source](accepted/planner.py),
[test output](test-output.txt), [receipt](receipt.json).

An independent permutation oracle also checked all **65,536 directed four-node
graphs**, including self-edges, in **131,072** order/duplicate representations.
It accepted 543 acyclic graphs and rejected 64,993 cyclic graphs, with input
immutability checks and six unknown-prerequisite cases.
[Review script](independent_review.py), [retained result](independent-review.json).

The invocation completed in 81.192 seconds: one child at depth one, no background
worker, no timeout, four parent turns. CLI success, child isolation, source
identity, patch quality and the requested effort are separate observations.
This run does not prove that a dynamic workflow was selected, that the worker's
prose constraints were an OS sandbox, or that another host is qualified.

## Reproduce the artifact check

```sh
python3 -m unittest -v tests.test_native_worker_fixture
python3 scripts/validate_convergence.py blueprints/convergence-practice/native-worker/experiment.json --root . --json
```

This offline replay preserves the eight failing seed tests and twelve passing
accepted tests. It does not launch a model or reconstruct a historical session.
The oracle is author-written and visible to the worker, not a held-out benchmark.

For a new native execution, create an owned disposable Git repository whose
default branch contains exactly the seed files, record its actual commit and
substitute that commit in a **new** prompt/plan. A child worktree may start from
the default branch, so stop on any base mismatch. Install the reviewed native
role with `model: inherit`, `isolation: worktree`, and `maxTurns: 16`; delegate
with the native Agent tool. `--agent` would instead select a main role and would
not reproduce this parent/child test. Never reuse another host's credentials.

The observed native command selected `--model claude-opus-5 --effort ultracode`,
`--max-turns 12`, `--output-format stream-json --verbose`, explicit
`Bash,Read,Edit,Write,Agent` tools and `--permission-mode dontAsk`. The existing
[POSIX supervisor](../../us-equities/research-runtime/run_worker.py) bounded the
owned process group to 300 seconds. Its finance-specific environment helper was
not used; native HOME/PATH and the selected project context were retained.
Native logs stay private; only sanitized outcome and usage fields are published.

## Usage and save boundaries

The [usage receipt](usage.json) retains three native views separately. Terminal
categories sum to **105,297** tokens, `modelUsage` categories to **277,732**, and
the child task summary reports **27,865**. They are not interchangeable totals
and must not be added. Stream message blocks repeat usage fields, making naive
event summation incorrect. Native retry coverage and the enclosing Desktop
task's usage remain unknown. There is no matched baseline model invocation and
no token-savings or billing-savings claim. The list-price estimate is not evidence
of an additional charge to the subscription.

The durable handoff is the frozen task, exact source, accepted patch, checks and
decision. No transcript becomes automatic memory. The historical native worktree
and private logs remain available for local inspection; deleting the owned fixture
is the rollback. This is not a full host backup, a crash-resume test, remote
provider-cancellation proof or an application/GPU benchmark. The next useful
trial is a real repository issue with predeclared quality and complete matched
parent/child/retry/cache accounting.
