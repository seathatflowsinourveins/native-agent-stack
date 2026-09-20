# Tavily in native Codex and Claude

Use the official [agent setup skill](https://tavily.com/agent-setup/SKILL.md) and [CLI](https://github.com/tavily-ai/tavily-cli). The authoring Linux host accepted CLI 0.1.8, a live search/extract and eight official skills. The previous explorer receipt is a separate dated installation scope.

Check `command -v tvly`, `tvly --version` and `tvly auth --json` first. Reuse a working native credential. If missing, the upstream installer is:

```sh
curl -fsSL https://cli.tavily.com/install.sh | bash
```

The observed installer selected `uv tool install tavily-cli`; another host must record the version it actually resolves. For a deliberate reproduction of the accepted package pin, use `uv tool install 'tavily-cli==0.1.8'` in the intended tool environment. Inspect the current installer before execution and retain its hash. Do not change the default Python or Node to complete setup when a compatible installed runtime is available.

Authenticate through native `tvly login` or its documented API-key option using private input. Never include the credential in public command receipts or shell history. The accepted host's CLI storage is owner-only mode 0600. Install the actual requested clients' skills:

```sh
npx --yes skills add tavily-ai/skills --skill '*' --agent claude-code --agent codex --global --yes
npx --yes skills list --global --agent codex
npx --yes skills list --global --agent claude-code
tvly auth --json
tvly search "Codex CLI Claude Code native agent harness skills official documentation" --depth basic --max-results 4 --include-domains developers.openai.com,code.claude.com --json
tvly extract https://code.claude.com/docs/en/sub-agents --extract-depth basic --query "native command line agent harness skills configuration" --chunks-per-source 3 --timeout 30 --json
```

Actual search returned four official Claude documents; selected extraction returned one result, zero failures. Each native Codex home's fresh `skills/list` found eight enabled skills. A direct Desktop-home probe failed SQLite initialization; a session-only private `sqlite_home` override allowed independent discovery without changing or opening the running Desktop transport. This is fresh-process discovery, not proof of the ongoing app registry. The CLI works immediately; newly discovered skills follow the client's normal rescan/new-session behavior.

Use Search and Extract for the task at hand. Map, Crawl and Research remain separately selected capabilities; this receipt does not qualify them or a full research report. No lifetime token-saving counter is claimed. [Exact native evidence](../evidence/receipts/native-tavily-cli-20260920.json).
