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

Use embedded DeerFlow as the second independent gatherer when the task calls for
both routes:

```bash
bash "${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack/deer-flow-research.sh" "short public research query with source URLs"
```

Each route prints its run directory. Inspect the GPT Researcher report's
References and DeerFlow's `answer.md`, then re-read the claims at their primary
sources. Report the two actual outputs and any failure separately. DeerFlow uses
the installed `DeerFlowClient.chat()` with a configured model and DuckDuckGo;
its embedded invocation starts no HTTP service. Keep account secrets out of
queries, reports and environment files.

Sources: [GPT Researcher CLI](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/cli.py#L336),
[DeerFlow embedded example](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1658),
[DeerFlow model and tools](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L250),
and the repository's `tools/research/gpt_researcher.sh`.
