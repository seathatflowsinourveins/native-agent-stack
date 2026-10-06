# NativeStack2604 ai-memory health observation

The canonical plan already binds the manual status command with
`AI_MEMORY_SERVER_URL=http://127.0.0.1:29374`. Preserve that binding and require
the native JSON `client.server_url` to equal the same origin. A successful status
from another endpoint cannot qualify this host's memory service.

The co-op's P3-11 direction reports a default-target timeout in its H2H caller and
a successful explicitly bound status. That is not a reproduced failure of the
canonical plan: the current main and held #723 copies already carry the override.
The stale H2H caller remains with its owner; this change adds a discriminating
observation gate and regression controls to the owned plan row.

Sources: [akitaonrails/ai-memory@7580b74d config.rs:664](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L664)
captures the environment selector; [1655-1656](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/config.rs#L1655)
overrides the configured server URL. [status.rs:203,231](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/status.rs#L203)
requests `/admin/status` and reports the selected endpoint. No credential or
configuration store is read by this repository change.

Synthetic controls execute the exact canonical health program: an inherited old
49374 selector is overridden; removing the binding fails; status failure remains
nonzero under pipefail; and a zero-exit status reporting 49374 fails the oracle.
The last control reproduced a false pass before the new check. These are local
integration/synthetic controls, not a new service or producer acceptance.

Current organic before and after counts are unknown: no matching task window
separates organic invocation from probes and fixtures. Historical T0 zeros are
reference only, with explicitly inadequate exposure. Host apply/acceptance is
pending the command center's ACK and the co-op's read-only stage check. No lane
host write, forced sign-in or new provider/model run is part of this change.

Alternatives were adding `--config` and copying host configuration, or changing
the service itself. The supported per-command selector and returned endpoint
avoid both dependencies. Reconsider if upstream changes the status/configuration
contract; retain the wrong-target and failure-propagation controls.
