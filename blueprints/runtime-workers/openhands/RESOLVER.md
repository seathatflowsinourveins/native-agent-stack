# OpenHands PR resolver: deterministic host driver

The resolver turns one owner-authored issue into a draft pull request. A contained
OpenHands agent writes a patch; this driver does everything that touches GitHub.
The design is the resolver plan of 2026-09-28: section 2 (the loop) and section 3
(the gh harness). Upstream references and their pins:

- EXT: OpenHands/extensions@bea7a20, `skills/github-issue-to-pr/scripts/main.py`
  and `skills/github-pr-reviewer/scripts/worker.py`.
- gh: cli/cli@0cf10924 (v2.101.0).
- SDK: OpenHands/software-agent-sdk@fcc102a.
- V0: OpenHands/OpenHands@7bc33009, the retired resolver.

Each function's docstring names the upstream step it follows, or says that it is a
local composition of cited mechanisms.

## Stages

- **Stage 1 (these files):** the driver's core and a CLI that exercises it against
  fakes. Nothing here makes a model call, starts a container, contacts OmniRoute,
  pushes, or writes to GitHub.
- **Stage 2:** wire the core into `host.py` and `dispatch.py`, then make the live
  run. `resolver.py run` raises `NotImplementedError` until then.

## Files

| Path | Role |
| --- | --- |
| `resolver.py` | Issue selection, the delimited instruction, branch naming, SOTA sources, PR body, review loop and CLI |
| `resolver/patch_policy.py` | Fail-closed patch parser and validator; derives the host-executed set at the base commit |
| `resolver/gh_harness.py` | Allowlisted gh and git operations, the child environment, preflight and push |
| `resolver/outgoing_guard.py` | Checks every text before it reaches GitHub; approves body files by hash |
| `skills/resolver/SKILL.md` | The agent-side skill that states the same bounds |
| `tests/test_runtime_worker_openhands_resolver.py` | Our integration checks and fixtures |

`resolver/` has no `__init__.py`. `resolver.py` loads each module by file path under
a unique name, so `import resolver` still finds the driver.

