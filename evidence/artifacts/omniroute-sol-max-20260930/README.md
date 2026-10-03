# 20128 at max effort for gpt-6.1-sol: upstream PR 15167 on the running build, 2026-09-30

Record of the restart of the 20128 gateway (`omniroute.service`) at 2026-09-30T06:32:50Z onto build `cf6748d04` (the running build `ae5539a56` plus the one commit of
upstream PR 15167, head `f5d8e150b79e0901fa18241c7f29bff889b87c14`), of its qualification and of the read-backs; claims, evidence classes and residuals are in `receipt.json`. The decision is the
2026-09-30 update in [`docs/decisions/2026-09-30-omniroute-rebuild.md`](../../../docs/decisions/2026-09-30-omniroute-rebuild.md).

| Files | What they are | Class |
| --- | --- | --- |
| `checks/upstream-pr-15167-identity.txt`, `checks/codex-bundled-catalog-0159.2.txt` | the PR's identity and patch-ids from git alone; the effort levels Codex 0.159.2 lists for the GPT-6 models | source review |
| `checks/calllog-effort-counts-before-switch.json`, `checks/calllog-effort-counts-after-switch.json` | counts of requested and upstream effort per model from 20128's call_logs (metadata columns, read-only) | our check |
| `checks/effort-wire-*.json` | what the Codex executor would put on the wire for 13 requests, on the running build's source and on the candidate's | our check |
| `checks/qualification-*.txt` | install, boot smoke (shim v1 as installed), upstream check:pack-boot, targeted tests on the candidate and on the running build's source | upstream check and our check |
| `checks/preflight-*.txt`, `checks/preflight-*.json` | the restart-blocking preflight trap (control with shim v1), the fix with shim v2, a second real instance still refused, and the scratch-port tables | our check |
| `checks/switch-output.txt`, `checks/readback-after-switch.txt`, `checks/unit-before-after.diff`, `checks/omniroute.service.after-switch.txt` | the switch script's output, the units' states and hashes, the three changed unit lines, the installed unit | our check |
| `checks/owner-record-*.json`, `checks/owner-record-diff.txt` | `gateway_record.py` (schema 2, both ports) before and after, and the path-by-path difference | our check |
| `checks/probe-gate-before-switch.json`, `checks/probe-gate-after-switch.json` | the same probe script before and after: statuses and the effort columns of each request | live model calls |
| `checks/sharedgw-connection-expiry-20260930.txt` | the 05:50Z to 05:55Z incident on 20129's sharedgw node and its repair (a transcription of printed outputs) | our check |
| `scripts/` | the harness as it ran, `lsof-shim-v2.sh.txt` (sha256 `b6ae900224df3dc73fff2a50b3d7206d78895c6147e93e80b62e66d423e69854`), and the diff of `switch_gateways.py` | our tools, not upstream |

Host paths are masks (`<NS>`, `<B3>`, `<B2>`, `<TOOLS>`, `<HOME>`, `<STATE>`); colour codes are removed; nothing else in an output is edited.
