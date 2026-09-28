# actionlint successor parity trial (2026-09-27)

Plan move M2 of the 2026-09-27 integrity-gate wave. The required `validate` job
pins `rhysd/actionlint` 1.7.12, whose upstream has stalled. This receipt
verifies the maintained fork `kjanat/actionlint` v1.17.0 and compares the two
binaries on this repository's workflows. It also backs the new non-required
`actionlint-successor` job in `.github/workflows/validate.yml`.

`receipt.json` holds the recorded values this page quotes. It was recorded at
`catalog_revision` `ba1700adc6557b03d3c9336c4d3a951791fc8de5`, main's tip
during the run. The upstream observations, verification and parity ran from
2026-09-28T02:03Z to 02:16Z UTC (2026-09-27 evening EDT). The branch checks,
mutation controls, attestation-count query and commit-author query followed
in the same session.
Evidence classes follow the brief: **upstream-unchanged** (an upstream tool or
verifier run as published), **our-integration** (our driver, fixtures,
mutations and tests) and **live-run-pending** (needs the hosted run).

## Upstream status, re-observed (upstream-unchanged)

Source: `gh api`, at 2026-09-28T02:03:12Z.

- **`rhysd/actionlint`.**
  - The last commit on main is 011a6d15 (2026-04-19), and main has no commit
    since 2026-06-29.
  - The latest release is still v1.7.12 (2026-03-30).
  - Issue #719, "rhysd (the author) inactive. Any active forks?", has been
    open since 2026-08-06.
  - The repository's `pushed_at` of 2026-07-16 is a push to another ref, not
    to main.
- **`kjanat/actionlint`.**
  - It was forked on 2026-08-07.
  - It has shipped 12 immutable releases, v1.8.0 (2026-08-18) to v1.17.0
    (2026-09-13).
  - `kjanat` wrote 242 of the 253 default-branch commits.
  - Commits fa049a71 and fc3cee3c accommodate Claude Code in the fork's own
    development.

## Verification (upstream-unchanged)

| Check | 1.7.12 (`rhysd`) | 1.17.0 (`kjanat`) |
| --- | --- | --- |
| `sha256sum --check`, same form as validate.yml | `8aca8db9…` OK, exit 0 | `620abd48…` OK, exit 0 |
| Matching `*_checksums.txt` line | yes | yes |
| `gh attestation verify --repo …` | exit 0, SLSA v1 | exit 0, SLSA v1 |
| Signer identity (SAN) | `rhysd/actionlint/.github/workflows/release.yaml@refs/tags/v1.7.12` | `kjanat/actionlint/.github/workflows/release.yml@refs/tags/v1.17.0` |
| Source digest, runner | 914e7df2, github-hosted | 08bb2c4f, github-hosted |
| Identity-pinned re-verify (`--cert-identity`/`--signer-workflow`, `--source-ref`, `--source-digest`, `--deny-self-hosted-runners`) | exit 0 | exit 0 for both identity forms |
| Immutable release | no | yes (`gh api`, `gh release view`) |
| `gh release verify` / `verify-asset` | n/a | exit 0 / exit 0 |

- The 1.17.0 digest carries 2 attestations: SLSA provenance and the
  immutable-release attestation (`https://in-toto.io/attestation/release/v0.2`).
- The annotated tag object 2da2ceb4 points to commit 08bb2c4f, the same
  commit the provenance names.
- Four negative controls each exited 1:
  - a wrong digest;
  - a wrong `--source-ref`;
  - the wrong repository;
  - a wrong `--cert-identity`.
- The parity config needed the runner's shellcheck. We fetched `shellcheck`
  0.9.0-1 through `apt-get download` and never installed it. It is the
  ubuntu-24.04 runner image's own version, and that image lists no pyflakes.
  Its trust chain:
  - the `.deb` SHA-256 matches the Packages index;
  - the Packages hash matches InRelease;
  - `gpgv` reported a good Ubuntu Archive signature.
- **Order.** Every table row except "Immutable release", the tag lookup and
  the four negative controls finished before either binary first ran; the
  first `-version` output is dated 02:05:54Z. The `gh release view` read and
  the shellcheck checks left no timestamped output, and the 2-attestation
  count ran after parity, so none of them is claimed as coming first.
  `receipt.json` `verification.order` gives the sources.

Flags: validate.yml passes `-version` and `-color`, and both exist in the
1.17.0 `--help` output.

## Parity on this repository (our-integration)

We ran `parity_driver.sh` from the checkout root:

- `-version` and `-color`, exactly as validate.yml does;
- `-format '{{json .}}'`, for pairing;
- `-verbose`, for what was linted.

Every run used `env -i`, the same PATH for both binaries, and no
`.github/actionlint.yaml`. `compare.py` pairs diagnostics on (file, line,
column, kind), then compares their messages as multisets, so each copy of a
duplicated diagnostic counts. A second pass catches findings whose column
moved. The counts below came from an earlier revision that matched messages
by membership. After review, the multiset revision was re-run over the six
retained report pairs: every count is unchanged, and the two fixture
pairings are byte-identical (`receipt.json` `parity.compare_rerun`).

| Tree | Tools on PATH | 1.7.12 `-color` | 1.17.0 `-color` | Files linted | Differences |
| --- | --- | --- | --- | --- | --- |
| ba1700ad (18 workflows) | none | exit 0, 0 diagnostics | exit 0, 0 diagnostics | 18 / 18 | 0 |
| ba1700ad | shellcheck 0.9.0, no pyflakes | exit 0, 0 | exit 0, 0 | 18 / 18 | 0 |
| this branch (new job added) | none | exit 0, 0 | exit 0, 0 | 18 / 18 | 0 |
| this branch | shellcheck 0.9.0, no pyflakes | exit 0, 0 | exit 0, 0 | 18 / 18 | 0 |

