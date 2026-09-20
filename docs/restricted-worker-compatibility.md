# Restricted native worker compatibility

Normal native workers should inherit the tools their connected client supports.
Narrow a role only when its instructions, installed hooks and permission contract
remain compatible. Directory ownership, worktrees and supported process supervision
are separate controls; an artificially restricted tool list is not an OS sandbox.

On September 20, Context Mode 1.0.169's Agent hook appended MCP/ToolSearch and
Write/Edit routing to the explicitly Bash-only recovery fixture, which denied
MCP tools. Installed `routing.mjs` matches tagged upstream commit
`589d8214d56740a28b5f7bf63167743d586b0b40` and the inspected current-main version
at `3053ca52af670519da368c4ef7cffa830f8f9243`; its SHA-256 is
`7447ee2e444743d6581c53aa1cfec9ffe0d904bc5a478d6fe2ac3e09ef0b3462`.
The [upstream Agent branch](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/hooks/core/routing.mjs#L892-L915)
appends that text without checking the child's available tools.

No supported role, project or invocation opt-out was found in that release or
the inspected current source. [Issue #946](https://github.com/mksglu/context-mode/issues/946)
tracks this restricted-child conflict.
[Issue #832](https://github.com/mksglu/context-mode/issues/832) records that a
proposed environment switch was dropped; it is not a shipped configuration option.
The child-originated `mcpToolsAvailable` redirect check does not control this
parent-side Agent prompt injection.

This is a concrete instruction conflict, but it does not prove why the child
added `ls -la &&` to its requested stage command. The earlier successful trial
received the identical 4,818-character actual child prompt and issued the expected
checkpoint command. The [combined supervised trial](../blueprints/convergence-practice/worker-recovery/containment-receipt.json)
remains failed before any effect; its permission refusal and cleanup are retained.

Keep the normal native defaults. Use a compatible inherited-tool role for ordinary
work; qualify any deliberately restricted role against its actual loaded hooks.
Do not invent an opt-out, patch the installed upstream plugin, disable every hook
or change global permissions to turn this fixture green. A future changed trial
must resolve the role/instruction contract first and preserve the original failure.

## Accepted inherited-tool recovery and post-hook permissions

The [later inherited-tool trial](../blueprints/convergence-practice/worker-recovery/native-exact-read-receipt.json)
kept upstream hooks and global settings unchanged. It completed native cancellation,
same-child continuation, an abrupt parent-runtime failure, automatic systemd cgroup
cleanup and same-parent/same-child finalization. Its checkpoint and frozen sources
were unchanged, with one final local effect and no direct descendant PID cleanup.
This qualifies the recorded role, task and same-host supervisor boundary. Host
crashes, independent-host recovery and provider cancellation remain unqualified.

A preceding inherited-role attempt failed during read-only inspection. The
[retained hook diagnosis](../blueprints/convergence-practice/worker-recovery/native-rewrite-diagnosis.json)
shows RTK 0.49.0 rewriting the original listing to `rtk ls`. Claude checks
permissions against a hook's updated input, so an invocation rule for the original
`ls` executable did not cover that transformed command. RTK's settings-file check
does not see the experiment's command-line permission rules. The actual hook row,
deterministic hook output and pinned upstream sources establish this mechanism.

The next profile retained the experiment's stricter `dontAsk` mode and added only
the exact rewritten listing for its owned fixture. The successful model run did
not request that listing; its extra read-only operation was tool discovery.
Accordingly, the native recovery result and deterministic listing-permission
diagnosis remain separate evidence. Keep required post-hook commands explicit in
a restricted task's local contract, without broad proxy grants or global changes.
