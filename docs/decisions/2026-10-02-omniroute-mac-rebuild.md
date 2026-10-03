# Decision: rebuild the Mac's OmniRoute gateway on release/v3.8.52 with GPT-6.1 Sol, follow the installed Codex version, and check upstream daily (2026-10-02)

Lane: foundation. North-star action served: the GPT lane can run GPT-6.1 Sol and GPT-6 Astra at max through the
gateway for every unit that serves the north star, including the clean-room definitive round. Status: switched on the
Mac coordinator on 2026-10-02 at 03:43:45Z under the user's direction ("update the omni first with clean SOTA
resolution and enable seamless auto update"), with the user's choices of a workstation-style rebuild and a
follow-and-notify update policy. The workstation gateway is untouched.

## Decision

The Mac's gateway (launchd `com.native-stack.omniroute`, loopback port 20128) now runs a build of upstream
`release/v3.8.52` (`528235175`) with upstream PR 13788 (`/v1/alpha/search` for Codex `web.run`) and upstream PR 15167
(GPT-6.1 Sol in the Codex registry and alias sets, so `max` reaches the wire), built with upstream's own release scripts
and artifact-policy check (recorded as a canary build, upstream's term for a build that carries unmerged changes).
This is the same composition the workstation gateway carries since 2026-09-30, on the newer release branch
(`docs/decisions/2026-09-30-omniroute-rebuild.md`).

- **Why GPT-6.1 Sol was missing.** The gateway sends `CODEX_CLIENT_VERSION` on its live Codex catalog query, and the
  Mac's launch agent fixed it at `0.158.0-alpha.2.1`, so the backend never offered GPT-6.1 Sol (the workstation record
  shows the same mechanism with 0.157.1). The static registry has no GPT-6.1 Sol entry in any release yet; PR 15167
  adds it.
- **Codex follow.** The launch agent now starts the gateway through `omniroute-serve.sh`, which reads the installed
  Codex CLI's version at every start and announces it; the plist value stays as the fallback. When Codex moved to
  0.160.0 during the switch, the gateway announced 0.160.0 with no edit.
- **Daily check.** `com.native-stack.omniroute-update-check` (09:17 local) restarts the gateway when the installed Codex
  version differs from the announced one and no non-browser client is connected, and posts a macOS notification when an
  official OmniRoute release carries both carried PRs, so the next switch can go to that release. It installs nothing.
- **Auth.** The gateway requires an API key and callers pass the documented loopback placeholder
  (`docs/secret-storage.md`, the `omniroute` row). The launch agent now passes that placeholder as the gateway's
  configured env key, so acceptance no longer depends on the database's key table. The first switch showed why: the new
  build's database migration left the placeholder unaccepted, every call answered 401, and the switch rolled back.

Evidence: `evidence/artifacts/omniroute-mac-rebuild-20261002/` (`receipt.json`, the build manifest with the tarball's
sha256, the probe gate before and after, both switch logs, the launch agents and the scripts as they ran).

## What the switch showed

| Check | Before | After |
| --- | --- | --- |
| `cx/gpt-6.1-sol` in the live catalog | no | yes (618 models) |
| `cx/gpt-6.1-sol`, body effort `max` | 400, not in the live catalog | 200 |
| `cx/gpt-6-astra`, effort `max` | 200 | 200 |
| `codex exec` through the gateway with GPT-6.1 Sol | fails (model unavailable) | exit 0 |
| Announced Codex version | 0.158.0-alpha.2.1 (fixed) | the installed Codex's (0.160.0 at start) |

The first attempt rolled back on its own after four failed probes. On the migrated database the previous build
answered 401 too, and its port preflight counted a browser's open dashboard connections as a listener and restarted
several times before it bound; the new build's preflight counts listeners only (upstream #14812). OmniRoute wrote its
own pre-migration database backup before migrating; it was not needed.

## Update, 2026-10-03

