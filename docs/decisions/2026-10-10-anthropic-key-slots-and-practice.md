# Anthropic key slots 5 to 10 and the key practice — 2026-10-10

## Decision and purpose

Declare optional `anthropic-api-5` to `anthropic-api-10` after
`anthropic-api-4` in the [credential inventory](../../adoption/credential-inventory.json).
Each mirrors `anthropic-api-4`'s `provider_api_key` class, foundation lane,
`private_env_file` store, single `ANTHROPIC_API_KEY` variable, consumers,
per-command loader and rotation grammar, with its own file beneath
`${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack`. The owner directed
more keys on 2026-10-10 (relayed by the command center). Declaring the slots
stores nothing, and it says nothing about credit, billing or any provider
feature.

Record the command center's key practice of 2026-10-10 as the repository's
practice, in [Key practice (2026-10-10)](../secret-storage.md#key-practice-2026-10-10):
one purpose per slot, hidden-prompt storage, per-command injection,
main-only environment secrets for CI, a no-token health check, tracking,
rotation, spend control and fill-first failover. Record `anthropic-api-3`'s
purpose as CI Claude review first, then local quality work; its key is the
main-only `claude-review` environment secret. The fill-first order is
`anthropic-api-4`, `anthropic-api-3`, `anthropic-api-5`, `anthropic-api`,
`anthropic-api-2`, then `anthropic-api-6` to `anthropic-api-10` as stored.
That is the owner's revision of about 15:12Z on 2026-10-10 (relayed by the
command center). It moved `anthropic-api-3` into the order, which the
command center's 14:15Z record had kept for CI alone.

