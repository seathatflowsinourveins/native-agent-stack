# New-machine install: hosted macOS arm64 bootstrap smoke (PR-6)

## Scope

PR-6 adds a portable, pinned macOS arm64 install path next to the accepted
Linux/WSL2 one, split into four units on separate worktrees over base commit
`445bc83`:

- **U-A** — `adoption/bootstrap-macos.sh`, the checksum-verified installer.
- **U-B** — `adoption/pins-macos-arm64.json`, the publisher-checksum pin set.
- **U-C** — this unit: the hosted `bootstrap-macos` job in
  [`.github/workflows/adoption-bootstrap.yml`](../../.github/workflows/adoption-bootstrap.yml)
  and this task record. Branch `claude/nmi-ci`.
- **U-D** — the macOS platform page and manifest/profile wiring.

Every unit codes against one fixed CLI contract so the workflow and the script
can be written in parallel:

```
bash adoption/bootstrap-macos.sh --profile <id> [--skip-system-packages] [--plan]
```

`ECO_INSTALL_ROOT` (default `$HOME/.local/share/codex-ecosystem`) selects the
prefix; the script writes `$ECO_INSTALL_ROOT/installed-versions.txt`; exit `2`
is a usage error, `1` a guard or refusal, `0` success; `--plan` resolves the
profile's pins with no network and still exits `1` on a null `sha256`.

This unit's owned paths are the workflow (new job only; the existing
`bootstrap-linux` job is untouched) and this file. It does not edit
`docs/github-automation.md`, `.gitleaks.toml`, `adoption/bootstrap-linux.sh`,
`tools/adoption/render_config.py`, `catalogs/foundation/automation.json`,
`catalogs/landscape/*`, `catalogs/sota-convergence/*`,
`catalogs/foundation/decisions.json`, `tools/sota-convergence/*`,
`docs/grand-catalog-handbook.md`, `manifests/evidence.json` or
`docs/ecosystem/*` — all peer- or coordinator-owned. The CI prose that would
normally live in `docs/github-automation.md` is therefore kept here.

## Decisions

1. **The hosted macOS run is a distinct `hosted_smoke` field, never a platform
   status flip.** `adoption/manifest.json` keeps `macos-arm64` at
   `drafted_not_accepted` and `supported_platforms` keeps `linux/x86_64`
   Python `3.13` only. A green `bootstrap-macos` job is recorded as its own
   hosted-smoke field/receipt, not as `accepted`. Alternatives considered:
   adding `macos/arm64` to `supported_platforms` so the status report turns
   green (rejected — it would silently reclassify an unaccepted platform and
   would make `scripts/adoption_status.py` report `prerequisites_present` on a
   runner that is not a developer workstation), or leaving macOS with no
   automated signal at all (rejected — no regression detection for the pins).
   Overturn only on an actual Mac workstation acceptance receipt, not on a
   hosted run.

2. **The status step accepts exit code `2` explicitly.**
   `scripts/adoption_status.py` returns `0` only when
   `status == "prerequisites_present"`, which requires `platform.supported`
   true; on darwin that is false by construction (lines 180-198), so the
   command exits `2` even when every profile command is installed. The job
   therefore accepts `0` or `2` and fails on any other code, and asserts the
   real signal separately with `jq`: no `profiles[].commands[]` and no
   `profiles[].recipes[]` entry with `present == false`, and
   `platform.os == "darwin"`, `platform.architecture == "arm64"`,
   `platform.supported == false`. Alternative considered: `|| true` around the
   command (rejected — it would swallow a genuine crash).

   **Fail-closed correction (independent review, 2026-09-22).** Accepting exit
   `2` initially removed the Linux job's fail-closed property: when the manifest
   or the requested profile is broken, `inspect_adoption` returns early with
   `manifest.status == "invalid"`, `"profiles": []` and a non-empty `errors`
   list, and `main()` still returns `2`. Against that report every emptiness
   assertion above passes vacuously (`[.profiles[].commands[] | select(...)] |
   length == 0` is `true` over an empty array, and `platform.supported` is
   initialised `false`), so a broken macOS profile — exactly what this smoke has
   to catch — would have gone green. A positive step now runs *before* the
   emptiness assertions and checks that the report is a real
   `macos-arm64-foundation` report: `.manifest.status == "valid"`,
   `.errors | length == 0`, exactly one profile with that id, its `commands` and
   `recipes` arrays non-empty, and its `status == "prerequisites_present"`. The
   last check subsumes the emptiness pair; both are kept because they localise
   the failure to a command versus a recipe in the step log.

