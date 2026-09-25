# Portable guarded runners and the switch tool

Two host-local launchers that keep a heavy maintenance job, and every process it
spawns, inside its own native systemd scope with hard memory, task and runtime
limits, plus a CPU quota where the user manager delegates the cpu controller. They exist because an unbounded scan or build on a WSL2 host can exhaust
the VM and take the whole session down; the scope kills the job instead.
A third script, `gitleaks-guarded-macos`, applies the same Gitleaks caps on
macOS, which has no per-job cgroup (see "macOS" below). A fourth tool,
`ecosystem-switch`, is unrelated to job containment: it is the one atomic
switch point a host uses to move an already-adopted component from one
installed version to another (see "ecosystem-switch" near the end of this
page).

| Script | Role |
| --- | --- |
| `ecosystem-bounded-run` | Generic launcher: runs `COMMAND [ARG ...]` in a transient `--user --scope` unit with `MemoryHigh`/`MemoryMax`/`MemorySwapMax`/`TasksMax`/`RuntimeMaxSec` applied, and `CPUQuota` where cpu is delegated (see "CPU quota" below). Refuses to run at all when it cannot contain the job. |
| `gitleaks-guarded` | Gitleaks front end: preserves upstream Gitleaks argument and exit-code semantics, adds a per-user non-blocking lock so two scans cannot run at once, and delegates the actual scan to `ecosystem-bounded-run`. |
| `gitleaks-guarded-macos` | macOS Gitleaks front end: the same argument and exit-code semantics, a per-user lock that waits up to 60 s, and a footprint watchdog that kills the scan's whole process tree above 6 GiB or after 600 s. Python 3 standard library only. |
| `ecosystem-switch` | Python-stdlib CLI: one `current/<id>` indirection per adopted component, flipped atomically by `apply`, gated by a receipt/window/memory/drift check, with a hash-chained ledger and an automatic rollback on a failed post-apply verify. |

## Provenance

`gitleaks-guarded-macos` has no external source: it was written in this
repository on 2026-09-24, after the macOS memory incident described below. The
rest of this section covers the two Linux scripts.

- Source: the `bin` directory of the private `codex-ecosystem` checkout on the
  WSL2 host that developed them (not published here; the two files below are the
  whole of what was copied).
- Copied: 2026-09-22.
- Original sha256 as read with `sha256sum` at copy time:
  - `ecosystem-bounded-run` —
    `7680fe1173b35a8472023772c8973c4a9b65c4e444414ac44efa199cbabe17db`
  - `gitleaks-guarded` —
    `66db06f653520ad49c2531ab2d5df762d1e952b1d1655ba5f509b6014cbc52f1`
- `ecosystem-bounded-run` was byte-for-byte identical to its source at copy
  time. On 2026-09-22 a cross-family review fix changed this repository's copy
  (see "Divergence in `ecosystem-bounded-run`" below), so it now hashes to
  `77c47d2dfea465a64ec7c7af8c80fe932d4bc43047d7608eee45ef13f6838a70`; the
  `7680fe11…` value above identifies the unmodified source only.
- `gitleaks-guarded` differs from its source on two lines only (see below), so
  the copy in this repository hashes to
  `61e87881841a346fc0c4d2ec514b283696311ce033fd7b27397973fc2429a655`. Compare
  against *that* value when checking this repository's file, and against the
  `66db06f6…` value when checking a copy taken straight from the source host.
- Re-synced 2026-09-24 for the CPU quota (see "CPU quota" below). The change
  was made on the source host first and copied here. Before it, the host's
  runner hashed `77c47d2d…`, identical to this repository's copy, so the host had
  already received the 2026-09-22 divergence fixes described below.
  - `ecosystem-bounded-run` is byte-for-byte identical to the host runner:
    `cde3374b1a6146d89a768fbe99d80ef934c150e0bad1a50e53bc73d3bc3c9c0e`.
  - `gitleaks-guarded` gained one line on both sides, `unset
    ECOSYSTEM_JOB_CPU_QUOTA`, and still differs from its source on lines 5 and
    6 only. The host source now hashes
    `0a645ac84a6a2172526ca968bfb7c83616194d145054fab6c190bd57a56e3703`, and this repository's copy hashes
    `7ead675d3a539b964e6d432427e5564cc9fa228e9196e715731d51c916a3acc9`.

### Exact lines changed in `gitleaks-guarded`

Only lines 5 and 6 differ from the source. Both originally held a literal
personal home path, which this repository forbids and which would not resolve on
another host.

| Line | Was | Is now | Why |
| --- | --- | --- | --- |
| 5 | a literal absolute path to the pinned Gitleaks binary under one user's home | `gitleaks_native="${GITLEAKS_NATIVE:-${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/gitleaks-8.30.1/gitleaks}"` | Resolves through the same `ECO_INSTALL_ROOT` contract the bootstrap scripts use, with `GITLEAKS_NATIVE` as an explicit override. The pinned version string `gitleaks-8.30.1` is unchanged. |
| 6 | a literal absolute path to `ecosystem-bounded-run` in one user's checkout | `gitleaks_runner="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/ecosystem-bounded-run"` | The guarded launcher finds its runner next to the path it was invoked with, so the pair stays correct wherever it is installed as long as the two files are installed together. `${BASH_SOURCE[0]}` is not symlink-resolved; see the install section. |

