---
name: verify
description: Pre-commit acceptance for this repository. Use right before committing code, evidence or manifests. Run the repository validator, scoped convergence checks for new claims and existing tests for touched paths at nice -n 19, then report commands and exit codes. Repository policy requires evidence and manifest validation even when native docs-only or tests-only guidance might skip this skill.
---

# Verify before committing

Read-only acceptance for a change about to be committed. Since 2.1.286, Claude
Code tells Claude to run a project skill named `verify` right before committing,
except for docs-only and tests-only commits. That is model guidance, not an
enforcement hook. Regardless of the native commit classification,
`AGENTS.md:21` requires `scripts/validate.py` before committing changed evidence or manifests, even when
the rest of the commit is docs or tests.

Work from the root of the worktree that holds the change
(`git rev-parse --show-toplevel`). Run the checks one at a time at `nice -n 19`
so they yield to other work on the host.

## Checks

1. Repository validator for the covered change. `AGENTS.md:21` requires it
   for evidence and manifests; this skill also runs it for code changes:

   ```sh
   nice -n 19 python3 -B scripts/validate.py
   ```

2. Convergence record, when the change adds a new convergence claim
   (`AGENTS.md:22`). `scripts/validate_convergence.py --help` takes records as
   positional canonical paths relative to the repository root; it has no
   `--record` or `--experiment` flag. Pass the scoped experiment record the
   change carries:

   ```sh
   nice -n 19 python3 -B scripts/validate_convergence.py <scoped-record-path>
   ```

   The check is offline consistency of what the record declares, not proof
   that it is true. Check only the record this change carries; unrelated
   records and `--all-recorded` are outside this check.

3. Unit tests for the touched paths: the existing modules or classes under
   `tests/` that load the changed code or receipts. `docs/lanes.md:40-67` says
   which test modules belong to which lane. Name each one after confirming it
   exists:

   ```sh
   nice -n 19 python3 -B -m unittest <test-module-or-class> [...]
   ```

   When no existing test covers a touched path, report the gap instead of
   running the whole suite or naming a test that does not exist.

## Boundaries

Observe and report. Leave the repository, client and host as you found them:
no install, fetch, fix, format, staging, commit or evidence-hash update. Return
a missing prerequisite or failing check, with its output, to the writer of the
change; the writer fixes it and runs `verify` again.

These are source, integration and fixture checks of this checkout. Report them
as such, distinct from unchanged upstream tests and from live model or provider
acceptance (`docs/acceptance-evidence-policy.md`).

This file is a Claude Code project skill. Codex writers keep running
`scripts/validate.py` under their own explicit acceptance commands.

## Report

Give one line per command run: the exact command, its exit code and, for a
non-zero exit, the failing check or test names with the first error lines.
Then list each check not run and why.

```text
verify at <short HEAD> in <worktree root>
nice -n 19 python3 -B scripts/validate.py -> exit 0
nice -n 19 python3 -B -m unittest <module> -> exit 1: FAIL <test id>: <first error line>
not run: validate_convergence.py (no new convergence claim)
```

## Sources

- Native commit guidance, section 2.1.286:
  [anthropics/claude-code@v2.1.292 CHANGELOG.md L567](https://github.com/anthropics/claude-code/blob/v2.1.292/CHANGELOG.md?plain=1#L567).
- Authored with
  [anthropics/skills@8a1541c4 skills/skill-creator/SKILL.md](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md);
  installed copy sha256
  `dcd4803e61e913e6fc27294184cd3a71f09f5e924ff20c8a9a20173e7b3c2bcf`.
- Repository rules at base `67c6b6f94b456a3a7b5d28bb1fa34625a808d316`: `AGENTS.md:21`, `AGENTS.md:22` and
  `docs/lanes.md:40-67`; record syntax from
  `scripts/validate_convergence.py --help`.