## Checks

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_runtime_worker_openhands_resolver -v
python3 blueprints/runtime-workers/openhands/resolver.py --help
```

The tests create their private directories under `TMPDIR`. They are local
integration checks with synthetic fixtures, local git and fake gh, git and gitleaks
executables. One test runs the installed gitleaks when it is on
`PATH`. None of this is upstream acceptance (`docs/acceptance-evidence-policy.md`),
and none of it is a live GitHub or model run.

## Patch validator

The validator refuses symlinks, gitlinks, other modes, binary hunks, `.git*` and
`.github/` paths, dot-paths unless owned exactly, instruction files (`AGENTS.md`,
`AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`), new top-level entries,
unowned paths, renames or deletes with an unowned end, and case, Unicode and
filesystem aliases. An empty or refused patch means no GitHub write.

The host-executed set is derived at the base commit, not listed by hand:

- inputs: every string in `.claude/settings.json` except `permissions` and `$schema`,
  and the hook scripts in `scripts/git-hooks/` without their comment lines;
- words that name tracked files become protected files, and a named code file
  protects its directory;
- the local Python import closure (`ast`), plus files loaded by path, is followed;
  a `sys.path` insertion protects the inserted directory.

At the base commit this gives the directories `.claude`, `scripts/git-hooks`,
`scripts/hooks` and `tools/sota-convergence`, plus 23 files. A test fails when a hook
names a tracked file that the derivation misses.

Known limits:

- Over-inclusion: every settings string is scanned, and files named only in echo
  messages are protected.
- Misses, caught by the oracle test but not by the tokenizer: absolute checkout
  paths in hook text.
- Not traced: scripts started by `subprocess` with computed paths, and quoted words
  that contain spaces. The evaluator for `sys.path` targets is heuristic.

## gh harness

- **Environment:** children get an allowlist (plan section 3), never the parent's
  environment. The harness adds `GIT_CEILING_DIRECTORIES`, so that gh and git find
  no repository above their empty 0700 working directory.
- **Preflight:** the gh executable the harness is given by absolute path must
  report 2.101.0. `gh auth status --active
  --json hosts` is judged by its parsed state, because `--json` exits 0 either way.
  The login must be the owner's, over https, with the token from stored config or
  the keyring and the `repo` scope. Only the token source's class is recorded, never
  its path. The driver never calls `gh auth token`.
- **Denied before any subprocess:**
  - `pr ready`, `pr merge` and `--auto`, and other PR state changes;
  - merge endpoints, ref DELETE, other non-GET methods, and GraphQL;
  - `auth` changes and `--show-token`;
  - release, workflow, secret, repo and ruleset commands;
  - force, delete, tag, mirror, all and prune pushes, including abbreviated options,
    `+` and `:` refspecs, and `git credential`.
- **Push:** `git remote get-url --push --all origin` must list only this
  repository. The push resets every inherited credential helper with empty values,
  then uses gh's own helper for github.com only (gitcredentials(7); gh
  `helper_config.go:36-56`). A local-git test shows the reset and its negative
  control.
- **pr create:** source review of gh `create.go:283-287`, `833-866` and `1085-1096`
  shows that `--head` with `GH_REPO` needs no local repository. Stage B still has to
  observe it.

## Outgoing-text guard

Checks run in this order:

1. The attempt's session key: plain, folded, separator-stripped, hex and base64
   forms. The key is held in memory only and never rendered.
2. `scripts/validate.py`'s own `PRIVATE_CONTENT`, and its
   `scan_file_for_private_content` on the exact body file.
3. Registered host paths, and the host user name as a whole word.
4. Extra scanners. `gitleaks stdin` runs with `--ignore-gitleaks-allow` and a
   distinct leak exit code, because gitleaks and host launchers also exit 1 on
   errors.
5. For model text only: no closing keyword with an issue reference and no
   @mention.

Model text reaches GitHub only inside an adaptive code fence or code span.

## PR loop

1. **Draft PR:** it gets exactly one lane label and a body with the template's
   headings. The SOTA section holds resolvable citations only, and is checked with a
   port of the CI regex. The body ends with `Closes #N` and EXT's disclosure.
2. **Read-back:** confirms an open draft on `main`, the label, the body, no merge
   and no auto-merge.
3. **Checks and review:** the required checks are polled, bounded at 60 minutes;
   "no checks reported" counts as pending. Then one body-only COMMENT review of the
   head, with its text from the injected reviewer.
4. **Repair:** one repair from the injected repairer, accepted only when the
   compare API reports `ahead`.
5. **Stop:** one residuals comment, a final read-back, then stop. A second
   `ReviewLoop.run()` stops before any call.

## Stage-2 integration points (anchors at e45c3cd1)

- **`host.py`:**
  - `preflight` (:194): skip the memory, embedding and QMD checks.
  - `workspace_skills` and `install_workspace_skills`: the resolver skill set, which
    is tdd, search-first and this skill.
  - `runtime_mounts` and the QMD setup step: skip.
  - `clone_command` and `run`: an anonymous pinned-main clone with its remote
    removed, and `git show <base>:AGENTS.md` written to the input mount.
  - `prepare_native_dispatch`: a resolver branch.
  - The attempt's session key goes to `OutgoingGuard` in memory.
- **`worker.py`:**
  - `build_agent`: an explicit `agents` skill, a resolver suffix, and zero MCP
    servers.
  - `worker_hooks` and `start_request`: no `hook_config` without MCP, and
    `resolver_instruction` as the message.
- **`dispatch.py`:**
  - `finish_result`: after the export, `validate_patch` on a `GitTree` at the base;
    `git apply --index --check`, then apply in a fresh clone; commit with EXT's
    identity and hooks off; `next_branch`; `GhHarness.push`; `open_pull_request`;
    `ReviewLoop`.
  - `execute`: the `rw-openhands-res-<N>-<date>` run id.
- **`resolver.py run`:** build the harness with the pinned gh and a gitleaks
  scanner, and a guard with the attempt's host paths.
