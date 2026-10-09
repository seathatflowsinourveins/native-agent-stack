# Second additional Anthropic Console key — 2026-10-08

## Decision and purpose

Add optional `anthropic-api-2` directly after `anthropic-api` in
[`adoption/credential-inventory.json`](../../adoption/credential-inventory.json).
It serves the foundation lane's additional-credit fast-mode trial. The second
key is additional: the first entry and its store remain separate. This change
declares a selectable store; it does not create one or establish provider,
credit, billing or fast-mode acceptance.

The second entry mirrors the first key's class, optional status, lane,
variables, consumers and store kind. Its file is `anthropic-api-2.env`, its
loader selects `anthropic-api-2`, and its rotation uses that id at the same
Console key page. The repository precedent is `alpaca-paper-2`, which selects
a second file through the existing inventory mechanism. No new runtime,
dependency, credential variable or custom runner is needed.

## Handling rules

Both stores use the existing private `0700` directory outside every Git
worktree and a `0600` env file. The operator supplies values through the
existing hidden-prompt setter after the inventory change lands. Creation or
rotation of the second store does not select or replace the first store.

Both entries declare only `ANTHROPIC_API_KEY`. Keep it in `must_not_be_set`
and inject it for one command only through
`tools/credentials/credential_run.py <inventory-id> -- <command>`. The existing
runner removes inherited credential variables, selects the requested store,
checks the shared writer/reader grammar and masks the injected output.
GitHub Actions retain workload identity federation; this entry adds no
GitHub secret.

Use a key scoped to one dedicated workspace with a spend limit, following
Anthropic's [key creation](https://platform.claude.com/docs/en/manage-claude/authentication#create-and-use-a-key)
and [workspace guidance](https://platform.claude.com/docs/en/manage-claude/workspaces#set-workspace-limits).
SDKs read `ANTHROPIC_API_KEY` automatically. A single-workspace personal or
service-account key requires no workspace header. A multi-workspace key
requires `anthropic-workspace-id`, which this single-variable entry does not
provide. The actual key type and workspace configuration remain unmeasured.

## Sources and research convergence

Public primary documentation was checked on 2026-10-08; these are dated
documentation observations rather than versioned execution acceptance:

- [Anthropic API overview, Getting API keys](https://platform.claude.com/docs/en/api/overview#getting-api-keys)
  and [authentication, Create and use a key](https://platform.claude.com/docs/en/manage-claude/authentication#create-and-use-a-key):
  supported Console creation, the canonical key page and SDK environment input.
- [Get your API key, Choose a key type](https://platform.claude.com/docs/en/get-api-key#choose-a-key-type)
  and [workspaces, API keys and resource scoping](https://platform.claude.com/docs/en/manage-claude/workspaces#api-keys-and-resource-scoping):
  personal versus shared service-account keys, single-workspace scope and the
  multi-workspace header boundary. A key scoped to a workspace is distinct
  from the legacy ownerless key type called a workspace key.
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars#variables)
  and [authentication precedence](https://code.claude.com/docs/en/authentication#authentication-precedence):
  mode-specific API-key behavior and authentication precedence.
- Repository source at
  [`c9ab2212142398234b6ba39a4cf33c5c2a6a643e`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/c9ab2212142398234b6ba39a4cf33c5c2a6a643e):
  `adoption/credential-inventory.json` (`anthropic-api`, `alpaca-paper-2`),
  `tools/credentials/set_credential.py:load_entry`,
  `tools/credentials/credential_run.py:find_entry` and `injectable`, and
  `scripts/hooks/secret_path_guard.py:SECRET_NAMES`, `STORE_PATHS` and
  `ENV_FILE_WORD`. The setter/runner select inventory ids; the guard already
  covers `ANTHROPIC_API_KEY` and both env-file paths. Its runtime needs no new
  id-specific rule.
- Repository native integration harness at that same revision:
  `tests/test_credential_run.py:RunnerCase` and `InjectionTests`. Acceptance
  uses these existing `unittest` fixtures with temporary stores and fake
  values, plus the repository's `scripts/validate.py` and the
  `scripts/host_receipts.py:register_file` helper.

Anthropic's SDK and `ant` CLI
[configuration profiles](https://platform.claude.com/docs/en/manage-claude/wif-reference#profile-configuration-file),
workload identity federation and secrets managers are documented
alternatives. The existing workflow already uses federation
for CI; this task needs an additional selectable local key for tools without
that identity path. Extending the inventory preserves the existing native
consumer contract without adopting another credential runtime. New evidence
that those consumers support the selected identity path without a stored key,
or a requirement for a multi-workspace key, would reopen this decision.

## Correction and evidence boundaries

The first entry's statement that a shell-exported key would override every
Claude Code session's native sign-in was too broad. Current environment
guidance says noninteractive `-p` uses a present key, while interactive mode
requires one approval before it overrides subscription credentials.
Authentication precedence adds further conditions. The inventory wording is
corrected and the mistake is recorded in the
[anti-pattern log](../harness-defaults.md#anti-pattern-log). Per-command
injection remains the handling rule for both keys.

The new integration test uses temporary stores and synthetic values to check
that the setter and runner accept both ids, preserve the first store when
writing the second, accept the same bare/quoted grammar, inject only the
selected value and refuse shell-expansion grammar. Inventory classification
now expects eleven injectable ids instead of ten. These are local integration
and synthetic checks, not unchanged upstream tests or live-provider evidence.
The PR declares every changed existing test expectation separately.

Key type, actual workspace spend limits, installed consumer acceptance and
provider execution are unmeasured boundaries. They remain distinct from the
declaration and local temporary-store checks. No credit or fast-mode result
is inferred from the entry's label.

## Inverse

Remove `anthropic-api-2` from the inventory, its documentation row and the
second-id test expectations, then re-register changed repository hashes with
`scripts/host_receipts.py:register_file` and run the affected native checks.
Keep `anthropic-api` and its store. If an operator later creates the second
store, its removal or Console key revocation is a separate explicit operator
action; reverting this declaration does not inspect, delete or rotate it.
