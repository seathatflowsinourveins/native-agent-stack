# Phase 1 transfer-only CLI slots — 2026-10-06

North-star action: move reproducible command/repository prerequisites to
NativeStack2604 for research and historical simulation, without revising
foundation default decisions.

The approved full-resolution plan, SHA256
775119dc6840552def19142a10e2730b489b6365c346e6f9fb6f5db5f2572ba2,
Phase1 step6 assigns each actual missing CLI a pinned install-plan slot or dated
not-needed row. Co-op A8 chooses a narrow transfer collection and makes P1-CLI the
central install-plan writer, including the P1-GIT Gitleaks8.30.1 prerequisite.

The maintained plan at ecfa11276 deliberately binds its owners to foundation
catalog rows (check_plan.py:382–418); the client-config tests also bind the63
installed owners. Appending migration utilities as foundation defaults would
change that accepted scope. The adopted transfer_clis collection leaves owners,
owners.json, the default mise.toml and ordinary installation selections unchanged,
while the same checker covers pins, sources, commands, native acceptance,
named-only dispatch and dated exclusions.

Native installation remains mise, uv tool install or explicit versioned apt-get.
The existing run_command/check/--only interfaces are extended, not replaced by a
new installation or E2E runner. A separate transfer-mise.toml records only transfer
pins. A native manager must already be available from the base runtime.

Alternatives:

- Add foundation default slots: rejected because Phase1 transfers an environment,
  not a new catalog/gate decision.
- Adopt mise task/config overlays: supported upstream, but overlays retain the
  base config, add another command representation and cannot replace this plan's
  source/coverage rules. Post-dependencies are unsuitable for acceptance because
  they run after failure. Plain safe TOML is not inherently a trust-prompt case.
- Copy legacy executables or custom wrappers: rejected without maintained pinned
  upstream installation and a native check.

Sources: plan files at ecfa112764c664d35377dd66b8cfcb67e5a94d60;
[jdx/mise v2026.10.1](https://github.com/jdx/mise/tree/v2026.10.1/docs);
[astral-sh/uv0.12.22 tools](https://github.com/astral-sh/uv/blob/0.12.22/docs/concepts/tools.md);
[Gitleaks v8.30.1 README](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md).
The repository/vault runbook cites Git2.53.0, util-linux2.41.3, systemd259.5 and
the canonical Librarium source at7c6215eb.

Overturn this scope if the foundation owner deliberately adopts one of these CLIs
as a catalog default, or a maintained native profile supplies the same pin/source/
exclusion/coverage guarantees with a smaller surface. Any such change needs its
own evidence rather than relabeling transfer rows.

Local contract checks are separate from future host/native self-tests. No host
installation, configuration, privileged mount or new foundation acceptance is
performed by this repository change.

