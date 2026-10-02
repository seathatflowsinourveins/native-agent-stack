# North Star host and paper activation packet

Version 1, 2026-10-02. Prepared against recovery source
`2c669e18f705212f6f407b80f668d2a253591167`, based on
`a2ad39abd8c6827069395682f50d5058492a0f34`. This packet supplies the remaining
inputs to the [two-host architecture](2026-10-02-two-host-north-star-architecture.md)
and the standing [paper authorization](../paper-lane-policy.md). Its commands
are prepared steps, not newly executed host or broker acceptance.

## Current boundary

| Scope | Observed status / required input |
| --- | --- |
| Mac native clients | Coordinator reports Codex and Claude logged in; selected Codex model/effort is Sol Ultra. Preserve those sign-ins. |
| Mac Alpaca | `credential_status` reports `alpaca-paper` env store `MISSING`; both named Keychain checks exited 44/missing. Operator must provision the paper pair locally. |
| Mac IBKR | Native application `not_local`; owner must identify the signed-in paper TWS/Gateway destination. |
| Workstation | No surviving WSL identifier, approved transport, SSH configuration or remote connector supplied. Enrollment precedes native-client or GPU acceptance. |
| Current implementation | 523 unique offline tests passed, zero skips, all 14 bounded runs exited 0. No actual paper execution or WSL acceptance ran for this source. |

Offline evidence: coordinator artifact `recovery/acceptance-record.json`, SHA-256
`78c2d1050eb7d11baa5cf2e8069ddbbc99355cc7fee0fab2046ad3de3276645e`.
Sanitized registration at
`blueprints/us-equities/adaptive-paper/receipt-recovery-f1-20261002.json` is pending
in the integration branch. Exact commands, test IDs, raw logs, the earlier 133
dependency skips and two incomplete timeouts remain retained. Coverage:
[recovery](../../tests/test_adaptive_paper_recovery.py),
[CLI recovery](../../tests/test_adaptive_paper_recovery_wiring.py),
[transport](../../tests/test_adaptive_paper_transport.py),
[runner](../../tests/test_adaptive_paper_runner.py),
[safety](../../tests/test_adaptive_paper_safety.py),
[native faults](../../tests/test_native_faults_min.py),
[native execution](../../tests/test_adaptive_paper_native.py) and
[mover integration](../../tests/test_adaptive_paper_mover_native.py).
These are real pinned SDK/engine checks against fake broker ports, evidence class
SYN. The historical [native fault receipt](../../blueprints/us-equities/adaptive-paper/native-faults/receipt.json)
binds engine `dca821cc`; it does not qualify the changed runner.

## 1. Enroll the surviving host, then authenticate locally

