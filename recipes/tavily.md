# Tavily in native Codex and Claude

Use the official [agent setup skill](https://tavily.com/agent-setup/SKILL.md) and [CLI](https://github.com/tavily-ai/tavily-cli). The authoring Linux host accepted CLI 0.1.8, a live search/extract and eight official skills. The previous explorer receipt is a separate dated installation scope.

Tavily is not the default web lane. Since 2026-09-26, search, fetch and
extraction use the free native lanes first: Claude Code WebSearch and
WebFetch, Context Mode's `ctx_fetch_and_index`, and Codex with
`-c web_search="live"` ([harness defaults](../docs/harness-defaults.md#use-skills-workers-and-tools-deliberately)).
Run a `tvly` Search/Extract command only when the user asks for Tavily, or
when a free lane cannot return the page the task needs, and record which
lane failed. Since 2026-09-29 the key's store of record is the private file
`<store>/tavily.env`, as in [Stored key](#stored-key-2026-09-29); until the
next kernel restart, a Linux or WSL2 host still runs `tvly` with the kernel
keyring copy through `scripts/kernel_keyring.py exec` or the installed
`tvly-keyring` wrapper, and macOS through `secret run`. For installation or a concrete
authentication failure, inspect `command -v tvly`, `tvly --version` and
`tvly auth --json`, the last through `exec`. If the CLI is missing, the
upstream installer is:

```sh
curl -fsSL https://cli.tavily.com/install.sh | bash
```

The observed installer selected `uv tool install tavily-cli`; another host must record the version it actually resolves. For a deliberate reproduction of the accepted package pin, use `uv tool install 'tavily-cli==0.1.8'` in the intended tool environment. Inspect the current installer before execution and retain its hash. Do not change the default Python or Node to complete setup when a compatible installed runtime is available.

Do not authenticate with `tvly login` or `tvly init`: both can write the credential to `~/.tavily/config.json`, which the operator's 2026-09-26 decision rules out. Keep the key in its store file as in the dated section below. Never include the credential in public command receipts or shell history. The 2026-09-20 acceptance authenticated with native `tvly login`, into owner-only mode 0600 CLI storage. Install the actual requested clients' skills (the `tvly` lines below are that acceptance's commands; on a keyring host run each through `exec`):

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

When Tavily is selected under the rule above, use Search and Extract for the task at hand. Map, Crawl and Research remain separately selected capabilities; this receipt does not qualify them or a full research report. No lifetime token-saving counter is claimed. [Exact native evidence](../evidence/receipts/native-tavily-cli-20260920.json).

<a id="memory-only-key-on-linux-and-wsl2-2026-09-26"></a>

## Stored key (2026-09-29)

Since 2026-09-29 the Tavily API key's store of record is the private file
`<store>/tavily.env` (inventory id `tavily`), as for every other provider
key ([decision](../docs/decisions/2026-09-29-key-management.md)). From
2026-09-26 it lived only in the kernel user keyring, under the name
`tavily_api_key`, which a kernel restart erases. The file's first write
comes from that keyring copy, once, through the create-only chain in
[secret-storage.md](../docs/secret-storage.md#kernel-keyring-transport-and-per-boot-spare-2026-09-29),
which also covers how long the copy lasts and what it does not protect
against. To rotate, the operator types the new key once with
`tools/credentials/open_credential_terminal.sh tavily` and types `replace`
at the hidden prompt.

No command in this repository reads the file yet. Until the next kernel
restart the keyring copy still starts `tvly` with the key. tavily-cli 0.1.8
reads `TAVILY_API_KEY` before its own file (`get_api_key()` in
`tavily_cli/config.py`: the environment, then `~/.tavily/config.json`, then
OAuth), so each command gets the key through `exec`, run from the checkout
root:

```sh
python3 scripts/kernel_keyring.py status tavily_api_key
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly auth --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly search "<query>" --depth basic --max-results 5 --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly extract "<url>" --extract-depth basic --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly research run "<question>" --model pro --json
python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- tvly research poll "<request_id>" --json
```

Where [`adoption/tools/tvly-keyring`](../adoption/tools/tvly-keyring) is
installed next to a copy of `kernel_keyring.py`
([adoption/tools/README.md](../adoption/tools/README.md#tvly-keyring-2026-09-26)),
`tvly-keyring <args>` runs that same `exec` for `tvly <args>`, from any
directory. It checks `status` first and exits 2, without starting `tvly`,
when the key is absent. Install the pair from the checkout root into one
directory on `PATH`:

```sh
install -m 0755 adoption/tools/tvly-keyring "$HOME/.local/share/codex-ecosystem/bin/tvly-keyring"
install -m 0644 scripts/kernel_keyring.py "$HOME/.local/share/codex-ecosystem/bin/kernel_keyring.py"
tvly-keyring auth --json
tvly-keyring search "<query>" --depth basic --max-results 5 --json
tvly-keyring research run "<question>" --model pro --json
```

After the restart the keyring copy is gone: `status` prints `absent`,
`tvly-keyring` exits 2 without starting `tvly`, and Tavily commands have no
key until a later change adds a loader for the file (or the operator stores
a per-boot spare again). Tavily is not the default web lane, so that gap is
accepted.

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
  as `env`, `printenv`, an `echo` of the variable or a plain `tvly auth`.
  Since a later change on 2026-09-26 the guard hook blocks these through
  `exec` and `tvly-keyring` too, once a host's user-level copy of the hook is
  replaced. It is a text heuristic with recorded gaps
  ([secret-storage.md](../docs/secret-storage.md#guard-coverage-2026-09-26)).
- Without `exec`, `search` and `extract` still run, in keyless mode with a
  rate-limit cap, while `map`, `crawl` and `research` stop and ask for a key.
  A missing key therefore shows up as capped searches rather than an error.
  The upstream skills call bare `tvly`, so route their commands through
  `exec` too. Check `status` first.
- `research run` waits and polls until the report is ready (`--timeout`,
  default 600 seconds). `--no-wait` returns a request id for
  `research status` or `research poll`.
- On macOS use the login Keychain instead:
  `secret run TAVILY_API_KEY -- tvly ...` (see secret-storage.md).

The Research endpoint (`tvly research run --model pro`) was first used on
2026-09-26, for the Alpaca platform landscape, and then for one report per
catalog layer of that day's landscape sweep. The
[qualification receipt](../evidence/receipts/tavily-research-qualification-20260926.json)
records native provider execution through the keyring exec: 33 reports, all
`completed`, with response times from 168.49 to 367.68 s (median 248.85) and
11 to 32 sources per report. It makes no quality comparison with another
research endpoint. The runs used a prototype of `kernel_keyring.py`, before
the committed script. Map and Crawl remain separately selected capabilities,
as stated above.
