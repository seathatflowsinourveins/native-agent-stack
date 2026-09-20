# Native Codex tool-turn recovery

One frozen synthetic attempt passed on the Mac's existing bundled Codex
`0.155.0-alpha.9.2`, preserving the observed GPT-6 Astra / Ultra configuration.
The native tool calls were exactly `checkpoint`, `wait`, `finalize`. The
coordinator withheld the wait response, received native interruption confirmation,
stopped that app-server, initialized a second process, and resumed the same native
thread and session IDs. The durable checkpoint was unchanged and executed once.
Both owned app-server processes exited zero. Elapsed time was 17.554 seconds.

[Receipt](receipt.json), [independent protocol audit](independent-audit.json),
[checkpoint](accepted/checkpoint.json), and [final result](accepted/final.json)
retain the bounded outcome. The [plan](plan.json), [task](seed/TASK.md),
[input](seed/input.json), deterministic [fixture](fixture.py), and test oracle
were frozen before native execution. Full native logs and identifiers remain
private; public hashes identify their retained, sanitized versions.

The final native cumulative usage was **55,376 tokens**: 55,233 input, including
18,176 cached input, plus 143 output. Five monotonic cumulative snapshots were
observed and the final total counted once. Native retries, billing and the
enclosing coordinator/review usage are unknown. There is no matched baseline
or savings claim.

This qualifies one same-host native dynamic-tool interruption and continuation.
The separately frozen [Claude CLI recovery](claude/README.md) now qualifies its
own SIGINT and same-session Bash continuation on Linux/WSL; it has distinct
process, model and usage boundaries.
It does not qualify shell descendant cancellation, remote provider cancellation,
network or power loss, independent-host restoration, or a distributed exactly-once
guarantee. The tool service remains alive in the coordinator while the two native
app-server processes are sequentially restarted. No native shell command was
observed; arbitrary MCP descendants and background terminals were not audited.

The official [app-server lifecycle](https://learn.chatgpt.com/docs/app-server#api-overview)
defines `turn/interrupt`, and [thread resumption](https://learn.chatgpt.com/docs/app-server#start-or-resume-a-thread)
defines same-ID continuation and restoration of experimental dynamic tools.
[Source review](source-review.json) distinguishes the fetched documentation hash
from the locally observed executable hash.

## Run only for an explicitly scoped qualification

Repository tests never call a model. To repeat the native experiment deliberately,
use an already authenticated executable and a new private directory outside Git:

```sh
python3 blueprints/convergence-practice/native-recovery/run.py \
  --codex /path/to/native/codex --run-dir /private/new-recovery-attempt
```

The runner checks the existing Astra/Ultra defaults before starting a turn. It
uses native authentication and configuration; it does not install or change them.
Each of two model stages has a bounded deadline. It stops only its own server
processes and retains failure evidence instead of automatically retrying.
Review output before publication. Starting the app-server can initialize existing
native integrations; a worktree does not isolate accounts or shared services.

The original executed runner is retained as inert
[execution-source text](executed-runner.py.txt). Post-capture review found that
the initial private logger retained the entire `config/read` response. Those
fields were removed from this owned run's logs without printing them, and
[the current runner](run.py) now logs only model/effort from that response.
Log hashes were refreshed; the receipt preserves the original executed source
hash. This logging correction did not trigger another model run.

Offline verification:

```sh
python3 -m unittest tests.test_native_recovery
python3 blueprints/convergence-practice/native-recovery/audit.py /private/retained-attempt
```

The second command requires deliberately selected private protocol files. Its
audit checks native request/response identity, the pending tool with no returned
result, interruption and completion statuses, exact native action order, output
bytes, cache accounting, and configuration-log minimization independently of
the main harness's pass flags.
