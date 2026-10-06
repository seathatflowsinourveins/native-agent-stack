# Native dashboard access

Use the installed upstream interfaces for their own data. These local URLs are
the authoring PC's loopback endpoints; resolve the installation's paths and ports
on another PC. The catalog is a setup guide, not an upstream telemetry dashboard.

For useful data, start with the [memory/RAG and savings view](native-dashboard-data.md).
It records actual scoped retrieval, source freshness, official memory and code-graph
interfaces, selected session refreshes and native counters. The HTTP access checks
below establish transport only; opening a dashboard is not application E2E.

| Upstream interface | Authoring-host URL | Verified scope |
| --- | --- | --- |
| Grafana | http://127.0.0.1:13000/d/ecosystem-native/native-agent-ecosystem | Native Grafana with locally provisioned ecosystem panels; anonymous viewing, no password challenge |
| Dagu | http://127.0.0.1:18525/ | Passwordless local dashboard; DAG run/write disabled; other administration remains available locally |
| Qdrant | http://127.0.0.1:16333/dashboard | Official web UI; five existing collections visible after adding static assets |
| AgentsView | http://127.0.0.1:17384/ | Existing explicitly scoped archive, started without syncing/importing sessions |
| agent-browser | http://127.0.0.1:4848/ | Upstream browser-session dashboard; not token savings |
| Prometheus | http://127.0.0.1:19090/query | Native metrics query UI; no password challenge |
| ntfy | http://127.0.0.1:18080/ | Native notification UI; no password challenge |
| OmniRoute | http://127.0.0.1:20128/ | Existing Windows gateway dashboard; passwordless management, gateway API-key requirement preserved |

Eight native HTTP checks returned 200/exit 0. Changed Dagu and Qdrant behavior
was also checked in an isolated upstream agent-browser session and independently
observed. These are local dashboard/API integration checks, not a full upstream
test suite, provider inference, or a token-saving benchmark. See the
[command evidence](../evidence/receipts/native-dashboard-access-20260921.json).

### NativeStack2604 equivalents (2026-10-06)

The table above is the authoring host's. WSL2 distributions share loopback
listeners, so 13000 can reach the legacy distribution's Grafana while it runs.
NativeStack2604 uses 21301. Its install plan
([`new-wsl-install-plan-20261002`](../evidence/artifacts/new-wsl-install-plan-20261002/README.md))
uses these loopback URLs. The three ported dashboards exist once the plan's
`grafana` row has run with the 2026-10-06 port; until then `/api/search` lists
only `token-layer`.

| Upstream interface | NativeStack2604 URL | Scope |
| --- | --- | --- |
| Grafana | http://127.0.0.1:21301/d/research-grand | Anonymous Viewer, no sign-in path (plan `config/grafana.ini`). Also `/d/ecosystem-native`, `/d/native-foundation-data` and `/d/token-layer`. The research dashboard shows Dagu run history without a Dagu login |
| Dagu | http://127.0.0.1:21080/ | Operator UI with its builtin login (Dagu 2.18.2's default when `auth.mode` is unset); `/api/v1/dags` answers 401 without it |
| Prometheus | http://127.0.0.1:21090/query | No password challenge |
| Alertmanager | http://127.0.0.1:21093/ | No password challenge; Telegram receiver |
| OmniRoute | http://127.0.0.1:21128/dashboard | `requireLogin=false` and a keyless loopback client API, the user's posture ([account-pool decision](decisions/2026-09-27-omniroute-account-pool.md)); the Health page needs a dashboard session, see [OmniRoute's Health page](#omniroute-health-page-on-a-passwordless-install-2026-10-06) |
| ai-memory | http://127.0.0.1:29374/web | Memory web UI |
| Codebase Memory | http://127.0.0.1:9749/ | Code-graph UI |

Qdrant, agent-browser and ntfy have no NativeStack2604 listener, and AgentsView
was not listening on 21808 when this was checked (2026-10-06, 00:40 EDT, 04:40Z).

