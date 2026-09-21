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

OmniRoute 3.8.50 is an optional, separately started Windows gateway profile. Its
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
  --no-browser --no-update-check --background
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
```

Do not run a second background daemon beside this unit. It retains the same
archive and `--no-sync` scope. This is native process supervision, not a new
session importer or proof of physical-PC reboot recovery.

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
