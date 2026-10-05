---
name: native-stack-research
description: Gather public research with the installed GPT Researcher and embedded DeerFlow routes, including a second independent gatherer when the task requests it.
---

For authorized public research, run the installed copy of the repository's
`tools/research/gpt_researcher.sh`:

```bash
bash "${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack/gpt-researcher.sh" "short current-month query"
```

The runner owns its
preflight, provider scrub, loopback route and 1500-second watchdog. A preflight
alone produces no research report.

Use DeerFlow's native headless CLI as the second independent gatherer when the task calls for
both routes:

```bash
DEER_FLOW_CONFIG_PATH="/absolute/path/to/current-public-deerflow-config.yaml" \
bash "${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack/deer-flow-research.sh" "short public research query with source URLs"
```

Use the public configuration supplied by the coordinator. The default uses
DeerFlow's tagged keyless DDGS search tool; no credential file or provider key is
needed or inherited.

Each route prints its run directory. Inspect the GPT Researcher report's
References and DeerFlow's `answer.md`, then re-read the claims at their primary
sources. Complete each call in the foreground and inspect its returned result.
Report the two actual outputs and any failure separately. DeerFlow uses the
shipped headless JSON CLI and its explicit native 100-step limit. Wait for each
foreground call to return; a background start or a completed session alone is
insufficient. The private run retains original events, final answer, stderr and
an integration receipt even when it fails. A matched DDGS empty-result object is
recorded as provider availability separately from native gatherer failure. It
does not qualify a completed cited research answer. No retry, fallback or HTTP
service is added. Report failed attempts and unknown terminal usage honestly.
The keyed Tavily candidate remains a separate proposal awaiting the command
center's owner ruling. Keep account secrets out of queries, reports and
environment files.

Sources: [GPT Researcher CLI](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/cli.py#L336),
[DeerFlow native CLI](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1837),
[DeerFlow model and tools](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L250),
[DDGS adapter](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/community/ddg_search/tools.py#L190),
and the repository's `tools/research/gpt_researcher.sh`.