## Dagu: remove the repeated browser password box

Dagu 2.16.6 served its HTML while `/api/v1/dags` returned 401 with
`WWW-Authenticate: Basic`. The browser therefore repeatedly prompted while the
application fetched data. For this trusted, single-PC dashboard, upstream
supports:

```yaml
host: 127.0.0.1
port: 18525
auth:
  mode: none
permissions:
  write_dags: false
  run_dags: false
```

Remove `auth.basic` and any Basic credential environment overrides when changing
the mode; upstream validation rejects them under `none`. Keep the private file's
mode 0600 and preserve all other existing fields. The terminal remains disabled
by this version's native default. The service still runs `dagu server`, without
starting a scheduler or adding provider/broker credentials.

```sh
systemctl --user restart dagu-equities.service
curl --include http://127.0.0.1:18525/api/v1/dags
```

The actual result changed from 401/Basic challenge to 200/no challenge. A fresh
browser view and reload both displayed the dashboard with no password field or
dialog. Source-backed negative probes returned 403 for workflow execution and
wiki modification. Prometheus now expects the dashboard's 200 response; the
native collector observed it and the corresponding alert is inactive.

The two permission flags are **not a global read-only policy**. Without builtin
authentication, upstream grants the local workspace an admin role; base settings,
views and managed-secret administration have separate controls. This mode trusts
users and processes on this PC. Keep loopback binding and existing CORS settings;
use upstream builtin/OIDC authentication for remote access. Native CLI workflow
execution is unchanged. The previous Basic-auth receipt remains historical.

Sources: [pinned auth middleware](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/frontend/auth/middleware.go),
[configuration validation](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/cmn/config/config.go),
[workspace roles](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/frontend/api/v1/workspace_access.go),
[run permission check](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/frontend/api/v1/dags.go),
[wiki permission check](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/frontend/api/v1/wiki.go).

## Qdrant: install the missing upstream UI