This update answers the first two items of issue 624's LE-18, which are addressed to the Mac OmniRoute service owner.
The details are in `evidence/artifacts/omniroute-mac-rebuild-20261002/le18-20261003.json`.

- **Running build.**
  - The listener on port 20128 started at the switch, 2026-10-02T03:44:48Z, from this build.
  - The installed package's `dist/BUILD_SHA` reads `6f246e84a`.
  - The retained tarball hashes to the build manifest's `d602dc42…`.
- **The process title `omniroute (v16.3.5)`** names the bundled Next.js version, not OmniRoute's. Next sets
  `next-server (v16.3.5)`, and OmniRoute's startup instrumentation renames it.
- **Effort read-back is still not done.** One GPT-6.1 Sol call at body effort `max` answered 200.
  - The gateway's call-log APIs record each call's model, provider, account, token counts and reasoning source, but no
    effort field.
  - The first limit below stands.
- **Update check, version 2,** deployed with version 1 kept beside it as the rollback. It still installs nothing. It
  adds notifications for:
  - a carried upstream PR closed without a merge, once per closure;
  - a new official release, with a read of its npm package for the two capabilities this build carries: the GPT-6.1 Sol
    catalog entry and the `/v1/alpha/search` route. A release with both can replace this build even if the carried PRs
    merged under other numbers.

  Tests:
  - A scan of this build's own package finds both capabilities; a scan of release v3.8.51 finds neither.
  - A dry run against a scratch state folder reports a new release and logs its notification.
  - Stubbed runs cover the closed-unmerged and carries-everything paths.
  - The first real run (05:38Z) changed nothing.
- **Not done here:** LE-18's third item, the `omniroute` row of `manifests/stack.json`. It is the lane:shared manifest
  owner's change.

## Limits

- Upstream effort on the wire was not read back on this host: the gateway's call log sits in its credential-bearing
  database, which this change did not open. `max` for GPT-6.1 Sol rests on PR 15167's source and on its measured
  read-back on the workstation gateway.
- Web search through the gateway does not work here: with no credentialed search provider resolved, the search route
  falls back to DuckDuckGo lite, which times out from this host. Page opening was already unsupported. Configuring a
  credentialed search provider in the gateway (for example the Tavily key of `docs/secret-storage.md`) is the user's
  step that would restore it.
- The build carries two open upstream PRs; the daily check flags when an official release carries both.
- The `omniroute` row of `manifests/stack.json` (npm 3.8.50) is unchanged: it is a shared hot file and changes in its
  own `lane:shared` change.

## Alternatives

- **Announce Codex 0.159.3 on the old build only.** Rejected by the user's choice: GPT-6.1 Sol appears but `max`
  clamps to `xhigh` without PR 15167.
- **Wait for an official v3.8.52.** Rejected: no release carries GPT-6.1 Sol yet, and the GPT lane needs it now.
- **Rebuild and switch automatically every night.** Rejected by the user's choice: it would put untested upstream
  changes into the live gateway; the daily check notifies instead.

## Overturn

Switch to the official release when the daily check reports that one carries PRs 13788 and 15167; drop the placeholder
env key if the gateway's key table is reconfigured; revisit the search fallback once a credentialed search provider is
configured.

## SOTA sources

- OmniRoute upstream: https://github.com/diegosouzapw/OmniRoute, `release/v3.8.52` at
  `52823517533cfceec7abef2ff3e6285a19fe4121`; PR 13788 (https://github.com/diegosouzapw/OmniRoute/pull/13788, commits
  `24bbadbad`, `6c7990058`); PR 15167 (https://github.com/diegosouzapw/OmniRoute/pull/15167, commit `0585aba55`);
  upstream's `build:release` and `check:pack-artifact` scripts.
- The catalog mechanism and the carry practice: `docs/decisions/2026-09-30-omniroute-rebuild.md` and
  `evidence/artifacts/omniroute-rebuild-20260930/receipt.json` (claim C9: the client version drives the catalog query).
