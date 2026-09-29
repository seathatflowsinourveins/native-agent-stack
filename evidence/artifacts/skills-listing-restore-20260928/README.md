# supply-chain-risk-auditor tree check, 2026-09-28

This is the retained tree-drift proof for the
[host listing drift addendum](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md#addendum-2026-09-28-host-listing-drift-restored).
The listing restore itself is recorded in the receipt
[`skills-listing-restore-20260928`](../../receipts/skills-listing-restore-20260928.json).

All six runs were on host `nativestack-5975wx-20260925` on 2026-09-28, from 16:46:25Z to 16:46:27Z,
with `TMPDIR=/var/tmp`, from the root of this pull request's worktree. Its HEAD was `ea6e1d0f` (the
first line of [`run_checks.log`](run_checks.log)), and this round's repair was not yet committed.
The script that ran is therefore identified by its sha256, `17cc1c3e0211ffdd…`, which every output
records as `method.script_sha256`. Every output records Python 3.13.15 (`method.python`), and each
run that reached a command records gh 2.101.0 (`method.gh_version`).

## Method

`scripts/skills_status.py` reports this folder only as `folder_tree` `drift`. That state is
informational, and every use of the skill brings it back. [`tree_drift_check.py`](tree_drift_check.py)
names each differing blob and fails on any difference outside an explicit `--allow` set. It writes
nothing. It executes the checkout's `scripts/skills_status.py` from the bytes whose sha256 each
output records (`adf89cd8…`, unchanged since `3058b237`), and takes `_git_blob_sha`,
`git_tree_sha`, `RUNTIME_ARTIFACT_DIRS`, `load_manifest`, `check_folder_tree`, `check_canonical`
and `check_lock_entry` from it.

1. **Scan.** The installed folder is walked without following a symlink, by the
   "lstat()/open()/fstat() trick" of CPython 3.13's `os.fwalk` and `shutil.rmtree` (`Lib/os.py`
   `_fwalk`, `Lib/shutil.py` `_rmtree_safe_fd`). Runtime-artifact directories are left out and not
   entered, as `git_tree_sha` leaves them out. Any other entry that is not a directory or a regular
   file, any entry named `.git`, and a folder that is itself a symlink are refused before any file
   is read or any command runs.
2. **Upstream.** Each row under the manifest path in the pinned listing must be a `100644` or
   `100755` blob or a tree. Any other row, such as a `120000` symlink or a `160000` gitlink, is
   refused.
3. **In-memory tree.** `tree_sha_from_rows` hashes a map of blob rows with `git_tree_sha`'s entry
   encoding and order (`skills_status.py` L172-176). Two self-checks run in every run that gets past the entry scan (the retained pass, no-allowance and planted-blob runs); a run refused at the scan reaches neither, and the upstream-gitlink control reaches only the local one. From the local
   rows it must reproduce `git_tree_sha` of the folder, and from the upstream rows the upstream
   folder row and every subtree row.
4. **Compare, then substitute in memory.** A difference outside the `--allow` set fails before
   anything is substituted. Otherwise each allowed upstream blob is fetched and verified against
   its SHA, and its row replaces the local row in a copy of the row map. The resulting tree must
   equal both the manifest `tree_sha` and the upstream folder row.

Sources, read 2026-09-28, all at git v2.43.0 except the book:

- Tree object: `builtin/mktree.c` `write_tree` (L47-66), entries ordered by `tree.c`
  `base_name_compare` (L102-119), and the object header from `object-file.c`
  `format_object_header_literally` (L1074-1078).
- Regular-file modes: `Documentation/gitformat-index.txt` (L94), "Only 0755 and 0644 are valid for
  regular files", and [Pro Git, Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects).
- `.git` entries: `read-cache.c` `verify_dotfile` (L902-944) rejects a `.git` path component.
  `builtin/add.c` `check_embedded_repo` (L301-323) warns when `git add` meets an embedded
  repository, and its advice (L285-299) says that clones "will not contain the contents of the
  embedded repository": git records the directory as a gitlink, not as files.

## Runs

