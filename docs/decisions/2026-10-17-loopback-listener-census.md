# Decision: a loopback-only listener census on the workstation (2026-10-17)

**Status:** adopted. Templates and the script are in this repository. NativeHorizonNY has run an equivalent census
every 5 minutes since 2026-10-17.

## Rule

- **Loopback binds only.** Every TCP and UDP listener binds loopback only: 127.0.0.0/8, ::1, or ::ffff:127.0.0.0/104.
- **Alert on any other listener.** A census runs every 5 minutes and alerts on any listener outside loopback.
- **One exception:** WSL's own DNS tunnel at 10.255.255.254:53. It is the nameserver that resolv.conf names on a
  mirrored WSL host, and WSL manages it.

## Why

- **The owner's choice.** On 2026-10-17 the owner chose to run dashboards and local services without passwords on this
  single-user PC.
  - Each service uses its upstream's own no-auth or anonymous mode, for example dagu `auth.mode: none`.
  - The credential rails stay strict.
- **The bind is the compensating control.**
- **WSL here runs in mirrored networking.** `wslinfo --networking-mode` printed `mirrored` at 2026-10-17T14:41:21Z.
- **What mirrored mode does.** Microsoft's WSL networking documentation (https://learn.microsoft.com/windows/wsl/networking,
  "Mirrored mode networking", read 2026-10-17):
  - it "mirrors" the Windows network interfaces into Linux;
  - one of its listed benefits is "Connect to WSL directly from your local area network (LAN)".
  - So a wildcard or interface bind can reach the LAN, while loopback reaches only this PC's own processes.
- **The command center's rulings.**
  - #17467 (2026-10-17T03:52:50Z), item 5: keep the loopback-only invariant.
  - #28846 (2026-10-17T13:31:27Z), part (b): ship the census and its timer as their own pull request, stating the rule
    exactly as above.

## How

- **`scripts/loopback_census.py`.**
  - It reads `ss -H -l -t -u -n -p` (iproute2 ss(8), 6.19.0 on the workstation): listening TCP and UDP sockets,
    numeric, with the owning process and no header.
  - It prints one JSON line: `check`, `at`, `listeners`, `violations`.
  - It exits 1 when any listener breaks the rule, and 0 otherwise.
  - Process names come from ss's users field when ss can see them. argv is never read.
- **`adoption/templates/systemd/loopback-census.service`.**
  - A timer-triggered oneshot. A breach fails the unit, so `OnFailure=stack-alert@%n.service` sends the command center
    one named hcom message.
  - It keeps the newest JSON line in `$XDG_STATE_HOME/loopback-census/last.json`.
- **`loopback-census.timer`** starts the service every 5 minutes (`OnUnitActiveSec=5min`, systemd.timer(5)).

## Residuals

- **Scope.** The census sees the listeners of this distribution's network namespace that ss reports.
  - The other WSL distribution, Windows processes and container namespaces are outside it.
  - Sockets owned by other users show no process name.
- **Detection, not prevention.** A breach is found within 5 minutes. Each service's own bind setting stays the first
  control.
- **Exposure that remains.** Each no-auth service is still reachable by local processes. This rule is that residual's
  control, not its removal.
