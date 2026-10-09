# Additional Anthropic Console key stores — 2026-10-09

## Decision and purpose

Declare optional `anthropic-api-3` and `anthropic-api-4` immediately after
`anthropic-api-2` in the [credential inventory](../../adoption/credential-inventory.json).
Each mirrors the second entry's `provider_api_key` class, foundation lane,
`private_env_file` kind, single `ANTHROPIC_API_KEY` variable, consumers and
per-command loader. The distinct files are `anthropic-api-3.env` and
`anthropic-api-4.env` beneath
`${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`.

The authorized CC dispatch relayed on 2026-10-09 selects additional Console
credit and direct Anthropic use following a reported gateway feature-parity
failure. That failure is a coordination input, not a measurement made by
this change. Declaring these entries does not establish storage, available
credit, billing, provider features or Batches API acceptance. Those require
their own operator confirmation or direct-client evidence.

## Handling rules

The committed inventory precedes any credential window. The CC opens the
existing hidden-prompt terminal from that committed worktree, selecting
each new id; the owner enters each key directly. Agents do not open the
terminal, read or copy either store, run a real entry, or enroll these keys
with the gateway. Push and draft-PR publication follow the co-op's
confirmation that both keys have been stored.

Consumers select one id through
`tools/credentials/credential_run.py <id> -- <command>`. The variable remains
in `must_not_be_set`; it is not exported into the host shell. Store files
remain outside every worktree and use the existing setter's private-file
permissions and rotation grammar. GitHub Actions retain workload identity
federation. These optional local entries introduce no GitHub secret.

Use a dedicated workspace with a spend limit. Anthropic's SDKs read
`ANTHROPIC_API_KEY`; a workspace-scoped key needs no workspace header. A
multi-workspace key requires `anthropic-workspace-id` and remains outside
this single-variable contract. The actual key type is unmeasured here.
Claude Code uses an available key in noninteractive mode and requests
approval in interactive mode before it overrides subscription sign-in.

## Sources and research convergence

The implementation follows the repository's maintained reference rather
than introducing a credential runtime. Each mirrored file was read at
the #889 merge, [aba02ec3456d383bcc2fc72883db098f9be7918a](https://github.com/seathatflowsinourveins/native-agent-stack/commit/aba02ec3456d383bcc2fc72883db098f9be7918a):

| Mirrored source at #889 | Applied behavior |
| --- | --- |
| `aba02ec3:adoption/credential-inventory.json:222` | Optional entry, distinct store, shared variable, selected-id loader and rotation. |
| `aba02ec3:catalogs/foundation/upstream-surface-dispositions.json:206` | Rebind shifted secret-storage line citations; the other four citations are at lines 734, 758, 770 and 794. |
| `aba02ec3:docs/decisions/2026-10-08-anthropic-api-second-key.md:12` | Reuse the inventory mechanism; distinguish declaration, synthetic verification and provider acceptance. |
| `aba02ec3:docs/harness-defaults.md:93` | Preserve the correction about authentication modes and apply per-command injection to all four entries. |
| `aba02ec3:docs/secret-storage.md:24` | Add the documentation rows and retain hidden-prompt, workspace and variable handling. |
| `aba02ec3:manifests/evidence.json:5263` | Bind changed files by SHA256 and bytes; the decision insertion is at line 18149. |
| `aba02ec3:tests/test_credential_run.py:39` and `aba02ec3:tests/test_credential_run.py:383` | Expand the injectable-id set and the existing synthetic setter/runner grammar test. |

Primary public documentation was fetched on 2026-10-09. These are dated
source observations, not authentication or provider execution:

- [Anthropic authentication, Create and use a key](https://platform.claude.com/docs/en/manage-claude/authentication#create-and-use-a-key):
  supported Console keys, SDK environment input and workspace scope.
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars#variables):
  noninteractive API-key use and interactive approval before overriding
  subscription sign-in.

The existing runner's `injectable` check at
`22e3ef6ffd53b09f3cb335c46f7c696093521274:tools/credentials/credential_run.py:151`
accepts optional private env stores by inventory metadata. At that same
pin, `scripts/hooks/secret_path_guard.py:202` protects the store root and
`:229` already includes `ANTHROPIC_API_KEY` in `SECRET_NAMES`. No new
variable or id-specific runtime guard is needed. The repository's native
`unittest` fixtures and `scripts/validate.py` remain the supported harness.

The #889 mechanism preserves selected-id stores; sharing one file would
remove that separation, while introducing another setter would duplicate
the supported path (`aba02ec3:docs/decisions/2026-10-08-anthropic-api-second-key.md:12`).
Reconsider this disposition when a supported upstream loader reproduces
separate hidden entry, private storage and per-command injection under its
own harness. Gateway feature and batch parity needs independent evidence
before a separate routing decision.

## Acceptance and boundaries

Extend the #889 fixture across all four Anthropic ids. It writes only
generated fake values into temporary stores, checks 0600 permissions,
preserves the first store while selecting each additional id, verifies
only the selected variable reaches the child without echo, exercises
quoted values, and refuses expansion syntax. Other inventory and
secret-storage readers run by module under `timeout 600`, followed by
`python3 scripts/validate.py`. Results and the exact commit are retained
in the lane's coordination receipts.

Synthetic tests establish the inventory-to-setter-to-runner contract.
Real key entry, account ownership, workspace scope, spend limits,
available credit, authentication mode and full feature or batch parity
remain separate acceptance boundaries. No real provider call is made by
this declaration's checks.

## Rollback

Remove only the two new inventory entries, their documentation and fixture
expectations; restore affected line citations and evidence bindings, then
run the affected modules and validation. The first two entries remain.
Deleting private stores or revoking Console keys is a separate operator
action; reverting the declaration does not inspect or rotate either key.