[`run_checks.sh`](run_checks.sh) made all six outputs and [`run_checks.log`](run_checks.log), run as
`TMPDIR=/var/tmp bash evidence/artifacts/skills-listing-restore-20260928/run_checks.sh > evidence/artifacts/skills-listing-restore-20260928/run_checks.log`.
Each folder fixture is a `cp -a` copy of the installed folder in one `mktemp -d` directory,
`/var/tmp/tdc-controls.wfFZOC`, which the script removed on exit. Every argv starts with
`python3 evidence/artifacts/skills-listing-restore-20260928/tree_drift_check.py --checkout . --skill supply-chain-risk-auditor`.

| Output | Further arguments | Fixture | Exit | Result |
| --- | --- | --- | --- | --- |
| [`tree-drift-check.json`](tree-drift-check.json) | `--allow scripts/uv.lock` | none: the installed folder | 0 | `pass` |
| [`control-no-allowance.json`](control-no-allowance.json) | none | none | 1 | `fail`: `scripts/uv.lock` is outside the empty allowed set, and nothing is substituted (`substitution` is null) |
| [`control-planted-blob.json`](control-planted-blob.json) | `--allow scripts/uv.lock --folder <copy>` | one newline appended to `scripts/model.py` | 1 | `fail`: `scripts/model.py` (`e948adfc…` in the copy, `81407c29…` upstream) is outside the allowed set, and nothing is substituted |
| [`control-symlink.json`](control-symlink.json) | `--allow scripts/uv.lock --folder <copy>` | `scripts/` moved out of the copy, to `outside/`, and replaced by a symlink to it | 2 | `refused`: `scripts` is a symlink. `runs` is empty, so no command ran. The log shows `outside/uv.lock` at sha256 `164f2149…` before and after the run |
| [`control-special-entries.json`](control-special-entries.json) | `--allow scripts/uv.lock --folder <copy>` | a FIFO at `assets/fifo`, and a gitfile reading `gitdir: ../.git/modules/agents` at `agents/.git` | 2 | `refused`: `agents/.git` (a file) and `assets/fifo` (a FIFO). `runs` is empty |
| [`control-upstream-gitlink.json`](control-upstream-gitlink.json) | `--allow scripts/uv.lock --gh evidence/artifacts/skills-listing-restore-20260928/fixture_gh_gitlink.py` | the installed folder, with the real listing rewritten by [`fixture_gh_gitlink.py`](fixture_gh_gitlink.py): a gitlink row `vendored` (mode `160000`, type `commit`) added under the manifest path, and that path's row recomputed to `4fdabda2…`, so the manifest `tree_sha` is the stale tree | 2 | `refused`: the upstream row `vendored`, mode `160000`, type `commit` |

Each output's `runs` lists the argument vector of every command it ran, with its exit code, byte
counts and stdout sha256. Every command exited 0 and wrote 0 bytes to stderr. The home directory is
written as `~` and the checkout as `<checkout>`.

## Result

From [`tree-drift-check.json`](tree-drift-check.json):

- `gh api 'repos/trailofbits/skills/git/trees/0cc1c73a5e96749ab32d7ea5e14892fafa6972ae?recursive=1'`
  returned `truncated: false`. The manifest path
  `plugins/supply-chain-risk-auditor/skills/supply-chain-risk-auditor` is tree
  `954cc68e05e24a2a14447b60d1e8946b53323b1b`. Its 16 rows are 13 blobs, all mode `100644`, and 3
  subtrees: `agents` `c1d1a4ab…`, `assets` `b1735ba7…` and `scripts` `eaedb5d0…`. Hashed in memory,
  the 13 blob rows reproduce the folder row and all three subtree rows (`upstream.self_check`).
- The scan of `~/.agents/skills/supply-chain-risk-auditor` left out the directories
  `scripts/.venv` and `scripts/__pycache__` and refused nothing. The folder holds the same 13
  paths as upstream, with no extra or missing file and no mode change. 12 blobs match.
  `scripts/uv.lock` differs: `ab864a16ac3b38bf469205ee65831b6737b4c867` on disk,
  `2fb44882a94a99013d613493e38bb372dfbbdd84` upstream. The local rows hash to
  `ec3f7c42f2a5d57c33c70f66c380b5c3abb445b2`, with `scripts/` at
  `3a48432338d4c46a482e05a768c9340145b73421`. That equals `skills_status.git_tree_sha` of the
  folder with runtime artifacts left out.
