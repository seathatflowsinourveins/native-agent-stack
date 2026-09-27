# jCodeMunch route arguments (2026-09-27)

This record supports the [jCodeMunch route addendum](../../../docs/decisions/2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-jcodemunch-route-arguments).
That addendum changes the token-lanes carrier and the Codex user instructions so that they no longer invite
`route(..., execute=true)`.

## Files

| File | Bytes | SHA-256 | Content |
| --- | ---: | --- | --- |
| `probes.json` | 3,031 | `b7d415ab6119eeb6ed31bff86a0a805dca14dda5a2fde20389d97a112e2e241f` | The coordinator's probe record, copied byte for byte. It holds no host paths or identities. |

## Source

The source is jcodemunch-mcp 1.108.319, upstream commit
[`8f7b34abe16fb459e0bf1c04747d584216dfe32e`](https://github.com/jgravelle/jcodemunch-mcp/tree/8f7b34abe16fb459e0bf1c04747d584216dfe32e),
whose `pyproject.toml` reads `version = "1.108.319"`. On 2026-09-27 the installed `counter.py` and `server.py` were
compared with the raw files at that commit. Both are byte-identical:

- `counter.py` is 33,194 bytes, sha256 `d56ba52f8ed5716f6ec9e2d79ab53d4333972fe1ad2a36cb981ff4752c0c97aa`.
- `server.py` is 542,239 bytes, sha256 `9b6335f29649c3fe7a4f783e5246cd789e6a6d21dfcf44de4856d701e20f9944`.

The wheel's `RECORD` lists the same `counter.py` digest.

- [`counter.py` L584-590](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/counter.py#L584-L590):
  `_QUERY_ARG` maps `search_symbols` and `search_text` to `query`.
- [`counter.py` L616-630](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/counter.py#L616-L630):
  `shape_execute_args` returns `{"repo": repo, qarg: task}`, so the whole task becomes the query.
- [`server.py` L5535-5580](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L5535-L5580):
  `_handle_route` builds each recommendation's `args_template` with that function first (L5549), falling back to a
  curated example only when it returns nothing. With `execute` it dispatches the top action with those same
  arguments (L5562). When it cannot shape them, it returns `execute_error` (L5563-5569). The handler's docstring
  (L5536) gives the signature `route(task, repo?, execute?, model?)`, the form the carrier's former clause also
  used.
- The route schema's `execute` description is at
  [`server.py` L460](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L460).

## Probes (`probes.json`)

The coordinator's Claude session made these calls through its native jcodemunch MCP tools, in the main checkout at
`c8362c02`, at about 2026-09-27T20:22Z. Each call ran once.

| Call | Result | Reading |
| --- | --- | --- |
| `order search_symbols {repo: ".", query: "register_file", kind: "function", max_results: 1}` | `register_file` in `scripts/host_receipts.py`, line 710, with its signature | One call returns the target. |
| `route("register_file", repo: ".", execute: true)` | Recommended `register_edit` (state-changing), `get_file_content` and `get_file_outline`; `executed: false` with an `execute_error` | An identifier alone routes to a catalog action whose name matches it and runs nothing. |
| `route("find the function register_file in scripts/host_receipts.py", repo: ".")` | Recommended `search_symbols` with `args_template` `{"repo": ".", "query": "<the whole sentence>"}` | Route picks the right action, but the caller must write the query. |

## Corroboration (another session's measurement)

This record repeats the following observations; it did not re-run them. The Codex-lane gate in
[PR #433](https://github.com/seathatflowsinourveins/native-agent-stack/pull/433) (`tools/capability-gate`, open at
this writing) belongs to another session, which ran `codex exec -p stack-worker` through promptfoo 0.123.1
`openai:codex-sdk` on 2026-09-27:

- In the first smoke (run 2026-09-27T20:09:50Z),
  `route {task: "find the function register_file in scripts/host_receipts.py", repo: "native-agent-stack", execute: true}`
  ran in one call in 6 of 6 runs. None of the 6 returned either target symbol among its 10 results.
- The gate's jcodemunch case uses `order search_symbols` with the identifier. It passed 6 of 6 gate rows, each with
  exactly one completed call that returned the signature (run 2026-09-27T20:16:19Z).

PR #433 classes both runs as smoke on the workstation, not receipts, and records its receipts after it merges.

## Boundaries

- The probes are local observations of one index and one catalog revision (1.108.319), one call each. They are
  not an upstream test, a repeated trial or a measurement of token savings.
- No subagent or Codex worker run with the changed carrier or instructions is claimed. Delivery of the new text is
  covered by the repository's structural tests only.
