# Native Claude session recovery

One frozen attempt passed on the existing VelaNext Linux/WSL runtime using Claude
Code 2.1.278 and explicitly scoped Opus5 / Ultracode. Six deterministic fixture
tests passed on that host before the native call. The two CLI invocations took
14.592 seconds together.

The first invocation ran exactly `python3 stage.py checkpoint`, then entered the
unfinished native Bash command `python3 stage.py wait`. The supervisor observed
the durable checkpoint, live owned wait and native tool call before sending
SIGINT to its own CLI process. That CLI exited zero and the wait stopped without
additional supervisor termination. A second invocation used `--resume` with the
same native session ID and ran only `python3 stage.py finalize`. It completed
successfully with an unchanged checkpoint and execution count one.

[Receipt](receipt.json), [independent audit](independent-audit.json), and
[accepted output](accepted/final.json) retain the result. [The plan](plan.json),
[task](TASK.md), [input](input.json), [stage implementation](stage.py),
[supervisor](run.py) and [test oracle](test_fixture.py) were frozen before execution.
The native session IDs, process identities and complete streams remain private.

The initial and resumed terminal usage categories total **14,590** and **15,851**
tokens. Independent inspection reconciles their sum, **30,441**, with the resumed
cumulative model record: 8 ordinary input, 7,871 cache creation, 21,777 cache read,
and 785 output tokens. Thinking's 250 tokens are already inside output. Do not
add that cumulative record again. The original recorder conservatively left the
combined total unknown; the separate audit establishes this category reconciliation.
Native retries, billing and enclosing coordinator/reviewer usage remain unknown.
Native list-price estimates in the receipt are not observed subscription charges.
There is no matched baseline or savings claim.

SIGINT, clean process exits and an unchanged file establish this one same-host
continuation. They do not confirm remote provider cancellation, cessation of
billing, independent-host recovery, power-loss durability or general exactly-once
effects. Only Bash was available for this task, with precise allow rules and MCP
tools denied for the two invocations. No child agents, global settings changes,
account changes or shared-service operations were performed. Explicit Opus5
selection does not qualify the `best` alias or Fable.

The official [CLI reference](https://code.claude.com/docs/en/cli-reference) documents
`--session-id`, `--resume`, persistent sessions, stream output, scoped tools,
turn limits and Ultracode. Local `--help` was inspected before execution; the
official reference also covers supported flags absent from that help display.
[Native interruption](https://code.claude.com/docs/en/how-claude-code-works#interrupt-and-steer)
is documented for interactive control. This experiment separately observes CLI
process SIGINT; it does not equate the two transport mechanisms.

Offline checks never launch a model:

```sh
python3 -m unittest discover -s blueprints/convergence-practice/native-recovery/claude -p test_fixture.py
python3 blueprints/convergence-practice/native-recovery/claude/audit.py /private/owned-attempt
```

To deliberately run another independently authorized qualification, copy this
directory to the intended Linux host, then invoke `run.py --run-dir` with a new
private directory outside the source. The runner uses the installed `claude` and
its native sign-in. It does not install or authenticate. The first CLI has a
20-second SIGINT exit limit; each model stage has a separate 180-second deadline.
Unexpected tools, identity changes and failures are retained, with no automatic
second attempt. Existing native startup hooks and integrations retain their
normal side effects; a source directory is not global-state isolation.
