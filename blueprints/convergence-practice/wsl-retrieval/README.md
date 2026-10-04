# Retired historical WSL retrieval reference

This directory is retired for installation and source/QMD replay. [run.py](run.py)
fails both old modes before launching a subprocess or creating an output directory.
The dependency-free [package.json](package.json) is a retirement guard; the original
manifest and recording aid are preserved as text artifacts. Since 2026-10-04 the
retained lock is stored byte-identical as [package-lock.json.frozen](package-lock.json.frozen),
a name no dependency scanner reads ([below](#lock-renamed-out-of-scanner-discovery-2026-10-04)).
Neither the retirement nor the rename patches the dependency, and no scanner
exception remains for it.

The separate current QMD recipe is in [recipes/README.md](../../../recipes/README.md#component-catalog-install-and-check),
with current native fixture guidance in [docs/native-token-ci.md](../../../docs/native-token-ci.md).
Active QMD's [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
advisory remains unresolved; this historical retirement does not qualify or change
that setup. [retirement-assessment.json](retirement-assessment.json) records the
current source disposition separately from the original receipts.

The retained September 20, 2026 receipts are an **incomplete historical fixture
reference**. They do not establish native E2E or adoption acceptance. Per-command
`argv` and working directories were not retained, and the original private raw-log
locations could not be verified. Selected outputs and hashes can be checked for
consistency, but cannot independently identify the commands that produced them.
The historical QMD installation also disabled all npm lifecycle scripts, which is
not the supported fresh-host recipe. The current assessment therefore defers
acceptance in [experiment.json](experiment.json).

The receipts report these outcomes, without a new native run during offline review:

| Retained attempt | Reported outcome | Recorded commands |
| --- | --- | --- |
| [Source attempt 1](source-receipt.json) | 22 checks passed | 6 |
| [QMD attempt 1](qmd-attempt-1.json) | URI-checker assertion failed | 5 |
| [QMD attempt 2](qmd-receipt.json) | 70 checks passed | 17 |

The source fixture contains the frozen planner from repository revision
`6f74bc503ccecaaf6ccebd53677b23aedab50921`. Its selected ripgrep **15.2.0** and
ast-grep **0.45.3** results contain exact file lines, byte spans and source text.
The QMD **2.8.3** fixture reports Node **24.21.0**, better-sqlite3 **13.0.3** and
sqlite-vec **0.1.9**, with the retained [package lock](package-lock.json.frozen). It covers
five positive and two negative queries, Unicode, a one-line `get`, process reopen,
update and deletion in a three-document primary collection plus one decoy.
The final recorded database has integrity `ok`, three active documents and zero
vector rows. These are receipt contents, not independently recovered execution.

These locally authored integration checks use synthetic documents and a frozen
source file. Under the [acceptance evidence policy](../../../docs/acceptance-evidence-policy.md),
they cannot substitute for unchanged upstream tests. No semantic RAG, production
corpus, native client, service, inference, OS-confinement or token-saving acceptance
is claimed. Output bounds are assertions after capture, not streaming limits.

## Preserved history and the provenance gap

The initial QMD checker compared an entire URI with a bare collection/path. The
selected output included the expected body and `?index=wsl-retrieval-fixture`, but
`qmd-positive-0_paths` failed. [run-initial.py.txt](run-initial.py.txt) preserves the
source attempt and failed QMD attempt's runner. The corrected historical runner
is now archived as [run-qmd-attempt-2.py.txt](run-qmd-attempt-2.py.txt), with its
original SHA-256 `4cbcceac02158629ca78262aaa826c995c21bbe45fa83481f7c139f16a6c52d2`.
The successful QMD receipt originally mapped `run.py` directly; the offline audit
now resolves that historical name to the archived bytes. Neither receipt was
rewritten to pretend it recorded today's file or missing invocation metadata.

[package-original.json.txt](package-original.json.txt) preserves the original
174-byte manifest with SHA-256
`7bbf63c5eafd347ae5ae56c684be06ef2589d38f2aab580ca7986ca4122bc6a8`.
Every historical `package.json` binding resolves to that archive without rewriting
the receipts' frozen-input names or declared runner mappings.
[run-recording-aid.py.txt](run-recording-aid.py.txt) preserves the later 16,427-byte
recording aid with SHA-256
`be852ce99501f5bc4567b846b90fb0e91d91de77b0eafbd3b72bb4484a2f7d12`.
It was a future recording aid, and is not attributed to the original execution.
All original receipts, source review and earlier runner archives remain unchanged.

The [install receipt](install-receipt.json) still records the actual historical
`npm ci --ignore-scripts --omit=optional` action. Its contents and digest are
unchanged. The [inventory](install-inventory.json) reports no optional llama
backend or model files, but does not qualify fresh native dependency setup.
[pins.json](pins.json) and [source-review.json](source-review.json) preserve dated
identities; release currency remains September 20, without a new latest-release
claim from the September 23 offline completion or subsequent review.

Original handoffs reported full stdout/stderr logs under private run directories.
Their exact locations remain unavailable, and those logs have not been reopened.
No command line or working directory has been reconstructed as an observation.
The historical [verification.json](verification.json) preserves the earlier
18-test offline check record; its original acceptance wording is superseded by
this incomplete assessment. Failed attempts and original evidence remain intact.

## Offline verification

From the repository root:

```sh
python3 blueprints/convergence-practice/wsl-retrieval/audit.py
python3 -m unittest tests.test_wsl_retrieval -v
python3 scripts/validate_convergence.py \
  blueprints/convergence-practice/wsl-retrieval/experiment.json --root . --json
python3 scripts/validate.py
```

The [audit](audit.py) requires the exact frozen-input and check-name sets for all
three receipts before comparing hashes and results. Mutation regressions reject
omitted inputs and same-count replacement checks as well as incorrect spans,
source bodies, URI scope, stale updates, erased failures and unsupported claims.
A zero audit exit means retained facts are consistent; its result explicitly
reports `native_acceptance_established: false`. It cannot repair missing evidence.
The companion `current_retirement_assessment` checks the exact new archives,
retained lock, retirement manifest and current entrypoint hashes. Regressions reject
changed recording-aid or manifest archives, restored dependencies/scripts and a
missing runtime guard. Both old modes must stop before output or subprocess work.
It also requires the lock to exist only as `package-lock.json.frozen` at its digest,
tracked in Git, and no `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`,
`pnpm-lock.yaml`, `bun.lock` or `deno.lock` anywhere in this directory, in any letter
case, on disk or in the Git index; it fails closed when Git cannot list the files.
Scenario regressions on scratch Git repositories and code mutants of the guard
(`LockDiscoveryGuardTests`) show each of those requirements is enforced.
These are local integration and artifact checks; they do not establish native npm
guard acceptance or a scanner exception.

## Supported entrypoint retirement

The retained private manifest has no dependencies or lifecycle/replay scripts. Its
`devEngines.runtime` names `retired-wsl-retrieval` with `onFail: error`. In the reviewed
[npm 11.19.0 supported behavior](https://github.com/npm/cli/blob/v11.19.0/lib/base-cmd.js#L201),
that runtime name is rejected before ordinary `install` and `ci`, including
`--ignore-scripts`. The [tagged manifest documentation](https://github.com/npm/cli/blob/v11.19.0/docs/lib/content/configuring-npm/package-json.md#L1117)
describes the check. Independent native controls belong to the separate retirement
acceptance record; the offline audit checks the guard's artifacts only.

Removing a manifest alone would leave [npm Arborist's root-lock fallback](https://github.com/npm/cli/blob/v11.19.0/workspaces/arborist/lib/arborist/load-virtual.js#L50).
The guard protects supported npm entry points. It is not an installation sandbox:
explicit `--force`, other package managers and restored historical files are
outside its claim. The text archives are evidence for offline review; this
directory provides no supported replay or installation route.

Recovered historical invocation evidence could reopen the incomplete acceptance
assessment. A current QMD trial belongs to the separate maintained recipe and
current status, with supported installation and complete command capture. Whole-task
provider, parent/child/retry/cache usage remains unknown; no savings claim is made.

## Lock renamed out of scanner discovery (2026-10-04)

The retained lock moved from `package-lock.json` to `package-lock.json.frozen` with
`git mv`. Its bytes are unchanged: 82,463 bytes, SHA-256
`5c51ee65cc477f2c1488a38ff5cad1c0a737f81a5b61bbd70d5edc4d15bfc3bb`.

GitHub's dependency graph, Scorecard's OSV-Scanner run and OSV-Scanner itself find
lockfiles by file name. Under its npm name this lock raised Dependabot alert 17
(braces 3.0.3, GHSA-vfj7-8cjw-p6xm, high, no patched release) and the Scorecard
code-scanning alert 19 that carries the same advisory. It also needed a dedicated
OSV-Scanner grant, due to expire on 2026-10-17. No scanner reads the `.frozen` name,
so that grant and its scan group are deleted. "Fixed" means the lock was removed
from discovery, not that braces was patched: the archived bytes still pin braces
3.0.3. Active QMD's own exposure to the advisory is unchanged and unresolved.

The receipts, the install inventory and the 2026-10-03 retirement assessment still
name the lock `package-lock.json`. The audit resolves that name to the archive, as it
resolves `package.json` to `package-original.json.txt`, and no receipt was rewritten.
The convergence record changes only the lock's path, with the same SHA-256, and the
evaluation digests of `audit.py` and `tests/test_wsl_retrieval.py`. This directory
still offers no supported way to restore or install the lock.

Decision: the 2026-10-04 addendum to
[2026-09-25-longmemeval-frozen-npm-lock.md](../../../docs/decisions/2026-09-25-longmemeval-frozen-npm-lock.md).
OSV-Scanner controls and the guard's mutants:
[wsl-lock-frozen-rename-20261004.json](../../../evidence/receipts/wsl-lock-frozen-rename-20261004.json).
