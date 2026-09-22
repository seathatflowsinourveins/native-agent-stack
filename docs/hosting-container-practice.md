# Hosting, containers and runtime workers

The [pinned deployment comparison](../catalogs/landscape/hosting-practice.json)
retains native Linux/WSL services, systemd and Dagu for the qualified local work.
Docker/Compose and Podman/Quadlet are credible conditional choices. No container
trial in this review establishes that either wins or fails on our workload.

| Requirement | Current choice | Candidate and adoption trigger |
| --- | --- | --- |
| Local coding/research workers | Native Codex/Claude, bounded roles and owned worktrees | Supported SDK or durable graph only for a demonstrated missing task/effect/recovery capability |
| Local service scheduling/supervision | Existing systemd and Dagu evidence | Compose for a selected multi-service OCI package; a durable scheduler for an actual host-loss/long-wait requirement |
| OCI dependency packaging | No new default engine | Docker Engine/Compose when a maintained upstream image or deployment constraint closes a measured gap |
| Rootless, systemd-managed containers | Native services remain accepted | Podman/Quadlet when privilege or service management is the requirement; qualify networking, volumes and API/GPU compatibility |
| IBKR gateway for Nautilus | Native external TWS/IB Gateway remains a valid path | Optional DockerizedIBGateway, independently qualified for image, sign-in, session restart and broker state |
| Production or remote/GPU hosting | No provider selected merely by catalog presence | Define availability, data/network scope, rollback, resources and workload cost before one targeted deployment trial |

For a container trial, follow [Docker build guidance](https://docs.docker.com/build/building/best-practices/):
record image digests, lock application dependencies and separate build/runtime
concerns where useful. Retain controlled updates and rollback. Keep credentials
outside images, source control and public receipts. Rootless Docker and
[Podman Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html)
have distinct prerequisites; neither is a blanket substitute for workload checks.

On WSL, use Linux-filesystem mounts and explicit resource limits. Select one
intended engine integration; Docker documents conflicts between its Desktop
integration and a separately installed engine/CLI in WSL.
[WSL performance](https://docs.docker.com/desktop/features/wsl/best-practices/)
and [engine setup](https://docs.docker.com/desktop/features/wsl/).
Do not add a second engine as a routine catalog refresh.

The selected [Nautilus IBKR source](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md)
starts `DockerizedIBGateway` separately and passes its host/port to client configs;
putting `dockerized_gateway` in those configs raises `ValueError`. Its default
gateway image uses the mutable `stable` tag, so retain the resolved digest before
a qualification trial. Image availability does not establish broker acceptance,
and existing Alpaca results do not qualify this IBKR path.

Compare one chosen container lane with the current native implementation using
the same locked application/database checks. Include installation, startup and
rebuild times, resources, networking, persistence, isolated backup/restore,
interruption recovery and cleanup. Add GPU or broker tests only for the selected
workload. Native services remain selected unless the challenger closes a concrete
gap while preserving the required behavior. Production uptime, hostile-code
isolation and another PC each need their own evidence.
