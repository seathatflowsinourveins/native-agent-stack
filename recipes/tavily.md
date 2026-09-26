# Tavily in native Codex and Claude

Use the official [agent setup skill](https://tavily.com/agent-setup/SKILL.md) and [CLI](https://github.com/tavily-ai/tavily-cli). The authoring Linux host accepted CLI 0.1.8, a live search/extract and eight official skills. The previous explorer receipt is a separate dated installation scope.

For ordinary work, run the selected Search/Extract command when `tvly` is
available, as its upstream skills instruct. Since 2026-09-26 the key stays out
of files: on Linux and WSL2 run every `tvly` command through
`scripts/kernel_keyring.py exec`, as in
[Memory-only key on Linux and WSL2](#memory-only-key-on-linux-and-wsl2-2026-09-26),
and on macOS through `secret run`. For installation or a concrete
authentication failure, inspect `command -v tvly`, `tvly --version` and
`tvly auth --json`, the last through `exec`. If the CLI is missing, the
upstream installer is:

```sh
curl -fsSL https://cli.tavily.com/install.sh | bash
```

The observed installer selected `uv tool install tavily-cli`; another host must record the version it actually resolves. For a deliberate reproduction of the accepted package pin, use `uv tool install 'tavily-cli==0.1.8'` in the intended tool environment. Inspect the current installer before execution and retain its hash. Do not change the default Python or Node to complete setup when a compatible installed runtime is available.

Do not authenticate with `tvly login` or `tvly init`: both can write the credential to `~/.tavily/config.json`, which the operator's 2026-09-26 decision rules out. Keep the key in the kernel keyring or the login Keychain as in the dated section below. Never include the credential in public command receipts or shell history. The 2026-09-20 acceptance authenticated with native `tvly login`, into owner-only mode 0600 CLI storage. Install the actual requested clients' skills (the `tvly` lines below are that acceptance's commands; on a keyring host run each through `exec`):

```sh
npx --yes skills add tavily-ai/skills --skill '*' --agent claude-code --agent codex --global --yes
npx --yes skills list --global --agent codex
npx --yes skills list --global --agent claude-code
tvly auth --json
tvly search "Codex CLI Claude Code native agent harness skills official documentation" --depth basic --max-results 4 --include-domains developers.openai.com,code.claude.com --json
tvly extract https://code.claude.com/docs/en/sub-agents --extract-depth basic --query "native command line agent harness skills configuration" --chunks-per-source 3 --timeout 30 --json
```

Actual search returned four official Claude documents; selected extraction returned one result, zero failures. Each native Codex home's fresh `skills/list` found eight enabled skills. A direct Desktop-home probe failed SQLite initialization; a session-only private `sqlite_home` override allowed independent discovery without changing or opening the running Desktop transport. This is fresh-process discovery, not proof of the ongoing app registry. The CLI works immediately; newly discovered skills follow the client's normal rescan/new-session behavior.

A later continuation exposed all eight Tavily skills in the active Desktop task's
host-supplied skill catalog. That task loaded and used `tavily-search` and
`tavily-extract` for the IBKR plan: the broad search returned three official
IBKR pages but missed the intended adapter guide; direct extraction of the known
Nautilus guide returned one useful result and no failed results. The selected
guide confirmed paper socket defaults and connection prerequisites. The
[current-task receipt](../evidence/receipts/native-tavily-session-20260920.json)
keeps that search limitation and exact command evidence. This establishes the two
selected skill operations in this task, not execution of all eight skills or a
provider-token savings total.

Use Search and Extract for the task at hand. Map, Crawl and Research remain separately selected capabilities; this receipt does not qualify them or a full research report. No lifetime token-saving counter is claimed. [Exact native evidence](../evidence/receipts/native-tavily-cli-20260920.json).

## Memory-only key on Linux and WSL2 (2026-09-26)

On 2026-09-26 the operator chose to keep the Tavily API key in memory only,
never in a file. On a Linux or WSL2 host it lives in the kernel user keyring
under the name `tavily_api_key`. How to store it, how long it lasts and what
it does not protect against are in
[secret-storage.md](../docs/secret-storage.md#memory-only-option-linux-kernel-keyring-2026-09-26).
tavily-cli 0.1.8 reads `TAVILY_API_KEY` before its own file (`get_api_key()`
in `tavily_cli/config.py`: the environment, then `~/.tavily/config.json`,
then OAuth), so each command gets the key through `exec`, run from the
checkout root:

```sh
python3 scripts/kernel_keyring.py status tavily_api_key
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly auth --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly search "<query>" --depth basic --max-results 5 --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly extract "<url>" --extract-depth basic --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly research run "<question>" --model pro --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly research poll "<request_id>" --json
```

- `tvly auth --json` prints only `authenticated`, `method` and `source`;
  through `exec` it reports `"method": "env"`. Plain `tvly auth` also prints
  the first eight and last four characters of the key, so use `--json`.
- Do not run `tvly login`, or `tvly init` without `--skip-auth`, on such a
  host. `tvly login --api-key` and `tvly init --api-key` write the key to
  `~/.tavily/config.json` and put it on a command line, and without a key
  both can start a browser login that stores its token in the same file
  (`save_api_key()` and `save_oauth_session()` in `tavily_cli/config.py`).
  The CLI's own hints (`tvly login --api-key tvly-YOUR_KEY`,
  `export TAVILY_API_KEY=...`) do not apply here.
- Never give `exec` a command that prints the environment or the key, such
  as `env`, `printenv`, an `echo` of the variable or a plain `tvly auth`. The
  guard hook does not stop these through `exec`
  ([secret-storage.md](../docs/secret-storage.md#memory-only-option-linux-kernel-keyring-2026-09-26)).
- Without `exec`, `search` and `extract` still run, in keyless mode with a
  rate-limit cap, while `map`, `crawl` and `research` stop and ask for a key.
  A missing key therefore shows up as capped searches rather than an error.
  The upstream skills call bare `tvly`, so route their commands through
  `exec` too. Check `status` first, and store the key again after the kernel
  restarts.
- `research run` waits and polls until the report is ready (`--timeout`,
  default 600 seconds). `--no-wait` returns a request id for
  `research status` or `research poll`.
- On macOS use the login Keychain instead:
  `secret run TAVILY_API_KEY -- tvly ...` (see secret-storage.md).

The Research endpoint (`tvly research run --model pro`) was first used on
2026-09-26, for the Alpaca platform landscape. Its qualification receipt will
be recorded separately; this recipe does not claim that Research qualified.
Map, Crawl and Research remain separately selected capabilities, as stated
above.