Mark the inventory sentence "no Anthropic key is stored in GitHub" as
superseded in `anthropic-api-3` and `anthropic-api-4`: under the owner's
ruling of 2026-10-10 (PR #968), the CI key from `anthropic-api-3` is an
environment secret of the main-only `claude-review` environment.

Add `tools/credentials/anthropic_key_health.py`, a port of the command
center's `cc-tools/anthropic_key_health.sh`. Per slot it reports whether a
key is stored, the `GET /v1/models` status and its class, the
`GET /v1/organizations/me` status, and the first eight characters of the
organization id. The key reaches only a child started through
`credential_run.py`; the request headers go to the child on its standard
input, never in argv. The tool prints no key, organization name or response
body. A timer is out of scope; the command center adds one separately.

## Evidence

Measured in this change (local integration, synthetic values only):

- The extended `tests/test_credential_run.py` failed against the base
  inventory and passed against this branch's inventory. Swapping in
  `e1c88ff3d:adoption/credential-inventory.json`, the same-grammar test and
  the two inventory-driven id-set tests ended `FAILED (failures=14, errors=18)`.
  The setter and the runner refused `anthropic-api-5` to `-10` as unknown
  ids, and both id sets differed. With `641e7d0b8`'s inventory the same
  three tests passed.
- `tests/test_anthropic_key_health.py` exercises the tool with a fake opener
  and a fake runner. One test runs the real `credential_run.py` over a
  temporary store holding a generated key, with the HTTP side faked inside
  the child. The fake opener saw the key's SHA-256 on both requests, and the
  report held neither the key nor any six-character piece of it. Mutants
  that let the child accept `x-api-key` on stdin, follow a redirect, or pass
  unchecked child fields into the report each failed their test. No test
  makes a network call.

Read from primary sources on 2026-10-10 between 14:44Z and 14:45Z. Each
`docs.anthropic.com` URL redirected to `platform.claude.com`; markdown
copies were taken from the same paths with `.md`. The quoted phrases were
checked in both the HTML and the markdown:

- [Admin API](https://docs.anthropic.com/en/api/administration-api) (now
  `platform.claude.com/docs/en/manage-claude/admin-api`, markdown
  `sha256:81e4ddbfdacfff793ab12f8a9bf2bcddda10dbc90c88d4dc6e86ce9468d8827e`):
  "The Admin API is unavailable for individual accounts." Under "Accessing
  organization info", the `/v1/organizations/me` endpoint "returns the
  organization that your credential belongs to". The same page lists the
  credentials the Admin API accepts: an Admin API key, an `org:admin` OAuth
  token, or a personal or service account key that isn't scoped to a
  workspace. The command center reports that the endpoint also answered for
  each stored key; this change did not repeat that call.
- [Usage and Cost API](https://docs.anthropic.com/en/api/usage-cost-api) (now
  `platform.claude.com/docs/en/manage-claude/usage-cost-api`, markdown
  `sha256:4e8c9658637916235ef0b8433e36ec494a2be519ad72f2c923470c7f80274231`):
  the same sentence, "The Admin API is unavailable for individual accounts."
- [Prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching),
  "Cache storage and sharing" (now
  `platform.claude.com/docs/en/build-with-claude/prompt-caching`, markdown
  `sha256:e52e22f01d4eb474d5b15bd2b3ced251223679c96241eb141b79816333005df0`):
  "Caches are isolated between organizations. Different organizations never
  share caches, even if they use identical prompts." The page also says
  caches "are isolated per workspace" within an organization on the Claude
  API.
- [API overview](https://platform.claude.com/docs/en/api/overview),
  "Response headers" (markdown
  `sha256:56b2a39bfcafe6f10efa7b5b3c81e4ba129d124998d67b278dbce8daaac607bf`):
  `anthropic-organization-id` is "The ID of the organization that the API
  key or access token used in the request belongs to."
- gh 2.102.0, installed, `gh secret set --help`: `--body` "reads from
  standard input if not specified"; `--env` sets a deployment environment
  secret.

Command-center inputs, used as leads and not re-measured here: the
practice record `key-practice-20261010.md` (finalized 2026-10-10T14:15Z,
`sha256:69dd4a8e1cad1cb63218358c5febfe47259435a909bfebfab05fa4a4e75f3eee`) and
`cc-tools/anthropic_key_health.sh`
(`sha256:713453037a589118f575f7500783291968ecc1ab497838a5017b6b82a8d922d1`).
Both live in the command center's private state directory. They supplied
the slot purposes, the organization id prefixes read at 14:14Z, the
individual-account finding, the CI cap and the first failover order. The
coordinator relayed the owner's revised order and `anthropic-api-3`'s
revised purpose after 15:12Z. The repository copy omits account names and
credit balances.

## Alternatives

- **Round-robin or pooled keys.** Rejected. Anthropic keeps prompt caches
  apart per organization and, on the Claude API, per workspace. Spreading
  one workload over the five accounts would make each one write and hold its
  own copy of a cached prefix. Pooling would also blur which account spent
  which credit.
- **Keeping `anthropic-api-3` for CI alone.** The command center's 14:15Z
  record did so. The owner's revision of about 15:12Z puts it second in the
  order, so its credit also serves local quality work after the CI review.
- **Admin API keys for usage, cost and limits.** Unavailable: both Anthropic
  pages state that the Admin API is unavailable for individual accounts.
  Converting an account to an organization would enable it; that is the
  owner's choice and is not needed now.
- **Repository-level Actions secrets, or no CI key.** Repository-level key
  secrets are refused on public repositories. Workload identity federation
  remains the documented path in this base's Claude review workflows; the
  owner's 2026-10-10 ruling (PR #968) puts the CI review on a main-only
  environment secret instead.
- **Using the command center's shell script as is.** It prints each
  organization name, probes for admin keys, and lives outside the
  repository. The Python port keeps the stdlib only, takes request headers
  on stdin, follows no redirect, reads no body, and has tests.
- **Gateway routing for these keys.** Out of scope. The 2026-10-09 decision
  keeps them for direct use after a reported gateway feature-parity failure.

## What would overturn it

- Anthropic shares prompt caches across organizations, or the accounts move
  into one organization. Re-examine fill-first versus spreading load.
- An account becomes an organization with Admin API access. Usage, cost and
  key state would then be readable through the Admin API, and the health
  check and ledger could use it.
- `GET /v1/organizations/me` stops answering for regular keys, or
  `anthropic-organization-id` leaves the documented response headers. The
  health check then reports `?` for the organization, and its source needs
  a new primary reference.
- Local quality work on `anthropic-api-3` draws down the credit the CI
  review needs. Revisit that slot's place in the order.
- The owner changes the CI ruling, a slot's purpose, or the failover order.

## Acceptance and boundaries

Synthetic tests establish the inventory-to-setter-to-runner contract for
all ten slots, and the health tool's behaviour against fake HTTP and the
real runner. Several things remain outside this change's evidence: real key
storage, account ownership, workspace scope, spend limits, credit, the
`claude-review` environment and its secret, the CI cap, and the launcher's
fill-first switching. The health tool has not been run against a real key
here.

## Rollback

Remove the six slot entries, their documentation rows and fixture
expectations, the health tool and its tests, and the practice section.
Restore `anthropic-api-3`'s label, rotation and notes and
`anthropic-api-4`'s notes, then the shifted line citations in
`catalogs/foundation/upstream-surface-dispositions.json` and the evidence
bindings. Then run the affected modules and `scripts/validate.py`. Deleting
stores, revoking keys or removing the environment secret are separate owner
actions.

## SOTA sources

- [Anthropic Admin API](https://platform.claude.com/docs/en/manage-claude/admin-api)
  (read 2026-10-10, markdown
  `sha256:81e4ddbfdacfff793ab12f8a9bf2bcddda10dbc90c88d4dc6e86ce9468d8827e`):
  unavailable for individual accounts; `/v1/organizations/me` under
  "Accessing organization info".
- [Anthropic Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)
  (read 2026-10-10, markdown
  `sha256:4e8c9658637916235ef0b8433e36ec494a2be519ad72f2c923470c7f80274231`).
- [Anthropic prompt caching, Cache storage and sharing](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-storage-and-sharing)
  (read 2026-10-10, markdown
  `sha256:e52e22f01d4eb474d5b15bd2b3ced251223679c96241eb141b79816333005df0`).
- [Claude API overview, Response headers](https://platform.claude.com/docs/en/api/overview)
  (read 2026-10-10, markdown
  `sha256:56b2a39bfcafe6f10efa7b5b3c81e4ba129d124998d67b278dbce8daaac607bf`).
- [python/cpython@v3.13.16 Lib/urllib/request.py](https://github.com/python/cpython/blob/v3.13.16/Lib/urllib/request.py#L623-L656):
  `HTTPRedirectHandler.redirect_request` copies every request header except
  content length and type to the redirect target. The installed 3.13.16 copy
  is byte-identical, which is why the probe follows no redirect.
- gh 2.102.0 (installed), `gh secret set --help`: `--body` and `--env`.
- Repository references at the base,
  [e1c88ff3d7edc71052d6fb4eed8422438b06efaf](https://github.com/seathatflowsinourveins/native-agent-stack/commit/e1c88ff3d7edc71052d6fb4eed8422438b06efaf):
  `tools/credentials/credential_run.py:151` (`injectable`), `:1013` (the
  command inherits the runner's stdin) and `:1110` (the `--check` line);
  `tools/credentials/alpaca_rate_limit_probe.py:49` (`_NoRedirect`), `:126`
  (body never read) and `:131` (error type only);
  `adoption/credential-inventory.json:272` (the `anthropic-api-4` entry
  mirrored); `.github/workflows/claude-pr-review.yml:13` (federation at this
  base).
- [#930, 80cc49d53d7911c258190cadd1a2911657fd539a](https://github.com/seathatflowsinourveins/native-agent-stack/commit/80cc49d53d7911c258190cadd1a2911657fd539a):
  the pattern mirrored for the inventory, documentation rows, line
  citations, evidence bindings and fixtures.