With shellcheck on PATH, neither binary logged `Rule "shellcheck" was
disabled`. Without it, both logged the line for all 18 files, so the
shellcheck path ran in the second configuration.

## Classification of the observed differences

Repository counts cover both trees and both configurations. Fixture counts are
under shellcheck 0.9.0. Upstream citations are in `receipt.json` under
`classification`.

| Class | Repository | Fixtures | Upstream source |
| --- | --- | --- | --- |
| identical | 0 | 3: `steps.get_value` undefined (x2), `max-parallel: 0` | unchanged behaviour |
| relocated (same finding, new column) | 0 | 2: SC2086 at column 9 in 1.7.12, column 19 in 1.17.0 | kjanat CHANGELOG v1.11.0: ShellCheck findings at exact YAML source locations |
| removed (1.7.12 rejects syntax GitHub accepts) | 0 | 8: `fromJSON` strategy (x2), `description`, `cancel-timeout-minutes`, `queue` (x2), `cache-mode` (x2) | CHANGELOG v1.8.0 (`queue`); v1.17.0 (workflow fields, `cache-mode`); v1.17.0 release notes |
| new true positive | 0 | 2: schedule entry without `cron`; `queue: max` with `cancel-in-progress: true` | v1.17.0 release notes, "Catch missing checks before GitHub does"; CHANGELOG v1.8.0 |
| default-config change (cache policies) | 0 | 2: `cache-operation`, `cache-write-untrusted` | CHANGELOG v1.17.0 upgrade note: three policies on without a config file |
| reworded | 0 | 0 | none observed |
| new false positive | 0 | 0 | none observed |

- **Why the cache policies found nothing here.** No workflow in this
  repository declares `cache-mode` or runs on `pull_request_target`,
  `issue_comment` or `workflow_run`.
- **Fixture sources.** The fixtures under `fixtures/` are stored as `.yml.txt`.
  - c1 and c2 are verbatim from rhysd v1.7.12 `docs/checks.md`.
  - c3 and c4 are verbatim from the v1.17.0 release notes.
  - c6, c7 and c9 are release-note snippets with a minimal job added.
  - c5, c8 and c10 are constructed from the documented rules.
  - `receipt.json` `fixture_provenance` gives each file's source.
- **The fixtures fail both binaries.** Both exit 1 on them, so the zero on the
  repository is not a vacuous pass.
- **Not exercised.** The fixtures give at least one recorded example of five
  classes above: identical, relocated, removed, new true positive and
  default-config change. They give none of reworded or new false positive
  (0 in the table), so they do not demonstrate those two, and they do not
  cover every change in the release. These were not exercised:
  - v1.8.0's runner-label alias remaps;
  - the v1.17.0 action-manifest and composite-step audit;
  - snapshot and matrix `include` expression checks;
  - the `cache-call-unrestricted` policy.

## New job and checks (our-integration)

The `actionlint-successor` job repeats the 1.7.12 step's download,
`sha256sum --check`, extract and `-version`/`-color` pattern for 1.17.0. It
keeps the house style:

- harden-runner in audit mode as the first step;
- `permissions: contents: read`;
- the same SHA-pinned `harden-runner` and `checkout` as the other jobs;
- `persist-credentials: false`;
- `timeout-minutes: 5`;
- no `continue-on-error`.

It is absent from `.github/main-ruleset.json`'s `required_status_checks`.

Checks run on this branch:

- **`python3 -m unittest tests.test_workflow_hardening -v`**: 61 tests OK,
  with 2 skips. One is the empty hash-frozen set. The other is PyYAML being
  absent.
- **`python3 -m unittest tests.test_zizmor_negative_control -v`**: 4 tests OK.
- **validate.yml's zizmor command**, without a token: exit 0, no findings. It
  suppressed 43 findings, against 42 on the base tree. The extra one is the
  pedantic `anonymous-definition` info that the four existing unnamed jobs
  also carry. The zizmor on PATH reports 1.30.1, but it was not checked
  against `.github/requirements-ci.txt`'s wheel hashes.
- **Mutation controls.**
  - Removing the new job's harden-runner step fails the harden-runner test,
    which names `validate.yml:actionlint-successor`.
  - Removing its `persist-credentials: false` makes zizmor exit 13 with
    `artipacked` at `validate.yml:164:9`.

## Live-run pending

- The hosted run of the new job and the pull request's checks.
- zizmor's online audits, which run with `github.token` in CI.
- The PyYAML-dependent parser cross-check.
- The required-gate swap. It waits for the hosted job to match this result.

## Retained failures and sanitization

- **The first identity-pinned attestation verify exited 1.** gh rejects
  `--cert-identity` together with `--signer-workflow`. Each flag passed on
  its own.
- **Superseded runs.** An earlier driver revision's base run gave the same
  zero-difference result and was replaced, along with the first fixture
  pairing, before the column-move pass existed. The raw outputs of both are
  not retained.
- **Sanitization.** Host paths are replaced by `<scratch>` and
  `<checkout root>`. Verbose logs are reduced to counts. No credential was
  read.
- **Where the other checks are.** `scripts/validate.py`, the catalog checks
  and the whole unittest suite ran after this receipt was registered. Their
  exit codes are in the handoff.