Nothing else in `gitleaks-guarded` differs from its source. Line 21, `unset
ECOSYSTEM_JOB_CPU_QUOTA` (added on both sides on 2026-09-24), gives every scan
the runner's default CPU quota, whatever job defaults the caller exported, in the
same way the explicit memory, swap, task and time exports above it do. Every absolute `/usr/bin` tool path
(`/usr/bin/systemd-run`, `/usr/bin/systemctl`, `/usr/bin/timeout`,
`/usr/bin/flock`), every exit code (`64` usage, `75` lock held by another scan,
`78` refusal to run uncontained) and every default limit (`MemoryHigh=4G`,
`MemoryMax=6G`, `MemorySwapMax=0`, `RuntimeMaxSec=600`, `TasksMax=256`) is
unchanged.

### Divergence in `ecosystem-bounded-run` (2026-09-22)

Two cross-family review rounds found three gaps, and fixed them in this repository's
copy first. The host original has since received the same fixes: on 2026-09-23 its
runner hashed `77c47d2d…`, identical to this copy before the CPU quota re-sync.

| Gap in the source | Change here |
| --- | --- |
| A successful `systemd-run --scope` did not prove the limits were enforced: systemd starts the scope and masks a limit whose controller an ancestor does not delegate, so the command could run with no memory or task cap. | The scope now starts `/bin/sh` with an in-scope check instead of the command. It reads the job's own `/proc/self/cgroup`, requires the leaf to be this run's unit, and requires the cgroup's `memory.max` to equal the requested `MemoryMax` rounded down to a whole page (`getconf PAGESIZE`) and `pids.max` to equal `TasksMax`. Otherwise, or if the command is not found, it exits 78 before the command runs. When the check passes, it `exec`s the command, so the command keeps the scope, PID, stdin and argument vector. A `MemoryMax` too large for 64-bit byte arithmetic is refused with 78 before anything starts. `MemoryHigh`, `MemorySwapMax` and `RuntimeMaxSec` are still applied but not re-read. |
| A launcher failure after the filesystem prechecks passed (a stale user-bus socket makes `systemd-run` exit 1 with `Failed to connect to bus`) propagated the launcher's status instead of 78. | The in-scope check creates a start marker in a private `mktemp -d` directory under `/run/user/$UID` immediately before `exec`. Without the marker the runner exits 78 (`command was not started`), whatever status the launcher returned. With it, the command's own status is returned unchanged, including 78 from the command itself. A missing command now yields 78, where the source returned `systemd-run`'s 1. |

The limit defaults, exit codes 64/78, the `/usr/bin` tool paths and the signal
handling (129/130/143 after a native scope stop) are unchanged. The marker
directory is removed on every exit path.

- The command lookup mirrors `exec`: a path must be an executable file, and a bare name must be an executable file in a `PATH` directory. A shell builtin with no file (for example `cd`) is refused with 78 before the start marker instead of failing with 127 after it (second cross-family review round, 2026-09-22).

## CPU quota (2026-09-24)

`ecosystem-bounded-run` adds `CPUQuota=` to the scope when the user manager
delegates the cpu controller, that is, when `cpu` appears in
`/sys/fs/cgroup<ControlGroup>/cgroup.controllers` for the manager's
`systemctl --user show --property=ControlGroup` path. A controllers file that
cannot be read means a wrong manager path and is refused with 78.

- **Default:** (online CPUs − 2) × 100%, with a floor of 100%. On a 24-CPU host
  that is `cpu.max` `2200000 100000`.
- **Override:** `ECOSYSTEM_JOB_CPU_QUOTA`, a positive percentage of one CPU
  (for example `200%`). Any other value is refused with 78.
- **Checked from inside the scope,** like the memory and task limits. The
  job's own `cpu.max` must equal the requested quota (N% is N ms of CPU per
  100 ms period), or the runner exits 78 before the command runs.
- **Without cpu delegation:** systemd's `user@.service` delegates cpu by
  default only from v252; Ubuntu 22.04 ships `Delegate=pids memory`. There, the
  default quota is skipped with one stderr note (`no CPU quota`), and the
  memory, task and runtime limits still apply. An explicit
  `ECOSYSTEM_JOB_CPU_QUOTA` is refused with 78, because it cannot be enforced.
  Delegation can be added with a drop-in
  `/etc/systemd/system/user@.service.d/delegate.conf` containing
  `[Service]` / `Delegate=cpu memory pids`, then `systemctl daemon-reload` and
  a new login. That drop-in has not been exercised by this repository's tests.