- The upstream `scripts/uv.lock` blob (337 bytes, fetched with
  `gh api repos/trailofbits/skills/git/blobs/2fb44882a94a99013d613493e38bb372dfbbdd84`) hashes to
  its own SHA. Substituted in memory, it gives `scripts/` `eaedb5d0840e7b155657478dd547e66abec537d1`
  and a folder tree of `954cc68e05e24a2a14447b60d1e8946b53323b1b`. That equals both the manifest
  `tree_sha` and the upstream folder row, and all three subtrees equal their upstream rows.
- The installed `SKILL.md` sha256 and the lock entry both read `ok`, and `folder_tree` reads
  `drift`. `tools/adoption/install_skills.py` therefore classifies the skill as `ok` and does not
  reinstall it (`classify_skill`, L117-135).

This matches the 2026-09-26 per-blob check
(`evidence/artifacts/skills-agents-layer-20260926/delta.json`, `host_observations.supply_chain_risk_auditor_drift`).

## Re-check

The allowed difference set is `{scripts/uv.lock}`. The check runs at the 2026-10-25 review on each
trial host, and before any reinstall or re-pin of this skill. A `drift` state from
`skills_status.py` does not trigger it on its own, because every use of the skill recreates that
state.

- Exit 0, `pass`: nothing is refused, every difference is in the set, and the substituted tree
  equals both the manifest `tree_sha` and the upstream folder row.
- Exit 1, `fail`: some other path differs, is missing or is extra, or the substituted tree differs
  from either. This reopens the reinstall path in the addendum.
- Exit 2, `refused`: an installed entry that is not a directory or a regular file, or is named
  `.git`, or an upstream row that is not a `100644` or `100755` blob or a tree. A refused installed
  entry lies outside the pinned tree, so it takes the exit-1 path.
- Exit 2, `error`: a truncated listing, no upstream or local blob, a failed self-check, or an input
  or command error.
- Exit 2 is never read as a pass. Any exit 2 other than a refused installed entry is resolved and
  the check re-run.

## Evidence class

- The `gh api` reads of the pinned tree and blob are native-measurement: the acceptance-evidence
  policy's "upstream example or native operation", with the actual returned output hashed in each
  file.
- The scan, the per-blob comparison, the in-memory substitution and the two self-checks are
  our-integration, the policy's "local integration check".
- The five controls are synthetic fixtures in the policy's sense, built by this repair round with
  `run_checks.sh`. Each fixture's expected result is a non-pass: exit 1 for the no-allowance and
  planted-blob controls, and exit 2 for the symlink, special-entry and upstream-gitlink controls.
  They are the discriminating runs for the passing one. The folder fixtures are altered copies of
  this host's installed folder. The gitlink listing is a rewritten response, not an upstream state.
- The results cover this host's folder at the time of the runs, not another host's.

## Erratum (2026-09-28)

[`tree_drift_check.py`](tree_drift_check.py) takes two more functions from `scripts/skills_status.py`
than the [Method](#method) section and each output's `method.functions` name: `resolve_lock_path` and
`load_lock` (`tree_drift_check.py` L284-285). They pick and read the global skills lock behind
`local.lock_entry_state`. The script keeps no copy of them: `load_checker` (L121-128) executes the
checkout's live `scripts/skills_status.py`, the same code an import runs. A re-run therefore uses the
`resolve_lock_path` that the checkout holds, and records that file's sha256 as `method.module_sha256`.

A later change joins that lock path as the skills 1.7.0 CLI joins it, with `path.join`
([`src/skill-lock.ts` L67-72](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/skill-lock.ts#L67-L72)),
which collapses a `..` lexically. From that change on, a re-run records a new `method.module_sha256` in
place of `adf89cd8…`. Its lock read, and so `local.lock_entry_state`, is the same as the recorded code's
unless a `..` in the variable the lock path uses (`XDG_STATE_HOME` when set, else `HOME`) follows a
missing folder or a symlink. After an existing real directory, a `..` names the same file either way, and
`HOME` does not reach the lock while `XDG_STATE_HOME` is set. In the remaining case the re-run reads the
lock where the CLI wrote it, while the script's own default folder (`~/.agents/skills/<skill>`, which it
joins with `pathlib` at L252) keeps the `..`. The folders in `skills_status.py`'s own report are joined as
the CLI joins them, but the script does not read that report. The script and its six outputs are
unchanged.