3. **Portable-runner provenance.** `runs-on: macos-15` is GitHub's Apple
   Silicon image and is free for public repositories; the job additionally
   asserts `uname -m = arm64` and captures `sw_vers` rather than trusting the
   label, because the label-to-architecture mapping is a platform decision
   that has changed before. `sw_vers.txt` ships in the artifact so the image
   version is recoverable from the run.

4. **Step-0 pin.** The job reuses exactly the SHA-pinned actions the Linux job
   already uses — `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`
   (v7.0.1), `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97`
   (v7.0.0) with `python-version: '3.13'` and `check-latest: false`, and
   `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
   (v7.0.1) — with `persist-credentials: false` on checkout and no job-level
   `permissions` block, so the job inherits the workflow's `contents: read`.
   Python 3.13 is installed before the status step for the same reason the
   Linux job does it (`tests/test_adoption_bootstrap.py`'s
   `AdoptionWorkflowPythonVersionTests`): the manifest pins the 3.13 line.

5. **Artifacts use `if-no-files-found: warn`, not `error`.** A "Collect the
   artifact payload" step with `if: always()` copies `status.json`,
   `sw_vers.txt` and `$RUNNER_TEMP/eco/installed-versions.txt` into
   `macos-status/` when each exists and names the absent ones. If the
   bootstrap fails, that step's failure must remain the visible failure
   instead of being replaced by a missing-artifact error. Artifact name
   `adoption-bootstrap-macos-status-<run_id>-<run_attempt>`, retention 30 days
   (longer than the Linux job's 7, because the macOS receipt has to outlive
   the review window).

6. **`render_config.py` runs with the committed example host.**
   `python3 tools/adoption/render_config.py --host example --out
   "$RUNNER_TEMP/rendered"` needs no live client files: `--host` reads the
   tracked `adoption/hosts/example.json`, and `--out` only writes into the
   chosen directory. (`--check`, which diffs against live configs, is
   deliberately not run in CI — there are no live configs on a runner.) This
   was confirmed locally before writing the step; see Verification.

7. **No change to `on:`.** The workflow's existing `push`/`pull_request` path
   filters already include `adoption/**` and
   `.github/workflows/adoption-bootstrap.yml`, so `adoption/bootstrap-macos.sh`
   and `adoption/pins-macos-arm64.json` trigger the job without touching the
   peer-owned trigger block. The weekly `schedule` and `workflow_dispatch`
   triggers apply to the new job too, so the pins get the same weekly live
   re-check the Linux pins get.

8. **`tests/test_workflow_security_coverage.py` is left unchanged.** Its
   coverage set enumerates workflow *files* (`WORKFLOWS_DIR.glob("*.yml")`),
   not jobs, and `adoption-bootstrap.yml` is already listed at line 56. The
   brief's condition for extending it ("only if its coverage set enumerates
   jobs") is not met.

9. **`gh --version` is printed for the run log, not as pinned-install
   evidence.** `gh` is not in the `macos-arm64-foundation` profile's
   `required_commands` and is preinstalled on the runner image, so the line
   normally reports the image's `gh` rather than anything the pinned bootstrap
   installed. A comment on that line says so, and the artifact's
   `installed-versions.txt` (hashed into the receipt as
   `installed_versions_sha256`) stays the authoritative pinned-version record.

10. **Static coverage of the profile id is an integration follow-up.**
    `tests/test_adoption_bootstrap.py` is outside this unit's owned paths. Its
    `test_profile_ids_referenced_by_workflow_exist_in_manifest` asserts only
    `foundation-cpu`, and `WorkflowReferenceTests` asserts only the Linux script
    path, so nothing statically fails if `macos-arm64-foundation` is renamed or
    dropped from `adoption/manifest.json`. The profile does exist today (ids:
    `foundation-cpu`, `research-runtime`, `observability`, `semantic-rag`,
    `recovery`, `macos-arm64-foundation`, `trading-nautilus`), and the new
    positive `jq` step in Decision 2 catches the rename at run time. The
    coordinator or U-D should still add `assertIn("macos-arm64-foundation",
    profile_ids)` and a `WorkflowReferenceTests` assertion for
    `adoption/bootstrap-macos.sh` at integration.

## Verification

Run from this unit's worktree on the WSL2 Linux host, branch `claude/nmi-ci`,
base commit `445bc83`. Commands were run raw (`rtk proxy`).

| Command | Exit | Observed |
| --- | --- | --- |
| `python3 -m unittest tests.test_workflow_security tests.test_workflow_security_coverage tests.test_adoption_bootstrap -v` | 0 | `Ran 30 tests in 0.158s` / `OK`, no skips. `test_workflow_security*` contributes 5 of them and did **not** skip (zizmor v1.30.1 is on PATH). `test_profile_ids_referenced_by_workflow_exist_in_manifest` and `AdoptionWorkflowPythonVersionTests` both still pass with the new job appended. |
| `zizmor --offline --no-config --no-ignores --persona regular --strict-collection .github/workflows` | 0 | `zizmor v1.30.1`, 12 workflow files audited, `No findings to report. Good job! (27 suppressed)` |
| `actionlint .github/workflows/adoption-bootstrap.yml` | not run | `which actionlint` exited 1 with no output: actionlint is **not** on this host's PATH |
| `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/adoption-bootstrap.yml')); print(sorted(d['jobs']))"` | 0 | parses; printed `['bootstrap-linux', 'bootstrap-macos']` |
| `grep -rn -E '/(home\|Users)/[a-z]' .github/workflows/adoption-bootstrap.yml docs/tasks/2026-09-22-new-machine-install.md` | 1 | no matches — no literal personal home path in either owned file, as `scripts/validate.py` PRIVATE_CONTENT requires |
| `python3 scripts/validate.py` | 1 | exactly two lines, both for the one file this unit changed: `.github/workflows/adoption-bootstrap.yml: SHA-256 mismatch` and `.github/workflows/adoption-bootstrap.yml: byte count mismatch` (the same cause — `manifests/evidence.json` still records the pre-edit digest and length; the coordinator rehashes at integration, and this unit is forbidden from editing that manifest) |

Evidence class for this unit: **structural validation** (syntax, static
security analysis, local contract tests). No macOS runner has executed this
job, so there is no native-operation evidence for it yet, and
`adoption/bootstrap-macos.sh` is written by a sibling unit — until both land on
the integration branch, the job cannot pass.

### Integration gates — to be filled at integration

The coordinator runs these on the integrated branch and records exact exit
codes here:

| Gate command | Exit | Observed |
| --- | --- | --- |
| `python3 scripts/build_ecosystem.py --check` | | |
| `python3 scripts/validate.py` | | |
| `python3 scripts/validate_catalogs.py` | | |
| `python3 scripts/validate_foundation.py --root . --json` | | |
| `python3 scripts/validate_convergence.py` | | |
| `python3 -m unittest` | | |
| `gitleaks` through the guarded ecosystem launcher | | |

### Receipt protocol

After the first green `bootstrap-macos` run on the integration branch, the
coordinator writes
`evidence/receipts/adoption-macos-hosted-smoke-20260922.json` with
`kind: native_cli_e2e`, `component_ids` set to the components the
`macos-arm64-foundation` profile pins, and `data` carrying `run_id`,
`run_url`, `run_attempt`, `head_sha`, `runner_label`, `image_version` (from
the uploaded `sw_vers.txt`), `status_artifact_sha256` and
`installed_versions_sha256`; `limitations` repeats the Limits below verbatim.
The coordinator then registers the receipt in `manifests/evidence.json`. No
receipt is written from a workflow file's mere existence, and a failed or
cancelled run is recorded as such rather than retried into a green receipt.

## Limits

- macOS stays `drafted_not_accepted`. A hosted runner is not a Mac
  workstation: no user account, no Homebrew-managed system state carried
  across runs, no Metal GPU work, no client sign-in.
- The job has never run. Everything above is structural; `zizmor` and the unit
  tests analyze the file, they do not execute the workflow. The run will fail
  until the sibling unit's `adoption/bootstrap-macos.sh` and
  `adoption/pins-macos-arm64.json` are merged.
- launchd service registration and the `llama-server` Metal embedding backend
  are unrun on any Mac. The job only prints `llama-server --version`; it does
  not start the server, load a model or measure an embedding.
- npm's optional darwin binaries are fetched by npm's own resolution, not from
  a checksum-pinned URL, so that part of the install is unpinned even though
  the top-level package versions are pinned.
- A fresh Mac ships `python3` 3.9 (or only the Command Line Tools shim). The
  CI job side-steps this with `actions/setup-python` 3.13; a real Mac install
  must install the 3.13 line first, and `scripts/adoption_status.py` will keep
  reporting `prerequisites_missing` until it does.
- There is no macOS equivalent of this host's guarded, memory-bounded runner
  (`ecosystem-bounded-run`, the guarded `gitleaks` launcher). Containment
  evidence from the Linux host does not transfer.
- `actionlint` was not available on this host, so the YAML has GitHub's
  schema-level lint only from `zizmor`'s collection plus `yaml.safe_load`;
  GitHub's own parser is the first to see it on the integration PR.
- `jq` and `gh` are assumed present on the `macos-15` image (both are
  documented preinstalled tools). If a future image drops either, the
  assertion and version steps fail loudly rather than silently skipping.