- **What it does not do:** the quota is per job and leaves two CPUs free. It
  does not throttle a scan that uses fewer cores. The measured Gitleaks peak of
  about 8.4 cores (`docs/next-host-stages.md`) runs unthrottled on any host with
  11 or more CPUs, and several concurrent jobs are not capped in aggregate. A
  lower scanner quota or a slice-level aggregate cap needs a measured comparison
  of scan duration against the 600 s bound, and of interactive CPU pressure,
  first.

## Install on a new Linux/WSL2 host

The agent rule these scripts serve assumes a PATH-resolved `gitleaks` *is* the
guarded launcher, so that no caller can reach the raw binary by habit.

```bash
export ECO_INSTALL_ROOT="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
mkdir -p "$ECO_INSTALL_ROOT/bin"

# Keep the pair together: gitleaks-guarded resolves its runner next to itself.
install -m 0755 adoption/tools/ecosystem-bounded-run "$ECO_INSTALL_ROOT/bin/ecosystem-bounded-run"
install -m 0755 adoption/tools/gitleaks-guarded      "$ECO_INSTALL_ROOT/bin/gitleaks-guarded"

# The guarded launcher must win PATH resolution for the name `gitleaks`.
ln -sfn "$ECO_INSTALL_ROOT/bin/gitleaks-guarded" "$ECO_INSTALL_ROOT/bin/gitleaks"

# Put that bin directory ahead of any directory holding the raw binary.
export PATH="$ECO_INSTALL_ROOT/bin:$PATH"
```

The `ln -sfn` above is safe **only because the link sits in the same directory as
`ecosystem-bounded-run`.** Bash sets `${BASH_SOURCE[0]}` to the path the script
was *invoked* with and does not resolve a symlinked file, so line 6's
`cd -- "$(dirname ...)" && pwd -P` canonicalises the directory the link lives in,
not the directory the real script lives in. A `gitleaks` symlink placed anywhere
else — `$HOME/.local/bin/gitleaks` pointing back at
`$ECO_INSTALL_ROOT/bin/gitleaks-guarded`, for example — makes the launcher look
for `ecosystem-bounded-run` beside *the link*, not find it, and refuse every scan
with **78**. Install the pair together and link only within that directory.
`tests/test_adoption_guarded_runners.py` exercises both cases.

Verify the install without starting a scan:

```bash
gitleaks version                      # execs the native binary directly
ecosystem-bounded-run true; echo $?   # 0 from inside a scope
ecosystem-bounded-run; echo $?        # 64, usage
```

The pinned native Gitleaks binary itself is installed by the host bootstrap, not
by these scripts. Point `GITLEAKS_NATIVE` at it if it lives outside
`$ECO_INSTALL_ROOT/tools/gitleaks-8.30.1/`.

Do not bypass the guarded launcher by calling the native binary directly, and do
not raise the limits to retry a scan that the scope killed: select a narrower
commit range or file set instead, and record any size-based exclusion as
incomplete coverage.

## Runtime boundary

`ecosystem-bounded-run` and `gitleaks-guarded` are **Linux-only**, and run only on a host that provides all of:

- **cgroup v2** — `ecosystem-bounded-run` requires
  `/sys/fs/cgroup/cgroup.controllers` to exist. Without it the memory and task
  limits cannot be enforced.
- **Optional: the cpu controller delegated to `user@.service`** (the systemd
  default from v252). Without it, jobs still run under the memory, task and
  runtime limits, with no CPU quota; see "CPU quota" above.
- **A native `systemd --user` bus** at `/run/user/$UID/bus` — it must be a real
  socket, not a symlink, and both it and `/run/user/$UID` must be owned by the
  calling user. On WSL2 this means systemd is enabled for the distribution
  (`systemd=true` under `[boot]` in `/etc/wsl.conf`) and a user manager is
  running.

When any of those preconditions fails the runner exits **78** and the command is
**not started**. There is deliberately no uncontained fallback: a refusal is the
designed outcome, because running the heavy job unbounded is the exact failure
being prevented. `gitleaks-guarded` refuses the same way (78) when the native
binary, the runner or the private runtime directory is unavailable — before any
scan begins.

**macOS has no cgroup equivalent.** launchd provides no per-job memory cgroup,
so `MemoryMax`/`MemorySwapMax` containment for a transient scope cannot be
reproduced there, and neither script above runs on macOS. For Gitleaks, a macOS
host uses `gitleaks-guarded-macos` instead (next section): a user-space
watchdog with the same caps, which is weaker than a kernel limit. Other heavy
jobs still have no macOS containment, and no macOS job has a CPU cap.

## macOS: `gitleaks-guarded-macos` (2026-09-24)

