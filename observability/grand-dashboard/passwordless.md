# Seamless local observation and native LLM workflow

The normal front door is [the grand dashboard](http://127.0.0.1:13000/d/research-grand?refresh=30s).
It opens without a password using Grafana's upstream anonymous **Viewer** mode.
The listener remains `127.0.0.1:13000`. Routine viewing, telemetry and research
progress do not require copying a credential or starting a model conversation.

The native Grafana configuration is:

```ini
[server]
http_addr = 127.0.0.1
http_port = 13000
[auth.anonymous]
enabled = true
org_name = Main Org.
org_role = Viewer
```

This configuration is included in the portable backend template. For an existing
installation, preserve its paths, datasource provisioning and administrator
environment file; update only these settings and restart
`ecosystem-grafana.service`. The organization name must match the native instance.
Anonymous Viewer can query the local organization's permitted telemetry, including
sanitized labels. This is a personal local observation boundary, not a tenant or
internet publishing design. To undo it, set `enabled = false` and restart Grafana.

## Native verification

A fresh browser session with no credential entry loaded the dashboard and its
historical results. Native requests without authorization headers or cookies
returned:

| Request | Direct result |
|---|---|
| `GET /api/health` | 200 |
| `GET /api/dashboards/uid/research-grand` | 200; canEdit/canSave/canAdmin/canDelete all false |
| `GET /api/admin/settings` | 403 |
| `GET /api/access-control/user/permissions` | 200; read/query permissions, no observed write/create/delete permissions |

The original authenticated dashboard receipt remains dated evidence. This
follow-up changes local viewer access only; private native model sign-ins remain
in their own account homes. A short connection-refused response immediately
after restarting Grafana was followed by a successful readiness check and fresh
navigation, not a repeated account login.

## Native workers and workflow history

Codex SDK workers reuse the explicit native Codex home; Claude uses its native
saved authentication. The accepted Dagu pipeline invokes those clients directly,
with a small source-linked packet and bounded tool policy. The completed native
[paired review](../../blueprints/us-equities/convergence-program/review-receipt.json)
already demonstrated ordinary runs without an interactive password prompt.
Future provider-mandated reauthentication uses the native sign-in flow; secrets
are not copied into Git, prompts or dashboards.

The upstream command reads local history without a browser login:

```sh
"$DAGU_BIN" history research-pair --context local \
  --dagu-home "$RESEARCH_HOME" --format json --last 30d --limit 10
```

Its accepted result contained **two succeeded runs**, each **27 seconds**:
`2026-09-19T19:41:23Z` to `19:41:50Z`, and `21:58:33Z` to `21:59:00Z`.
These are prior real research runs; viewing them does not spend model tokens.
The optional adapter omits raw run identifiers, paths, parameters and errors.
Enable it using the existing installer with both explicit native paths:

```sh
python3 observability/grand-dashboard/install.py \
  --repo "$STACK_REPO" --config "$OBSERVABILITY_CONFIG" \
  --units "$USER_UNIT_ROOT" --data "$OBSERVABILITY_DATA" \
  --dagu-bin "$DAGU_BIN" --dagu-home "$RESEARCH_HOME"
systemctl --user daemon-reload
systemctl --user start ecosystem-research-progress.service
```

Installation and activation exited 0. Native Loki returned the summary and two
run rows; Grafana's anonymous API and fresh browser both showed **15 panels**.
`acceptance.py --output "$NEW_PRIVATE_ACCEPTANCE"` reported **10 native queries,
3 generation checks, passed**. The adapter's twelve focused tests and independent
review passed; the adopted SDK environment passed all **202 tests** without skips.
Missing or failed native history is explicitly unavailable, not zero or success.

The Dagu
operator UI keeps its existing protection: upstream `auth.mode: none` does not
mean anonymous read-only, because some workspace/scheduler operations bypass the
two DAG run/write switches. Models continue using native commands for authorized
work rather than an unprotected browser control endpoint.

This setup adds no authentication proxy, token forwarding, remote model route,
paid host or automatic broker execution. New machines adopt the same native
recipes, sign in locally once where required, and perform their own acceptance.

Primary sources: [Grafana anonymous access](https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/anonymous-auth/),
[Dagu 2.16.6 workspace role behavior](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/service/frontend/api/v1/workspace_access.go#L305),
[Dagu DAG write permission](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/service/frontend/api/v1/workspace_access.go#L355).
