# Native archive refresh and optional gateway recovery

Observed on 2026-09-21. These results extend the [rendered dashboard checks](native-dashboard-data.md) with two actual operational recoveries. Native commands and original outputs remain in the authoring host's private `dashboard-gap-resolution-20260921/operations` evidence directory; screenshots contain selected local history and remain private.

## Refresh only the selected archive

AgentsView 0.43.0 is a deliberately scoped archive. Its `--no-sync` server does not continuously import every session. Refresh each explicitly selected source with its [native single-session command](https://github.com/kenn-io/agentsview/blob/9be7745ad1906ee24e04eb05bb86c872ef0939a1/cmd/agentsview/session_sync.go):

```sh
agentsview session sync "$SELECTED_NATIVE_SESSION_FILE" \
  --server http://127.0.0.1:17384
agentsview session list --server http://127.0.0.1:17384 \
  --include-one-shot --include-automated --include-children --json
```

This recovery refreshed the same current Codex file and two previously selected Claude files. All three commands returned `synced`. The Codex archive record increased from 2,249 to 2,753 messages, and its latest recorded event advanced from 02:30:21 UTC to 13:27:39 UTC. The completed Claude records remained at 19 and 6 messages. All 17 session identities were preserved; every unselected row was unchanged.

The [native dashboard](http://127.0.0.1:17384/) rendered 17 sessions and 3,697 total messages, matching the native command's records. It displayed the selected Codex session and archive synchronization as “just now.” This is a refreshed snapshot: later conversation events require another explicit refresh. Fourteen top-level rows and seventeen rows including children are different, legitimate scopes.

## Recover the existing FreeLLMAPI desktop profile

The installed [FreeLLMAPI desktop 0.11.0](https://github.com/tashfeenahmed/freellmapi/releases/tag/v0.11.0) was stopped. Its existing selective Windows launcher starts the upstream executable with the saved desktop profile directory:

```powershell
& "$StackRoot\bin\start-services.ps1" -Service FreeLLMAPI
Invoke-RestMethod http://127.0.0.1:31415/livez
Invoke-RestMethod http://127.0.0.1:31415/readyz
```

Returned results after launch:

```json
{"status":"ok","version":"0.4.1","uptime_s":37}
{"status":"ok","ready_upstreams":1}
```

The desktop release and bundled server report different version numbers. Native routes, provider configuration, compression, caching and account defaults were unchanged. Readiness establishes one ready configured upstream, not a new inference or savings benchmark. No provider request was generated.

The existing account also passed the upstream authentication protocol: `POST /api/auth/login` returned HTTP 200 and a token; `GET /api/auth/status` returned HTTP 200 with `authenticated: true` and `needsSetup: false`; `POST /api/auth/logout` returned HTTP 200. Credentials and tokens stayed in the verification process and were not retained in receipts.

## Distinguish the desktop interface from browser sign-in

The bundled desktop frontend has an upstream `__FREEAPI_SESSION__` bridge for automatic local authentication. The ordinary [browser interface](http://127.0.0.1:31415/) displays a sign-in form instead. Its email validator rejects the existing desktop-generated localhost account before submitting the login request. This is an observed interface incompatibility; the authenticated native API accepts the same account.

An `agent-browser auth login` success message alone did not establish login: the rendered screenshot exposed this validation error. Its temporary verification vault entry was removed. No account, email address, password or frontend validator was changed to hide the difference.

The supported passwordless path is the installed **native desktop opener**, which preserves the recorded profile:

```powershell
node "$StackRoot\bin\open-component.cjs" FreeLLMAPI
```

The upstream [single-instance handler](https://github.com/tashfeenahmed/freellmapi/blob/955e9cf6413314d461d8130f695a81b8c5f246fe/desktop/src/main.ts#L61) opens the existing authenticated dashboard on another native launch. Its [window creation](https://github.com/tashfeenahmed/freellmapi/blob/955e9cf6413314d461d8130f695a81b8c5f246fe/desktop/src/window.ts#L18) and [preload](https://github.com/tashfeenahmed/freellmapi/blob/955e9cf6413314d461d8130f695a81b8c5f246fe/desktop/src/preload.ts#L1) supply and refresh the machine-account session automatically. No web-form workaround is necessary.

This native path was then inspected using the installed `agent-browser` Electron workflow. A temporary launch with Electron's loopback debugging flag enabled attachment to the actual desktop renderer:

```sh
agent-browser skills get electron
agent-browser --session free-native-inspection \
  --cdp http://127.0.0.1:19226 snapshot -i
agent-browser --session free-native-inspection \
  --cdp http://127.0.0.1:19226 screenshot native-dashboard.png
```

The personally viewed screenshot showed the authenticated Models page with the existing two local models. The renderer reported `nativeDesktop: true`, `bridgePresent: true`, desktop version `0.11.0`, and zero password inputs. Selecting Analytics showed 15 retained requests and 100% success over seven days. Its native `/api/analytics/summary?range=7d` response independently returned **1,861 input tokens, 82 output tokens, 15 lifetime requests, and zero estimated cost savings**. These are historical gateway records, not new inference or token savings.

The inspection session was closed, the desktop app was restored to its ordinary launch without debugging flags, and readiness again returned HTTP 200 with one ready upstream. The temporary debugging port was confirmed closed. The normal native opener then opened the desktop dashboard for use. The earlier ordinary-browser validation failure and WSL Computer Use limitation remain historical evidence; the authenticated native desktop inspection resolves the practical dashboard-access gap.