**Why.** At 09:45 and 09:46 EDT on 2026-09-24, Jetsam on a 24 GB MacBook Pro
recorded three concurrent Gitleaks 8.30.1 processes at a combined 52.8 GiB,
then 58.2 GiB, and killed 405, then 4,255 other processes. The two largest came
from the global pre-commit hook (`gitleaks git --pre-commit --staged --redact`)
on scratch commits made by `tests/test_catalog_freshness_propose.py`, before
#181 made the tests' Git configuration hermetic. `TrackedExplorerSubprocessTests`
force-adds the generated explorer. The mechanism is upstream redaction:
`filter()` calls `report.Finding.Redact` for every finding, and `Redact` copies
the finding's whole line. In Git mode a hunk holds whole lines, so the
explorer's 2,335 findings on one 12,889,851-byte line retain about 28 GiB. The
same happens to `gitleaks git --redact=100` over this repository's all-refs
history, where 240 commits touch that file. `dir` mode reads files in bounded
chunks and stayed at about 0.13 GiB, even for 714 MB with nested worktrees. The
measurements are in
[the receipt](../../evidence/receipts/gitleaks-macos-memory-bound-20260924.json).

**What it does.**

- It keeps Gitleaks' arguments, output and exit status. `version`, `--version`,
  `--help` and `-h` on their own exec the native binary with no lock or
  watchdog.