The workstation owner supplies its host identifier, surviving distro, approved
access method, OS/architecture, accepted source revision and private receipt
destination. Follow the existing [WSL first-boot checklist](../../adoption/templates/wsl/first-boot-checklist.md)
and [F8 host-file/F9 bootstrap recipe](../../adoption/platforms/linux-wsl2-new-distro.md#f8-host-value-file).
Record storage, system/user-manager, cancellation and restart proofs. Removed
distro receipts cannot accept this destination; GPU/driver identity remains unknown.

After enrollment, the designated installation owner uses
`adoption/bootstrap-linux.sh --profile new-wsl-clean-foundation` from the accepted
source and completes its existing receipts. Native sign-in occurs once per host,
in the operator's terminal:

```sh
codex login --device-auth
claude auth login
python3 scripts/adoption_status.py --profile new-wsl-clean-foundation --json
python3 scripts/credential_status.py --json
```

Use [Codex native authentication](https://learn.chatgpt.com/docs/auth) and
[Claude native authentication](https://code.claude.com/docs/en/authentication).
Record installed clients and effective Sol Ultra selection using the
[existing native launch](2026-10-02-two-host-north-star-architecture.md#runtime-and-model-contract).
Native stores stay local. Configuration readback alone does not establish model
execution; required native-host proof is a separate owned run.

## 2. Reproduce the locked private trading runtime

Use the existing `trading-nautilus` [profile](../../adoption/manifest.json),
[runtime target](../../catalogs/us-equities/runtime-target.json) and
[combined requirements](../../blueprints/us-equities/adaptive-paper/requirements.txt).
The accepted Mac bundle contains CPython 3.13.15, Nautilus 2.0.0rc5 and Alpaca
0.44.0, with 20 official binary wheels. Obtain the coordinator's nonsecret bundle:

- `requirements-macos-arm64-py313.lock`, SHA-256 `31f5ef188b855d5eb40a707a0086ed4a5d4376d84c49b1b710e15b1c96cac8f4`;
- `artifact-provenance.json`, SHA-256 `a491313505218a782b142e6af30fb58a21f8066562deeb2d54dc879e9d9eb468`, with wheel digests, licenses and official source URLs.

The owner sets `TASK_ROOT` to a new absolute private directory outside the
checkout, supplies `TASK_PYTHON` as the qualified CPython 3.13 interpreter, and
places that verified lock and wheel bundle there:

```sh
set -eu
: "${TASK_ROOT:?owner-assigned private directory}" "${TASK_PYTHON:?qualified CPython 3.13}"
uv --no-config venv --python "$TASK_PYTHON" --no-python-downloads \
  --cache-dir "$TASK_ROOT/cache" "$TASK_ROOT/runtime"
uv --no-config pip sync --python "$TASK_ROOT/runtime/bin/python" \
  --no-index --find-links "$TASK_ROOT/wheels" --require-hashes \
  --only-binary :all: --cache-dir "$TASK_ROOT/cache" \
  "$TASK_ROOT/requirements-macos-arm64-py313.lock"
uv --no-config pip check --python "$TASK_ROOT/runtime/bin/python"
```

Retain versions, commands, exits and offline receipts.
Official artifacts are [Nautilus rc5](https://pypi.org/project/nautilus-trader/2.0.0rc5/)
and [Alpaca 0.44.0](https://pypi.org/project/alpaca-py/0.44.0/).
The Mac ARM64 lock cannot accept WSL. A Linux-compatible official wheel lock and
its destination checks remain required; missing binary artifacts block setup.

## 3. Complete read-only paper preflight before orders

On Mac, the operator enters the pair through local prompts, once:

```sh
secret set APCA_API_KEY_ID
secret set APCA_API_SECRET_KEY
secret run APCA_API_KEY_ID APCA_API_SECRET_KEY -- \
  "$TASK_ROOT/runtime/bin/python" blueprints/us-equities/adaptive-paper/runner.py \
  preflight --credentials keychain-env \
  --config blueprints/us-equities/adaptive-paper/config.json \
  --output "$TASK_ROOT/alpaca-preflight.json"
```

Values never enter chat, argv, logs or source; keys and native stores stay local.
Injection belongs to that command only. WSL has no Mac login Keychain: use its
locally provisioned, guarded source only after the
[credential policy](2026-09-22-broker-credential-handling.md) passes.
Verify the assigned paper account privately, `ACTIVE`/unblocked state, paper
endpoint, feed/entitlement, quote age, session/clock and existing orders/positions.
The [Alpaca paper protocol](../../blueprints/us-equities/engine-nautilus/acceptance-plan.md#6-alpaca-paper-procedure)
and [official paper documentation](https://docs.alpaca.markets/us/docs/paper-trading)
govern that independent boundary.

For IBKR, sign in through native paper TWS/Gateway with execution disabled and
Read-Only API enabled. The owner supplies the verified host, paper port
(Gateway 4002 or TWS 7497), unused client IDs and qualified probe interpreters.
Run the existing [read-only probes](../../blueprints/us-equities/engine-nautilus/ibkr-acceptance/README.md):

```sh
"$IBAPI_PYTHON" blueprints/us-equities/engine-nautilus/ibkr-acceptance/ibapi_probe.py \
  --host "$IBKR_HOST" --port "$IBKR_PORT" --client-id "$IBAPI_CLIENT_ID" \
  --receipt "$TASK_ROOT/ibapi.json"
"$TASK_ROOT/runtime/bin/python" blueprints/us-equities/engine-nautilus/ibkr-acceptance/nautilus_probe.py \
  --host "$IBKR_HOST" --port "$IBKR_PORT" --client-id "$IBKR_CLIENT_ID" \
  --ibapi-receipt "$TASK_ROOT/ibapi.json" --receipt "$TASK_ROOT/ibkr-native.json"
```

Require a fresh passing same-endpoint receipt and exactly one managed `DU` paper
account before order admission. Record sanitized contract/currency/exchange,
permissions, data mode/age and positions/open orders; keep the account ID private.
Missing runtime, identity or read-only evidence leaves IBKR blocked. Use the
[official native IBKR integration](https://nautilustrader.io/docs/latest/integrations/interactive_brokers/).

## 4. Freeze and execute each broker's remaining contract

The coordinator freezes numeric limits, instruments/session, feed,
request/cleanup reserves, IDs, disposition and source hashes under the
[acceptance plan](../../blueprints/us-equities/engine-nautilus/acceptance-plan.md).
One writer owns each account. A durable intent/order/fill/fee journal reserves
before send; unknown identity, missing fills, snapshot/cash contradictions or
expired budgets stop entries. STOP survives restart; retain the same ledger,
account scope and budget history. Apply the existing
[recovery contract](../../blueprints/us-equities/adaptive-paper/README-recovery.md).

| Broker | Mandatory actual-paper evidence still required |
| --- | --- |
| IBKR rc5, single DU | Submit/acknowledge, fill/cancel and commission cash match; reconnect with an owned open order; process restart with working orders and historical fills; STOP/kill and restart retaining the halt; confirmed boundary cancel/flatten disposition. Exact order/execution IDs and quantities, zero duplicate effects and unexplained differences. |
| Separate Alpaca adapter | Accepted submission with lost response/timeout resolved by original client ID without another POST; nine-decimal partial/duplicate/late fills and cancel races; 429/5xx exhaustion with bounded backoff and cancel/reconcile reserve; stream disconnect/in-flight process restart; persistent STOP and fresh final order/position/cash/fee reconciliation. Unobserved faults remain unobserved. |

The [IBKR order harness](../../blueprints/us-equities/engine-nautilus/ibkr-paper-orders/README.md)
is historical 1.231.0 evidence, not an executable rc5 closure packet. A supported
rc5 order/fault harness and its frozen receipt binding remain missing.
The dated target records [5007](https://github.com/nautechsystems/nautilus_trader/issues/5007),
[5057](https://github.com/nautechsystems/nautilus_trader/issues/5057) and
[5060](https://github.com/nautechsystems/nautilus_trader/issues/5060) as open;
retain those gaps until release/source and native evidence resolve them.
The [Alpaca native-fault harness](../../blueprints/us-equities/adaptive-paper/native-faults/README.md)
covers a narrower resting-submit/cancel/refusal contract; it needs the documented
account-identity/clock preflight and fresh source binding and cannot close the
additional ambiguity/partial/throttle/restart cases by itself.

Each case ends with source/runtime/input hashes, exact commands/exits, durable
journal before/after, outbound requests, independent account observations and
PASS/FAIL/BLOCKED or unobserved outcome. Required missing cases keep that broker's
gate open. Source integration, host activation, strategy merit and live acceptance
remain separate decisions.