The native Qdrant 1.19.1 API was healthy, but `/dashboard` returned 404 because
its static directory was absent. Follow the distribution layout in Qdrant's
[pinned packaging script](https://github.com/qdrant/qdrant/blob/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/tools/sync-web-ui.sh).
This host selected official [UI v0.2.18](https://github.com/qdrant/qdrant-web-ui/releases/tag/v0.2.18),
commit `6f8536529934672a0d2631cfaa0d0779967922bc`.

Set `QDRANT_UI_STAGE` to a fresh owned staging directory and `QDRANT_UI_DIR` to
a new absolute versioned installation directory; create both first.

```sh
set -eu
gh release download v0.2.18 --repo qdrant/qdrant-web-ui \
  --pattern dist-qdrant.zip --dir "$QDRANT_UI_STAGE"
printf '%s  %s\n' \
  fdce24c04ec1627d2369cb8fe610ee06ad9236f82aad214aa7f294ac37372859 \
  "$QDRANT_UI_STAGE/dist-qdrant.zip" | sha256sum --check --strict
unzip -q "$QDRANT_UI_STAGE/dist-qdrant.zip" -d "$QDRANT_UI_STAGE/unpacked"
cp -a "$QDRANT_UI_STAGE/unpacked/dist/." "$QDRANT_UI_DIR/"
curl --fail --location \
  https://raw.githubusercontent.com/qdrant/qdrant/6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de/docs/redoc/master/openapi.json \
  --output "$QDRANT_UI_DIR/openapi.json"
printf '%s  %s\n' \
  eb3e5d71ba74e1d99124ca1a77d563bbfa47084f04a13ef9b197e339f5a4ce0a \
  "$QDRANT_UI_DIR/openapi.json" | sha256sum --check --strict
```

Verify the 7,189,135-byte archive against SHA-256
`fdce24c04ec1627d2369cb8fe610ee06ad9236f82aad214aa7f294ac37372859`
before extracting it. Preserve the existing Qdrant configuration and add only
these fields inside its `service` mapping, using the actual absolute directory:

```yaml
enable_static_content: true
static_content_dir: /absolute/versioned/qdrant-web-ui-directory
```

```sh
systemctl --user restart qdrant-agent-lab.service
curl --include http://127.0.0.1:16333/dashboard
curl --fail http://127.0.0.1:16333/collections
```

The retained check matched 225 installed assets to the official archive and the
OpenAPI file to the server revision. The same five collection names remained,
all reported green, and the browser rendered five collection rows. Collection
name equality is not a byte-for-byte storage comparison. No indexing/import or
authentication change was made. The UI exposes the existing API's management
capabilities; it is not a read-only client. Upstream does not publish a fixed
UI/server compatibility matrix; this pairing is accepted within these checks.

## On-demand dashboards and hosted accounts

The portable stack selects OmniRoute 3.8.51. The recorded Windows dashboard
acceptance used an optional, separately started OmniRoute 3.8.50 profile. Its
existing selective launcher starts native `omniroute serve --port 20128
--no-open --no-tray --no-recovery` with the saved data directory and
`OMNIROUTE_SERVER_HOST=127.0.0.1`. It is not a replacement for native Codex/Claude
sign-in or the default traffic route.

The supported passwordless dashboard setting is persistent `requireLogin=false`.
Use the existing native dashboard login once, then the authenticated upstream
`POST /api/settings/require-login` endpoint with JSON `{"requireLogin":false}`.
Do not publish or embed the password/session cookie in a launcher or URL. This
host used the existing private password in process memory and recorded only
response statuses and the selected boolean. Dashboard reads now return 200 at
`/dashboard` without a login redirect or HTTP authentication challenge.

Dashboard login is separate from effective `REQUIRE_API_KEY`. Native, cookie-free
`GET /v1/models` returned 401 before and after the change; an invalid key also
returned 401. A valid dashboard cookie is an upstream authentication alternative,
so do not use that cookie when checking anonymous client-API protection. No model
or provider request was made. The dashboard setting also opens ordinary local
management operations; it is not a read-only mode. Protected destructive routes
retain their upstream guards. Keep this profile on loopback.

Sources: [pinned setting route](https://github.com/diegosouzapw/OmniRoute/blob/5458026c216f77a3da68ea49152dc33470cfe2cb/src/app/api/settings/require-login/route.ts),
[API-key flag precedence](https://github.com/diegosouzapw/OmniRoute/blob/5458026c216f77a3da68ea49152dc33470cfe2cb/src/shared/utils/featureFlags.ts),
[route guards](https://github.com/diegosouzapw/OmniRoute/blob/5458026c216f77a3da68ea49152dc33470cfe2cb/src/server/authz/routeGuard.ts).

### OmniRoute Health page on a passwordless install (2026-10-06)

On NativeStack2604's 21128 build (3.8.51 content plus PR 15167 and the affinity
patch, `BUILD_SHA` `5f4b3d577`), `/dashboard/health` throws `TypeError: Cannot
read properties of undefined (reading 'uptime')`. The cause in this install is
its passwordless posture (`requireLogin=false` and no stored password, so no
browser holds a dashboard session) meeting a route that ignores `requireLogin`;
the install is not broken. Read in the installed build
(`~/.local/share/omniroute-builds/omniroute-3.8.51-5f4b3d577-affinity-pr15167/lib/node_modules/omniroute/`):

- `GET /api/monitoring/health` calls `requireManagementAuth(request, {alwaysRequireAuth: true})`
  and, for a request without a dashboard session, answers HTTP 200 with only
  `{status, setupComplete}` (`dist/.build/next/server/chunks/_14gdr2j._.js:1:290`,
  the response helper, and `:1:539`, the auth call).
- `alwaysRequireAuth` skips the `requireLogin=false` shortcut; only a dashboard
  session cookie (`auth_token`), the internal service token, a CLI token or a
  management access token pass (`dist/.build/next/server/chunks/src_04ajmw1._.js:1:1702`;
  `isAuthRequired` returns false for `requireLogin === false` at `_0m42383._.js:1:33832`).
- The page fetches that route, destructures `system` from the body and reads
  `system.uptime` (`dist/.build/next/static/chunks/07_92fqf2xgq6.js:3:18913`, `:3:21720`
  and `:3:27164`).

Without a session the page cannot render, no other setting changes that, and no
upstream file is to be patched. The choices are to set a management password and sign in once (the
login route refuses while no password is stored, `dist/.build/next/server/chunks/_0ajtddf._.js:1:3030`;
this gives up the passwordless posture, so it is the user's call), or to
read health from the public `GET /api/health` and Prometheus. The two 404s on the compression settings page
are upstream's too: the page links `/dashboard/context/<engine>` for every entry
of `ENGINE_IDS` (`dist/.build/next/static/chunks/1tljxm1kldxz3.js:1:13502` and `:1:14016`), the catalog lists
`codex-responses` and `relevance` (`open-sse/services/compression/engineCatalog.ts:85-86,112,192`),
and the build has no page for either (`dist/.build/next/server/app-paths-manifest.json`).
Next.js prefetches those links and gets 404; nothing else breaks.

Start the installed browser dashboard with its native command:

```sh
agent-browser dashboard start
```

For AgentsView, select the existing archive explicitly and avoid changing its
import scope merely to open its interface:

```sh
env AGENTSVIEW_DATA_DIR="$EXISTING_SCOPED_ARCHIVE" \
  AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 \
  agentsview serve --host 127.0.0.1 --port 17384 --no-sync \
  --no-browser --no-update-check --require-auth --background
```

The archive is historical, not live accounting for this task. Both native
interfaces rendered without password fields or dialogs. The services remain
available after the browser check; only the owned test-browser session was closed.

The initial unmanaged AgentsView background process later exited; the exact
termination cause was not established. HTTP timed out and no listener/process
remained. The adopted persistent profile uses the same native foreground command
under the existing user service manager. Copy and resolve
[the user-unit example](../examples/agentsview-archive.service.example), then run:

```sh
systemctl --user daemon-reload
systemctl --user enable --now agentsview-archive.service
systemctl --user restart agentsview-archive.service
systemctl --user is-enabled agentsview-archive.service
curl --fail http://127.0.0.1:17384/
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:17384/api/ping  # 401 without a token
```

Do not run a second background daemon beside this unit. It serves the same
archive, in live mode since 2026-09-27 ([live mode](#live-mode-on-the-workstation-2026-09-27)).
This is native process supervision, not proof of physical-PC reboot recovery.

### Token on the archive API (2026-09-27)

The unit runs with upstream `--require-auth`. Without it, v0.43.0 checks no
token on the dashboard's own `/api/` routes; only the machine-to-machine
remote-sync, raw-sync and artifact-exchange routes keep their own authentication
([auth middleware](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/server/auth.go#L110-L161)).
Those dashboard routes include session
[resume and open](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/server/huma_routes_sessions.go)
actions that start programs
([openers](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/server/openers.go)),
and a [terminal setting](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/server/huma_routes_config.go)
that chooses what they start. Host and Origin checks stop browser pages, not local
programs that set those headers, and with WSL mirrored networking, Windows
processes share this loopback address.

- The interface still loads, because static pages are not gated. Unlike the
  passwordless first check above, it now asks once for the bearer token stored
  as `auth_token` in the archive's `config.toml`. Serve logs only that a token
  is configured.
- The CLI with `AGENTSVIEW_DATA_DIR` set and no `--server` sends its reads to
  the archive's running daemon, with the archive's token
  ([transport](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/transport.go#L275-L303)).
  An explicit `--server` request needs `--server-token-file`; without it, it
  returns 401.
- Set `require_auth = true` in the archive's `config.toml` as well, as the
  [archive config example](../examples/agentsview.toml.example) does.
  - When no daemon is running, a read without `--server` starts one itself. That
    daemon takes its settings from the config, not from the unit's flags.
  - It also syncs, because `--no-sync` is a runtime option with no config key
    ([config](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/internal/config/config.go#L711)).
    The live-mode unit syncs too. For a frozen `--no-sync` archive, keep its
    unit running while you read in the data-dir form.
- While the unit runs, a direct write such as `AGENTSVIEW_NO_DAEMON=1 agentsview sync`
  on the same archive is refused
  ([write guard](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L1421-L1427)).
  Refresh a selected file with `agentsview session sync FILE` through the unit.
- Telemetry and the update check are off, but the pricing refresh still fetches
  from raw.githubusercontent.com and openrouter.ai at start and every 24 hours
  ([pricing schedule](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/pricing_schedule.go)).
- On the workstation, the unit serves the default directory `~/.agentsview`. The
  2026-09-25 host receipt filled it by default discovery, with no allowlist, and
  live mode keeps importing from every default and configured home. So the token
  protects it, not scoping.
- Measured on the workstation:
  - without a token, `/` returned 200, and `/api/ping`, `/api/v1/sessions` and
    `/api/v1/projects` returned 401;
  - with the unit running, the data-dir form of `agentsview projects --json`,
    `session list` and `session search` returned archive rows.

Alternatives were no token (rejected because of the routes above) and a reverse
proxy with its own login (another layer for a gap the upstream flag already
closes). An upstream release that removes or separately guards the
program-starting routes would overturn this.

### Live mode on the workstation (2026-09-27)

The user chose AgentsView as the live view of all jobs, so the unit no longer
passes `--no-sync`. At v0.43.0
([9be7745a](https://github.com/kenn-io/agentsview/tree/9be7745ad1906ee24e04eb05bb86c872ef0939a1)),
`serve` without it does the following:

- runs an initial sync
  ([main.go#L206](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L206));
- builds the sync engine
  ([main.go#L306-L325](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L306-L325));
- watches session files
  ([startFileWatcher](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L1969));
- polls directories it cannot watch every 2 minutes
  ([intervals](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L43-L45));
- runs a scheduled reconciliation every 15 minutes
  ([periodic sync](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L2726)).
  That pass covers only providers that declare `PeriodicReconcile`
  ([scheduledReconcileTargets](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/main.go#L2910-L2955)).
  Codex and Claude Code do not declare it, so their sessions arrive through the
  watcher and the 2-minute poll.

A worker lane that runs Codex with its own `CODEX_HOME` is outside the default
Codex directories. The workstation makes such homes visible by listing them
under `[agents.codex] homes` in the archive's `config.toml`. Listed homes add to
the default ones; `dirs`, the directory environment overrides and
`[[session_sources]]` are the supported alternatives
([alternate agent homes](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/docs/configuration.md#L988-L1013)).
The GPT-6 lane homes listed there are host-private paths.

Local observation (not a receipt): the unit restarted in live mode at
18:37Z. A later probe ran 14 `codex exec` sessions between 18:58Z and 19:04Z.
All 14 thread ids were listed without a manual sync, by:

```sh
agentsview session list --agent codex --active-since <start> \
  --include-automated --include-one-shot --include-children --json
```

Return to `--no-sync` for an archive that must stay frozen, such as one a
receipt cites, or if continuous sync's load or a parser regression harms the
host. The alternative was the frozen archive plus on-demand `agentsview session sync`
runs, which does not show jobs as they run.

[Context Mode Insight](https://context-mode.com/insight) is a separate hosted,
opt-in account. Opening its landing page does not connect local telemetry or
establish paid enrollment. Its Google/GitHub sign-in is separate from native
Codex/Claude accounts. No subscription or event forwarding was enabled here.

Grafana was verified with the browser's native defaults. A test session using
agent-browser's `--allowed-domains` option resolved Grafana's nested API URLs
incorrectly; the same page rendered normally without that option. This is a
bounded browser-profile limitation, not a missing dashboard. A 401 on Grafana's
anonymous user-stars endpoint has no `WWW-Authenticate` challenge and did not
produce a password prompt.