- One scan runs per user, across worktrees and clients. The front end holds an
  exclusive `flock` on `~/.local/state/ecosystem-gitleaks.lock`, and the scan
  inherits it. A second scan waits up to `ECOSYSTEM_GITLEAKS_LOCK_WAIT` seconds
  (default 60; `0` gives the Linux launcher's fail-fast behaviour) and then exits
  **75**. A read-only descriptor is enough to take the lock, so sandboxed
  clients can use it, but only an unsandboxed run can create the file.
- Every 50 ms it sums the physical footprint (the figure Jetsam acts on) of the
  scan's whole process tree, including its `git` child. Above **6 GiB** it
  SIGKILLs the tree and exits **137**. After **600 s** it sends SIGTERM, then
  SIGKILL 5 s later, and exits **124**. `ECOSYSTEM_JOB_MEMORY_MAX` and
  `ECOSYSTEM_JOB_SECONDS` can lower either cap, never raise it.
- It refuses with **78** before any scan in these cases: off macOS; the native
  binary is missing (default
  `${MISE_DATA_DIR:-~/.local/share/mise}/installs/gitleaks/8.30.1/gitleaks`, or
  `GITLEAKS_NATIVE`); that path is the front end itself; the lock is unusable or
  a symbolic link; a limit is malformed; or process footprints cannot be read.
  A scan whose footprint becomes unreadable while it runs is killed and exits
  with the same 78.
  A signal to the front end stops the tree and exits 128 plus the signal
  number.
- The scan stays in the caller's process group, so a group signal from the
  caller, such as Ctrl-C or a tool timeout, reaches it too.

**What it is not.** It is a user-space watchdog, not a kernel limit. The
measured overshoot was 0.04-0.20 GiB above the cap at the observed allocation
rates. If the front end itself is SIGKILLed, the scan continues unwatched but
keeps the lock, so no second scan can start. There is no CPU or task cap. A scan
stopped at the cap produced no result: that is fail-closed, not coverage.

**Rejected alternatives**, measured on the same host:

- `--max-target-megabytes` fails open. Gitleaks skips an oversized fragment at
  debug log level, so the staged explorer's 2,335 findings became `no leaks
  found` with exit 0.
- Path exclusions in `.gitleaks.toml`: a top-level path allowlist skips whole
  files in both modes (see that file's header), and `dir` memory was already
  bounded.
- `GOMEMLIMIT`: at 4 GiB the history scan still crossed the cap, because the
  growth is live findings, not garbage.
- A kernel memory limit: `memorystatus_control` refuses unprivileged callers
  with EPERM.

**Install (the host's owner).**

```bash
install -m 0755 adoption/tools/gitleaks-guarded-macos "$HOME/.local/bin/gitleaks-guarded-macos"
gitleaks-guarded-macos version                     # execs the native binary directly
: > "$HOME/.local/state/ecosystem-gitleaks.lock"  # once, outside any sandbox
```

Every caller must invoke the front end, not the native binary. That includes
the global pre-commit hook, which the agent-ecosystem repository installs; the
hook change is handed off to that repository's owner. Do not raise the caps to
retry a scan the front end killed. Narrow the scope instead, for example to the
CI history scope (`--log-opts=HEAD --max-target-megabytes 2`, measured at
2.9 GiB), and record any size-based skip as incomplete coverage.

## What the tests establish

`tests/test_gitleaks_guarded_macos.py` covers the macOS front end. Structural
checks run on every host, plus a refusal check off macOS. On macOS, integration
checks against stub binaries cover exit-status propagation, the memory cap on an
allocating grandchild, the runtime cap, the lock (busy, waiting, serialised,
held during the scan) and every refusal. The stubs are synthetic fixtures; the
Gitleaks measurements are in the receipt above. The rest of this section covers
the Linux scripts.

`tests/test_adoption_guarded_runners.py` covers two different evidence classes,
and prints which containment branch it took.

- **Structural validation** — ShellCheck (`-S style`, gated on `shutil.which`,
  with `SC2317` excluded — see the note at the end of this page)
  finds no other finding in either script; neither file contains a personal home path
  literal; `ecosystem-bounded-run` with no arguments exits 64. On strict mode,
  note the divergence: **the shipped scripts do not carry `set -Eeuo pipefail`.
  Both open with the literal line `set -euo pipefail`, and that literal is what
  the suite asserts**, because the files are copied byte-for-byte from their
  source and adding `-E` here would break the byte-fidelity guarantee recorded
  under Provenance. Neither script installs an `ERR` trap, which is the only
  reason the missing `-E` changes no behaviour, so the suite asserts the
  absence of an `ERR` trap as well and that exemption cannot go stale silently.
  An upstream sync that adopts `-E` must update the script and that assertion
  together. This class proves artifact consistency, not that containment works.
- **Local integration check** — on a host that has cgroup v2 and a working
  `systemd --user` bus, the suite asserts that `ecosystem-bounded-run sh -c
  'exit 3'` propagates exit 3 and that `ecosystem-bounded-run true` exits 0, and
  then proves containment *from inside the job*. A single job writes three
  oracle files: its own `/proc/self/cgroup`, the systemd properties of the unit
  that cgroup path names, and the limit files the kernel applied to that cgroup.
  The test then requires all of: the job's cgroup v2 leaf is an
  `ecosystem-job-<uid>-<pid>-<random>.scope`, the launcher's own unit name;
  `systemctl --user show` reports that unit as `running` with `TasksCurrent` at
  least 1 and `MemoryMax=6442450944` *while the job is still inside it*, which
  is only true if `systemd-run` really created the unit; and the cgroup's own
  `memory.max` is `6442450944` with `pids.max` `256`, i.e. the kernel, not only
  systemd, applied the documented defaults. Any ambient `ECOSYSTEM_JOB_*`
  override is stripped from the job's environment first, so the defaults are
  what is measured. Separately, and before the command can run, the runner
  itself re-reads `memory.max`/`pids.max` inside the scope (see the divergence
  above). `BoundedRunSetupRefusalTests` drives instrumented copies whose only
  change is the `systemd-run` path. A stand-in that fails like a stale bus, one
  that runs the command with no scope, and one that creates a real scope
  without the four resource properties must each exit 78 without running the
  command. Workload statuses 1, 78 and 127 must pass through unchanged, and a
  missing command must exit 78. Non-default, page-unaligned limits
  (`1000001K`, 64 tasks) must still run and show the page-rounded value.
  `BoundedRunCpuQuotaTests` checks the CPU quota. The default and an explicit
  `50%` must reach the job's own `cpu.max`; this needs cpu delegation and is
  skipped without it. Stand-in launchers that drop `CPUQuota` or change it to
  `37%` must each exit 78 without running the command. The dropped variant
  runs in a fresh slice, so it always reaches the missing-`cpu.max` refusal,
  and the altered one reaches the mismatch refusal. An unreadable controllers
  file must also be refused with 78. A controllers file
  without `cpu` must skip the default with the note and refuse an explicit
  quota with 78, and a `cpuset`-only list counts as no delegation. Instrumented
  CPU counts of 1, 2 and 3 must give the one-CPU floor (`100000 100000`) and 4
  must give `200000 100000`. A manager query that stalls must be refused with
  78 within the 5 s timeout. `0%`, `max`, `150`, `1000000%` and `-5%` must be
  refused with 78. Checked by mutation on 2026-09-24, with each of these runner edits
  failing at least one of these tests:
  - removing the in-scope `cpu.max` check;
  - tolerating a missing `cpu.max`;
  - not refusing an explicit quota without delegation;
  - dropping the `CPUQuota` property;
  - changing the default to CPUs − 1;
  - opening the quota regex;
  - treating an unreadable controllers file as "no cpu";
  - matching `cpuset` as `cpu`;
  - lowering the small-host floor to `CPUs > 1`;
  - removing the 5 s timeout on the manager query.
  GitHub-hosted runners have no `systemd --user` manager, so there the
  containment and CPU-quota tests take their skip or refusal branches. The
  executed evidence for them comes from a host with a user manager.
  `LiveTaskQueryTests` stubs `systemctl` and requires that a failed query, or a
  missing count for a cgroup that still exists, is an error and never "no
  tasks". Checked by mutation on 2026-09-22: a stand-in runner that
  `exec`s the command directly fails with `the job did not run inside an
  ecosystem-job-*.scope; its own cgroup was '0::/init.scope'`, and a runner
  patched to `MemoryMax=8G` fails with `'8589934592' != '6442450944'` — so a
  silently uncontained or unbounded run cannot pass this test.
  Afterwards the test polls for the release of **only that one unit name**, so a
  concurrent guarded scan by the same user elsewhere can neither fail nor mask
  it. `--collect` cleanup is asynchronous and its latency is not bounded: on the
  developing WSL2 host the unit usually left the listing in 0.02s-0.06s, but one
  scope unit was still listed more than 30s after the runner returned. That
  lingering unit reported `TasksCurrent=0` and an already-removed control
  group, i.e. an empty unit waiting for systemd's garbage collector, not an
  escaped job. So the test polls to a 45s deadline, prints the observed release
  time, and if its unit is still listed it fails only when that unit still
  holds tasks. That count must come from a successful `systemctl --user show`
  reporting a number, or else from the job's own cgroup directory having
  disappeared. A failed query fails the test. A listing taken right after the runner exits can legitimately
  still show the scope, so `systemctl --user list-units 'ecosystem-job-*'`
  returning a line is not by itself a containment failure — check
  `TasksCurrent`. The suite also
  drives `gitleaks-guarded version` at a stub binary via `GITLEAKS_NATIVE`,
  through an instrumented copy of the runner, and asserts the stub's oracle file
  exists while the runner's oracle file does not — i.e. the fast `version` path
  really does `exec` the native binary and never pays for a scope.
- **Local integration check** — the install boundary above: a `gitleaks` symlink
  created *beside* `ecosystem-bounded-run` reaches the native binary, and the
  same symlink created in another directory refuses with 78 without entering a
  scan path. This measures the documented rule rather than restating it.
- On a host **without** the user bus, the same test asserts the refusal property
  instead: exit 78 and the oracle file the wrapped command would have created
  does not exist — the "never runs a command uncontained" guarantee. The
  branch probe (`systemd-run --user --scope true`) is itself run under a
  timeout inside `try`/`except`, so a host where the probe cannot even execute
  takes the refusal branch rather than erroring at import time.

The integration branch is evidence for the host that ran it. It is not upstream
Gitleaks evidence, and it says nothing about a host with a different systemd or
cgroup configuration.

The per-user lock is **not** covered by the suite, because a test that takes
`/run/user/$UID/ecosystem-gitleaks.lock` would contend with a real scan on the
same host. It was checked once by hand instead, on 2026-09-22 (bash 5.2.21): with
a sleeping stand-in for the native binary, a second `gitleaks-guarded dir .`
launched while the first was still scanning exited **75** with `another scan
holds the per-user lock`, and the first then exited 0. The lock file descriptor
opened at line 22 (line 21 before the 2026-09-24 re-sync) survives the final `exec` on this bash (verified separately via
`/proc/self/fd`), which is what makes that guarantee hold. This is a one-host
observation, not a suite assertion.

The shellcheck structural test excludes `SC2317` (info: "command appears to be unreachable"): the bounded runner's cleanup function is only reached through `trap`, which the shellcheck release on the current GitHub-hosted image (its version is not captured in the run log) reports as unreachable while 0.11.0 is clean; the scripts are kept faithful to their recorded provenance (only the divergences listed above) rather than annotated for that finding.

## `ecosystem-switch`

**Why.** Before this tool, every consumer of an adopted component -- `bin/*`
symlinks, a systemd unit's `Environment=PATH=...`, a wrapper script, an MCP
server config -- pointed straight at that component's versioned install
(`tools/<name>-<version>`), and "rolling forward" meant hand-editing each of
those consumers, with `ln -sfn` (a remove-then-create window, never atomic)
for the symlink ones. `ecosystem-switch` introduces one indirection,
`current/<id>`, so every consumer is edited exactly once (by `adopt --relink`,
described below) and every later version change is one atomic flip of that
one link, with a receipt/window/memory/drift gate in front of it, a
hash-chained record behind it, and an automatic reverse-order rollback if the
post-apply verify fails.

**Install.** Same pattern as the guarded runners above: copy the file to
`$ECO_INSTALL_ROOT/bin/ecosystem-switch` and make sure that directory is on
`PATH`. It is Python 3 standard library only (no pip install, no virtualenv).

```bash
install -m 0755 adoption/tools/ecosystem-switch "$ECO_INSTALL_ROOT/bin/ecosystem-switch"
```

**Component spec.** `ecosystem-switch` manages exactly the components named in
`$ECO_INSTALL_ROOT/switch/components.json` (or an explicit `--spec PATH`,
including a full `adoption/pins-linux-x86_64.json`-shaped `{"tools": [...]}`
file, from which it reads each tool's `id`, `version`, `root_name`,
`current_link`, `entrypoints[]`, `surfaces[]`, `state_dirs[]`, `window` and
`rollback_class` -- see `adoption/pins-schema-v2.json` for the exact shape of
each field). A component with `root_name`/`current_link` both `null` (a
self-updating `native`-kind pin such as `claude-code`, or a `uv-tool`-kind
pin whose environment `uv` itself owns) has no switch-managed root at all;
`adopt --relink` skips it and `adoption/pins-linux-x86_64.json`'s
`divergence[]` array is where that is declared, not this tool.

**One-time migration: `adopt --relink [--component ID ...] [--spec PATH]`.**
For each managed component, creates `current/<id>` pointing at whatever real
root is already active (a no-op in terms of real, resolved paths: `readlink
-f` on every entrypoint before and after this command must be identical --
enforced, not just documented, by an in-process check that aborts the whole
relink if it is not), then repoints every `entrypoints[]` symlink and every
`surfaces[]` `text-replace`/`file-write` surface (a systemd unit, wrapper
script or MCP config text) from the real root to `current/<id>/...`. A
`text-replace` surface under a path containing `/frozen/` is refused outright
before anything is written; every other one backs up the original bytes
under `switch/backups/<txn>/` first and refuses unless its declared `old`
substring occurs exactly `expected_count` times. Idempotent: re-running it
once relinked leaves everything unchanged. `adopt --baseline [--spec PATH]`
is the read-only counterpart: it snapshots the current, already-relinked
state (or records that a component is not relinked yet) without changing
anything, for `status`/`verify` to compare against later. `adopt --resync ID
--reason TEXT` accepts a live value some out-of-band change (an operator's
manual `ln -sfn`, the pre-switch workflow) produced, recording the reason in
the ledger, so `apply`'s drift check does not keep refusing it.

**Everyday version change: `plan` then `apply`.** `plan ID --to-root PATH
--receipt RID` prints the exact ordered operations `apply` would run and
their `plan_sha256`; `apply ID --to-root PATH --receipt RID --window NAME
--plan-sha256 SHA [--confirm-within SEC]` re-computes that same plan and
refuses if its hash no longer matches (something changed between review and
execution), then, only once every gate below passes, executes it and appends
one hash-chained ledger entry per operation:

- **Receipt gate.** `--receipt RID` names a
  `switch/receipts/<RID>.json` document shaped like
  `tools/sota-convergence/native-rollout-receipt.schema.json`. `apply` refuses
  unless that receipt's overall `status` is `"passed"`, its `identity`
  matches the component and the *full* target version derived from
  `--to-root`'s basename after stripping the `<component>-` prefix (so
  `tools/rtk-0.50.0-r20260925` is version `0.50.0-r20260925`, not just the
  text after the last hyphen -- a receipt for one root never authorizes a
  different root that happens to share a trailing segment), its
  `install.root` (its `${STACK_HOME}` placeholder resolved against
  `ECO_INSTALL_ROOT`) names that same `--to-root`, tiers `T0`, `T2` and `T4`
  are all `"passed"`, and tier `T1` is either `"passed"` or explicitly
  `"unavailable"` with a stated reason. (`install.marker_sha256` is not
  cross-checked: no generic, per-component marker-file location is defined
  yet for this tool to locate on its own.)
- **Window gate.** `--window NAME` names `switch/windows/<name>.json`
  (`{name, start_utc, end_utc, allowed_components}`); `apply` refuses outside
  that time range or when the component is not in `allowed_components`.
- **Memory gate.** A plan step that restarts a unit (a `surfaces[]` entry of
  kind `unit-restart`) refuses when `/proc/meminfo`'s `MemAvailable` is below
  a floor (default 6 GiB, `ECOSYSTEM_SWITCH_MIN_MEMORY_KIB` only ever lowers
  it -- any higher value is clamped back down to the default, never trusted
  outright -- for tests) -- the same rule this rollout's own workers apply to
  themselves before a heavy job (`docs/linux-efficiency.md`), applied here to
  a restart that may load a model. A test that needs the gate to
  deterministically refuse regardless of this host's real `MemAvailable` uses
  the separate, unbounded `ECOSYSTEM_SWITCH_TEST_FORCE_MIN_MEMORY_KIB`
  instead, so the production-facing variable's one-directional guarantee is
  never itself weakened for a test's convenience.
- **Drift gate.** If `current/<id>`'s live target no longer matches what the
  ledger last recorded, `apply` refuses and names `adopt --resync` as the
  fix, rather than silently overwriting an out-of-band change.
- **Denylist.** A `unit-restart` step never restarts
  `adaptive-paper-rung1x-20260923-ladder2`, `ibkr-paper-post-20260923`,
  `incentive-forward@1330`, `mover-daily-scan-0925` or
  `mover-rth-trial-20260924`, whether or not a receipt or window would
  otherwise allow it.

After the operations run, `apply` runs the same check `verify` below runs for
that one component; a failure there triggers an immediate, in-process,
reverse-order rollback of everything the transaction just did, and the
command exits non-zero. On success, with no `--confirm-within`, the
transaction is immediately `applied`. With `--confirm-within SEC`, it asks
`systemd-run --user --on-active=<SEC>s -- ecosystem-switch rollback --txn T
--if-unconfirmed` to call back later (real usage: this always fires well
after `apply` itself has returned and released its lock) and the
transaction's own status is `pending_confirmation` until `confirm --txn T` is
run or that timer fires. `ECOSYSTEM_SWITCH_SYSTEMD_RUN` /
`ECOSYSTEM_SWITCH_SYSTEMCTL` point tests at stub executables instead of the
real commands.

**Everything else.** `status [--json] [--component ID]` prints each managed
component's current root and every recorded transaction; `confirm --txn TXN`
marks a pending transaction confirmed and best-effort stops its revert timer
(refuses a txn that was already rolled back, or whose post-apply verify
already failed); `rollback ID | --txn TXN [--if-unconfirmed]` undoes a
transaction's operations in reverse order -- a service's `unit-restart` is
always reversed only after its own `link` (never restarted while
`current/<id>` still points at the new root), and its health probe compares
against that `link`'s own recorded old root, not the pre-restart MainPID
string the ledger's `unit-restart` entry itself carries -- (`--if-unconfirmed`
is a no-op once the transaction was already confirmed or already rolled back
-- exactly what the scheduled timer above calls; every rollback also refuses
a txn a later apply on the same component has since superseded, and one with
no reversible operation at all, e.g. a bare baseline/resync/prune record);
`verify [--component ID] --json` re-checks live state against the ledger and
the ledger's own hash chain, independent of any apply; `recover` rolls back
any transaction still `in_progress` (a crash
mid-`apply` or mid-`relink`) rather than ever completing one after the fact;
`prune --list` reports `tools/<name>-<version>` roots no `current/<id>` link
points at, that are not the previous root of any not-yet-rolled-back txn (a
pending or already-applied txn's own rollback target stays live until that
txn is actually rolled back), and that this tool's own (reduced-scope: `PATH`
entries, `bin/` symlink targets, this user's own running processes'
exe/cwd/cmdline and this user's `systemd --user` unit file text -- no mount/
symlink-hop/citation scan, and no check of hard-coded roots inside wrapper
scripts under `adoption/tools/` since this tool only ever reads
`$ECO_INSTALL_ROOT`, never the catalog checkout -- `bin/ecosystem-wave-retention`
on the host has the fuller technique this should grow into) in-use check
does not find referenced; `prune --apply ROOT --reason TEXT` removes one such
eligible root and records the reason; `write-installed-versions` regenerates
an `installed-versions.txt`-style report from the switch state, independent
of running a fresh bootstrap, backing up any file it is about to overwrite
under `switch/backups/` first.

**Safety.** A global `flock` on `switch/switch.lock` (busy -> exit 75, the
same convention as `gitleaks-guarded` above) and, in the same call, the
bootstrap lock `bootstrap-linux.sh` itself takes, so a switch operation and a
bootstrap run can never interleave. The ledger
(`switch/ledger.jsonl`, 0600, append-only, one JSON object per line: `seq,
txn, op, component, surface, from, to, pre_sha256, post_sha256, backup,
receipt, window, rollback_class, actor, at_utc, prev_hash, hash`) is hash-
chained (`hash = sha256(prev_hash + canonical_json(entry))`); `verify` and
`recover` both re-derive that chain and report a break rather than trust a
cached summary. `switch/state.json` is always recomputed from the ledger,
never hand-edited.

**What the tests establish (`tests/test_adoption_switch.py`).** A synthetic
temporary `ECO_INSTALL_ROOT` throughout, with `ECOSYSTEM_SWITCH_SYSTEMCTL` /
`ECOSYSTEM_SWITCH_SYSTEMD_RUN` stubs for the unit-restart and confirm-or-
revert tests (one stub health-probes a real, separately copied Python
interpreter running under the new root, because `/proc/<pid>/exe` reports the
exec'd file's own real path, not a symlink's target). Covered: relink
preserves every real, resolved path and is idempotent; a `text-replace`
surface is rewritten and backed up, a frozen one is refused untouched, and a
partial relink failure is left `in_progress` for `recover` to roll back;
apply's receipt/window/memory/drift/denylist gates each refuse under a
`.stderr` naming the reason and leave the live entrypoint unchanged; a failed
verify triggers the automatic rollback; `rollback` (no `--txn`) selects the
most recently touched transaction by ledger sequence, not by sorting
transaction-id text (an earlier draft of this tool picked the wrong one this
way, confirmed by a failing test before the fix); a tampered ledger line is
detected by `verify`; a held `switch/switch.lock` makes a second operation
exit exactly 75; and `prune --list`/`--apply` distinguish a referenced root
from an eligible one. The lower-level `text-replace`/`file-write`/
`native-cli`/`data-backup`/`data-restore` operation functions are additionally
exercised directly (`OperationUnitTests`), because none of this track's
shipped `adoption/pins-linux-x86_64.json` entries has a populated
`surfaces[]` of those kinds to drive them through the CLI end to end yet --
every one of the 14 migrated pins is a bare CLI tool with no known external
hard-coded-root consumer today. `switch.md`'s Facts section names the actual
hard-coded roots a later qualify wave should give real `surfaces[]` entries
(`vllm`, `gitleaks`, `mcp-inspector`, `serena-context`, `dagu`,
`adaptive-paper-runtime`; see `adoption/pins-linux-x86_64.json`'s
`candidates[]`), which is also why the denylisted-unit names above are
enforced unconditionally rather than only for a component that happens to
declare them.
