# Portable guarded runners

Two host-local launchers that keep a heavy maintenance job, and every process it
spawns, inside its own native systemd scope with hard memory, task and runtime
limits. They exist because an unbounded scan or build on a WSL2 host can exhaust
the VM and take the whole session down; the scope kills the job instead.

| Script | Role |
| --- | --- |
| `ecosystem-bounded-run` | Generic launcher: runs `COMMAND [ARG ...]` in a transient `--user --scope` unit with `MemoryHigh`/`MemoryMax`/`MemorySwapMax`/`TasksMax`/`RuntimeMaxSec` applied. Refuses to run at all when it cannot contain the job. |
| `gitleaks-guarded` | Gitleaks front end: preserves upstream Gitleaks argument and exit-code semantics, adds a per-user non-blocking lock so two scans cannot run at once, and delegates the actual scan to `ecosystem-bounded-run`. |

## Provenance

- Source: the `bin` directory of the private `codex-ecosystem` checkout on the
  WSL2 host that developed them (not published here; the two files below are the
  whole of what was copied).
- Copied: 2026-09-22.
- Original sha256 as read with `sha256sum` at copy time:
  - `ecosystem-bounded-run` —
    `7680fe1173b35a8472023772c8973c4a9b65c4e444414ac44efa199cbabe17db`
  - `gitleaks-guarded` —
    `66db06f653520ad49c2531ab2d5df762d1e952b1d1655ba5f509b6014cbc52f1`
- `ecosystem-bounded-run` is byte-for-byte identical to its source; its copy here
  still hashes to the value above.
- `gitleaks-guarded` differs from its source on two lines only (see below), so
  the copy in this repository hashes to
  `61e87881841a346fc0c4d2ec514b283696311ce033fd7b27397973fc2429a655`. Compare
  against *that* value when checking this repository's file, and against the
  `66db06f6…` value when checking a copy taken straight from the source host.

### Exact lines changed in `gitleaks-guarded`

Only lines 5 and 6 differ from the source. Both originally held a literal
personal home path, which this repository forbids and which would not resolve on
another host.

| Line | Was | Is now | Why |
| --- | --- | --- | --- |
| 5 | a literal absolute path to the pinned Gitleaks binary under one user's home | `gitleaks_native="${GITLEAKS_NATIVE:-${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/tools/gitleaks-8.30.1/gitleaks}"` | Resolves through the same `ECO_INSTALL_ROOT` contract the bootstrap scripts use, with `GITLEAKS_NATIVE` as an explicit override. The pinned version string `gitleaks-8.30.1` is unchanged. |
| 6 | a literal absolute path to `ecosystem-bounded-run` in one user's checkout | `gitleaks_runner="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/ecosystem-bounded-run"` | The guarded launcher finds its runner next to the path it was invoked with, so the pair stays correct wherever it is installed as long as the two files are installed together. `${BASH_SOURCE[0]}` is not symlink-resolved; see the install section. |

Nothing else was touched. Every absolute `/usr/bin` tool path
(`/usr/bin/systemd-run`, `/usr/bin/systemctl`, `/usr/bin/timeout`,
`/usr/bin/flock`), every exit code (`64` usage, `75` lock held by another scan,
`78` refusal to run uncontained) and every default limit (`MemoryHigh=4G`,
`MemoryMax=6G`, `MemorySwapMax=0`, `RuntimeMaxSec=600`, `TasksMax=256`) is
unchanged.

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

These scripts are **Linux-only**, and only on a host that provides all of:

- **cgroup v2** — `ecosystem-bounded-run` requires
  `/sys/fs/cgroup/cgroup.controllers` to exist. Without it the memory and task
  limits cannot be enforced.
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

**macOS has no equivalent.** launchd provides no per-job memory cgroup, so there
is no way to reproduce `MemoryMax`/`MemorySwapMax` containment for a transient
scope. The "always run Gitleaks through the guarded launcher" rule is therefore
scoped to Linux/WSL2 hosts; a macOS bootstrap must not pretend to satisfy it by
installing an unbounded shim.

## What the tests establish

`tests/test_adoption_guarded_runners.py` covers two different evidence classes,
and prints which containment branch it took.

- **Structural validation** — ShellCheck (`-S style`, gated on `shutil.which`)
  finds no finding in either script; neither file contains a personal home path
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
  what is measured. Checked by mutation on 2026-09-22: a stand-in runner that
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
  holds tasks. A listing taken right after the runner exits can legitimately
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
opened at line 21 survives the final `exec` on this bash (verified separately via
`/proc/self/fd`), which is what makes that guarantee hold. This is a one-host
observation, not a suite assertion.

The shellcheck structural test excludes `SC2317` (info: "command appears to be unreachable"): the bounded runner's cleanup function is only reached through `trap`, which shellcheck 0.9.x on GitHub-hosted runners reports as unreachable while 0.11.0 is clean; the scripts are kept byte-faithful to their recorded provenance rather than annotated.
