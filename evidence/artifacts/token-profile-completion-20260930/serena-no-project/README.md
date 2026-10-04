# Explicit no-project Serena parity correction

Pinned source: oraios/serena `c6fbd1c5932df2494ffa0020af5a9fbe80b82143`.
The earlier local `--project-from-cwd` probe activated an ancestor project.
Its 21-tool Claude response is authentic historical execution, but the earlier
"no active project" scope was incorrect. Clean CI exposed 23 tools, adding
`activate_project` and `get_current_config`. All 21 shared schemas were identical;
Codex and initialize bytes were unchanged.

The native commands now omit autodetection and use a new empty scoped
`SERENA_HOME` for each context:

```text
serena start-mcp-server --context claude-code --enable-web-dashboard false --open-web-dashboard false
serena start-mcp-server --context codex --enable-web-dashboard false --open-web-dashboard false
```

Both stdout files and `acceptance-observation.json` are unchanged originals.
Independent and green fixture drivers exited 0; the latter returned three native
commands and four integration checks. Each single-field schema-control driver
exited 1 at the complete byte oracle; native servers exited 0. The untouched
context remained exact and owned temporary state was removed. These are native
executions and local integration controls, not upstream tests. No provider call
was made. The independent Astra review accepted the correction.

The oracle neither discards nor normalizes fields. Original inherited-project
preimages remain in `token-lifecycle-resolution-20260930/serena-repair/`.
The preceding failed CI return is retained in `../ci-repair.json`.

Primary sources: [ancestor detection](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L369-L383),
[single-project predicate](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/agent.py#L699-L701),
[two-tool exclusion](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/agent.py#L839-L848),
[Claude context](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/resources/config/contexts/claude-code.yml#L52).
