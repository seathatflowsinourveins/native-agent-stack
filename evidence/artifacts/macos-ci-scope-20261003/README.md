# macOS CI scope receipt (2026-10-03)

The measurement receipt for
[docs/decisions/2026-10-03-macos-ci-scope.md](../../../docs/decisions/2026-10-03-macos-ci-scope.md): the inputs its
replay used, the outputs its own replay and simulation saved, and a replay script that re-runs the pull-request replay
from those inputs.

**Evidence classes.** The GitHub reads (G, P, J, E) are historical API reads as fetched on 2026-10-03, not new runs.
The replay is a local artifact measurement over those reads and the repository at `6112d14d4`. The classification
labels are model output, kept as recorded. Nothing here is a hosted run of the changed workflow; the record's §6.7
controls are that.

**Provenance.** The record's rounds produced these files as working copies in a session scratch directory that is
wiped at boot. They were then kept outside the checkout, and this receipt copied them byte for byte on 2026-10-03. The
`gh` reads used the coordinator's own sign-in; no token or host path is in any file here (scans below).

## Files

| Key | File | sha256 | Bytes | Contents |
| --- | --- | --- | --- | --- |
| G | `runs_graphql.json` | `be20e3aecd835ea8b26565f87d0061280909d002a6a3682feccf3f18daae0c39` | 2161325 | GraphQL read of all 1,800 "Adoption bootstrap smoke" runs created 2026-09-23T23:16:19Z to 2026-10-03T18:29:50Z, with each check run's status, conclusion, start and end. Fetched 2026-10-03T18:37:38Z. |
| R | `files_of.json` | `e9d76e8c384f66cebfdef8cf095f5cc8e2cb06b7d01b5e18de7c67d943855df4` | 2926603 | For 1,747 of the 1,792 pull-request head SHAs, the file list of `git diff` against the merge base with main. |
| P | `prs_graphql.jsonl` | `2de818fa7ff5a828ff90057baded7449786461c25ecc5ad75d8e9582eba92bc9` | 422744 | The 13 GraphQL pages of the repository's 643 pull requests (head branch, state, merge commit, closedAt), fetched 2026-10-03T20:27Z. The pages are concatenated JSON documents, not one document per line. |
| P | `pr_map.json` | `8d499b66c8582c8172ea1ceb36c65f2964e68db9c8309e7f2f42f759a166e492` | 349949 | Derived from P: head SHA to pull request numbers, and each pull request's state, merge and close times. |
| M | `main_6112.json` | `23d8c3ac63a4328b685e44c02a0965ab45783f6fb546a732e5248daceb10face` | 542167 | The 369 first-parent commits of main at `6112d14d4` since 2026-09-25T00:00:00Z, with their files. |
| J | `job_111226811878.json` | `84b03a7993261f4013feee0a832582d6a60a398a4e864d5b85719b36721fdd2d` | 3282 | REST read of the steps of job 111226811878 (run 37131206057). |
| E | `macos-ci-evidence.json` | `2560d0d2e516785fea82941fc6fa2a5d3cfbc59af8f6c78214a88bca02da9e87` | 31213 | The REST sample: 1,000 runs, with jobs fetched for 256. |
| E | `macos_ci_evidence.py` | `d49cfea091c31588ec6e0d9fea16515081132df6a3513bd1d7a73d228e1e84bf` | 4499 | The script that fetched E with `gh api`. It writes `macos-ci-evidence.json` next to itself, so never run it in place: a run is a new live read, not a replay, and would overwrite the recorded file. |
| E | `macos_ci_summary.py` | `b93c3213e8a32fa1bd719a809265e4316fbb3604ded1f72b9bf1bf1be121946c` | 1862 | The summary script read with E. |
| K-C, K-G | `runs30.json` | `ef128445d1b8ac84db1cb9acdc80fc4296ddf8912f25d569ce92f2374638f3f2` | 6798 | The 30 macOS-only failures: event, each family's label (`gpt` is `-` for the 5 only the critic classified), failing modules, creation time, and the outcome under B0, B′ and (b2). |
| R | `fail_mods.json` | `f4e6988b8f72e5a31c2c8f409cc21f0b72e687a8dbcf9c066658a0ba3f4f515b` | 6537 | Per failure run: head SHA, failing test modules and the suite's summary lines, from the full-suite logs. |
| R | `run_pr.json` | `68f723d33fc74752605b531f111614495b1ee78dddac23eb868ddb4f20c058af` | 2651 | Per failure run: branch and pull request. |
| R | `d1_rows.json` | `c3d603434af74222e334038a76cf55f9b0ec61037870c14b5166ac2a042b39f1` | 3778 | The 18 deterministic macOS-only pull-request failures (D1) with each candidate's caught (`C`) or escaped (`-`) flag. |
| Lists | `lists_r2.json` | `8186d26d047243fc0689091382bf45b8f5f6290a1ef94e2f8efaa869794cb589` | 23921 | `B0`, the previous round's 67 patterns; `Bp`, the record's 89 (§6.2); and two working fields of the earlier static scan (`mac_tests`, 208 paths, and `tokens`, 303 search tokens) that no figure in the record uses directly. |
| Lists | `mac_tests_strict.json` | `289da3dfb339b85c77961be457f9574152407407848f2d1b5618a54d2c7a52ad` | 4199 | The 117 test modules of candidate (a-mac). |
| Lists | `c5wide.txt` | `9c1b2f766d93e667e088a733d4a3af77b0640a4f293cc53e22d1836cb0b51d7b` | 1334 | The 27 files of the widened C5 grep at `6112d14d4` (21 listed, 6 excluded). |
| Lists | `closure.json` | `d23ae588ff9678b2e7c0e56f8512b767c1dc0ba34edb5ac13ce350c55cf515e9` | 4138 | The 98 paths of the in-repository import closure of C3 and C4, from which the C6 entries come. |
| R | `modcount.json` | `b0f1fc1f7568f1969a54bca8a5542be868b07f4fdb9ed8b38370216462edc8db` | 8747 | Tests per module at the base, for the changed-tests duration estimate. |
| Saved output | `replay_r2.json` | `7bc87e20402e96fd3624b63bc9dfc3b1cd08668cef0222c23471a6c7f23cf21c` | 711 | The record's replay of B0, B′, (a-mac), (a-all) and (b2). |
| Saved output | `replay_final.json` | `db740c8e9736f42d88ea06892a0d7c69b346df10830e717b60dd61ea5920675c` | 1249 | The previous round's outcome for each of the 25 classified failures under B0. |
| Saved output | `sim_r2.json` | `84eaa304af37193799659f847cc2f24cd0aa70572f01e116ae5efd2555deceb9` | 783 | The 5-slot first-in-first-out simulation's outputs (an inference; its code was not retained). |
| Receipt check | `replay.py` | `ecd0e81da9770ae0b1b76f7a4f3d82a3b97a00e9e83b160a42238cc6e90118ad` | 12974 | Re-runs the replay; see below. |
| Receipt check | `replay-output.txt` | `5db05889dc24bbbf0cc307fac0364e569906a199badf91eb2265900ce49af436` | 3802 | Its output, run on 2026-10-03 by the implementing pull request at `nice -n 19`. |
| Receipt check | `replay-exit.txt` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` | 2 | Its exit code, `0`. |

`manifests/evidence.json` registers every file here, this README included.

## Referenced, not copied

These working copies are byte-identical to repository content at the verification base, so the receipt names the
command that reproduces each instead of a copy.

| Working copy | sha256 | Reproduced by |
| --- | --- | --- |
| `ab.yml` | `bcfcb91c7a1bc0ec16eb1223776ff91c8e4311dc2be6a55312ddbf387bc0bc1f` | `git show 6112d14d4:.github/workflows/adoption-bootstrap.yml` |
| `closure.md` | `82695fb0f06eb10ab874ecc1f592b0f8baf4c793547c3b4d52719a5c4c91867f` | `git show 6112d14d4:docs/decisions/2026-09-22-github-automation-closure.md` |
| `ruleset.json` | `5b6a1543053c995222fb0b6de9e213fa9446aa86e20aaa6086e6289bf1e97013` | `git show 6112d14d4:.github/main-ruleset.json` |
| `tracked_6112.txt` | `db754181a87b8b0f09d8c7fe7b52918c6f84dac2f53e3d4cd9394bcc74204a9f` | `git ls-tree -r --name-only 6112d14d4`, run from the repository root |

M's commits and file lists (`main_6112.json`) equal, commit for commit, the output of
`git -c core.quotepath=false log --first-parent --name-only --no-renames --since=2026-09-25T00:00:00Z 6112d14d4`
(checked by the implementing pull request). Its raw working copy, `main_6112.txt`, is not copied.

## Not retained

- **L**, the GraphQL read of live jobs at 2026-10-03T18:44:39Z. The record takes it from the previous round.
- **The full K-C and K-G results**: the previous round's Claude output (with its Mac host audit and the critique) and
  the GPT result `macos-classify2-20261003T193218Z`. `runs30.json` carries both families' per-run labels.
- **The original replay and simulation code.** `replay.py` re-implements the replay from the record's method; nothing
  here re-implements the simulation.
- **Superseded or unused working copies**, with their sha256 for anyone holding them:
  `lists.json` (`e4de44caeed2426e27a022010baa5d1a4ab84e653eb9752db227381e6448ac57`),
  `lists2.json` (`db881b5341b1955c5db35fad828a6a49da8b05a01b6bc203488b833ba954222e`),
  `lists3.json` (`d3dd59d191eccbe9e54b8c252be8e185b1ed727b1300621bcac9b21962f0aa08`) and
  `lists4.json` (`85384b0bc54d2f8cdc2c77cc664909488f3dfce7c187640b1f91093d7a572671`), the earlier rounds' lists, whose
  67-pattern list is `lists_r2.json`'s `B0`; `replay.json` (`200c481e7f4e279f8d9fde710e5a945dd7659ef365f8e16762123c80596c5c5d`),
  an earlier round's replay of the 25 with superseded lists; `main_commits.json`
  (`71c955d94ddf5b3bed41f97d716879ed028b979e2e5dc26ca43dee2e9c534b5c`), M at an earlier base;
  `main_6112.txt` (`5f7184bfbe6b6650fbac9c36de081a588075d823c2122c88c11d1407769d573d`), the raw log that
  `main_6112.json` parses; `decision-record-draft.md`
  (`3f2aea7e98dff3d553fdf99afb840df6e6be5b7a0255021e75dc878bfe8f0897`), the previous round's draft, which the record
  supersedes; `pr632.md` (`2a4eb8819b32b7bf7c9f83e8df1d35e86e9da61075440c02e1027bafaafea7b3`), PR #632's record at
  `85e9bc653`, readable in that pull request; and `prs_graphql.err`, the P fetch's standard error, which was empty.

## Re-running the replay

From any directory of a clone that holds `6112d14d4` (a full-history clone):

```sh
python3 evidence/artifacts/macos-ci-scope-20261003/replay.py
```

It needs the standard library only, runs offline, and writes nothing. It reads `MACOS_PATTERNS` from the committed
`.github/workflows/adoption-bootstrap.yml`, so it measures the list that ships, then compares each recomputed number
with the record's figure and with the saved outputs above, one line per comparison. Exit status 0 means every
comparison matched. The method is in the script's docstring; in short, a pattern matches as a bash `case` glob does,
a head SHA without a file list counts as a full run, and no module is dropped as deleted, because the file lists carry
no deletion status.

**Result on 2026-10-03** (`replay-output.txt`, exit 0): every checked figure matched. That covers the 89 patterns
(equal to the record's list, matching 151 files at the base, none dead); the 1,069 pull-request jobs and their 348.8
slot-hours; the full, skipped and changed-tests counts and slot-hours of B0, B′, (a-mac), (a-all) and (b2), including
(b2)'s 0.67 and 1.23 min changed-tests estimate; the 18 D1 rows and their escapes per candidate; the pull-request rows
of the 30-run table; both families' label counts over the 25; the main-commit exposure; and the 1,211 pull-request
runs with a `changes` result. Two figures do not reproduce, and the record's §10 says so:

- `sim_r2.json` gives (b2) with B+ as 339.9 slot-hours and a pull-request wait p90 of 1.7 min, while the record states
  319.6 and 1.4. The simulation code was not retained, so neither can be re-run.
- The record's "52 of 1,211" counts skipped `bootstrap-macos` check runs across all events, one of them a
  `workflow_dispatch` run. Among the pull-request runs it is 51.

## Scans

On 2026-10-03, before commit: `python3 scripts/validate.py --scan-file` over every file here and every file the
implementing pull request changed found none of the repository's private-content patterns, and gitleaks 8.30.1
(`gitleaks dir` with the repository's `.gitleaks.toml`, `--redact`) found no leaks in the same files.
