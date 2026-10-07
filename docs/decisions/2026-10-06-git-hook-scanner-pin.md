# Keep the Git hook's Gitleaks pin and install it through mise aqua

Date: 2026-10-06. Lane: foundation. Status: accepted subject to the command
center's exact-head read and co-op host acceptance.

The approved Phase 1 Git task pins Gitleaks 8.30.1 and activates the existing
repository hooks on NativeStack2604. Its north-star action is to make the local
secret gate work before future changes enter the foundation/trading landing queue.

Use the maintained mise aqua backend with
`aqua:gitleaks/gitleaks@8.30.1`, preserving the existing pre-commit hook,
repository `.gitleaks.toml`, guarded launcher and bounded runner. The standalone
native acceptance configuration and the scanner prerequisite for the central plan are in
`evidence/artifacts/p1-git-hook-20261006/`. The central installer has a separate
writer; the supplied prerequisite does not change that installer's dispatch.
The command center's A21 assigns that integration to the P1-CLI lane.

Betterleaks 1.9.0 was the alternative allowed only if its default rules and exit
semantics were equivalent. Both scanners default findings to exit 1, but the
repository extends their embedded defaults: Gitleaks has 222 rules and
Betterleaks has 463. Their config bytes differ. This rejects the required
same-rule-set equivalence; it does not establish a coverage ordering or decide
the separately preregistered Betterleaks CI/hook migration.

The release API reports Gitleaks v8.30.1 published on 2026-03-21. This is the
task's explicit compatibility pin, not a claim that the release meets the
standing 180-day currency criterion: that release line lapsed on 2026-09-17.
The central plan's 2026-10-20 deadline is the separate 90-day commit-recency
line, based on master commit `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b`
at 2026-07-22T16:50:33Z. The original record wrongly compared that commit
deadline with the release timestamp; native release and commit GETs corrected
the claim on 2026-10-06. Both gates come from
`native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:docs/decisions/2026-10-04-repository-quality-rule.md:19`.

The host recipe copies the checksum-verified native binary into the guard's
owned target instead of linking into mise's install. Mise's documented prune
operation can remove command-line-only versions. The recipe verifies the
copied SHA and guarded PATH before enabling hooks for all linked worktrees.
Git maps every nonzero pre-commit result to a failed commit; the positive
native findings line, unchanged HEAD and redaction check identify detection.

Native installation in isolated mise directories and a guarded scratch-clone
check passed: a clean commit succeeded, one generated inert AWS-shaped value
was blocked with exit 1, HEAD stayed unchanged and output omitted the generated
value. This is local integration with a synthetic fixture. It is separate from
unchanged upstream tests, hosted CI and application of host settings.

An initial broader guard test run failed on native systemctl property parsing.
The test now retains names and checks the exact returned properties instead of
assuming D-Bus output order. It still checks the native scope, tasks, memory
and kernel limits. Forty hook/config cases then passed without skips and
33 guard cases passed with one existing skip. The initial failure remains
separate from those results. The initial local
clone completed without the required nice 19 prefix; subsequent scanner
installation, hook commits and test runs used nice 19. Host application remains
the co-op's work after the PR's checks pass.

Overturn this pin when the user approves a newer compatibility pin, or when the
preregistered Betterleaks comparison establishes the required history/corpus
acceptance and authorizes the shared hook migration. Complete that qualification
before the 2026-10-20 commit-recency deadline; reaching it without current
evidence overturns the maintained-status claim. A scanner refusal,
containment failure or lock contention is unfinished acceptance, not proof that
a secret was detected. Manual replay and broad secret coverage are outside the
small synthetic check.

Sources:

- [Gitleaks v8.30.1 release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), source `83d9cd684c87d95d656c1458ef04895a7f1cbd8e`; `config/config.go:19-20`, `config/gitleaks.toml`, `cmd/root.go:76`.
- [Betterleaks v1.9.0](https://github.com/betterleaks/betterleaks/releases/tag/v1.9.0), source `81aff7a638638aae3a659845d089043e1d8fe9ac`; `config/config.go:22-23`, `config/betterleaks.toml`, `cmd/root.go:82`.
- [mise registry backend](https://github.com/jdx/mise/blob/050ce5a20287a0aafd872b1191699a5fdafff5ac/registry/gitleaks.toml#L1) and [isolated directories](https://github.com/jdx/mise/blob/050ce5a20287a0aafd872b1191699a5fdafff5ac/docs/directories.md#L13), mise 2026.10.1.
- [mise prune](https://github.com/jdx/mise/blob/050ce5a20287a0aafd872b1191699a5fdafff5ac/docs/cli/prune.md#L14) and [Gitleaks latest master commit](https://github.com/gitleaks/gitleaks/commit/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b), native GETs verified 2026-10-06.
- [Native Git pre-commit contract](https://git-scm.com/docs/githooks#_pre_commit), read 2026-10-06: nonzero aborts the commit.
- [systemd v259.5 property iteration/filter](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/shared/bus-print-properties.c#L354) and [named output](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/shared/bus-print-properties.c#L36) explain the measurement correction.
- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:scripts/git-hooks/pre-commit:7`, `.gitleaks.toml:144`, `adoption/tools/gitleaks-guarded:5`, `adoption/tools/ecosystem-bounded-run:133`, `tests/test_pre_commit_gate.py:58`, `docs/secret-storage.md:353`.
