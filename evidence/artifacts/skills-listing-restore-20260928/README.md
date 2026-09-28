# supply-chain-risk-auditor tree check, 2026-09-28

This is the retained tree-drift proof for the
[host listing drift addendum](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md#addendum-2026-09-28-host-listing-drift-restored).
The listing restore itself is recorded in the receipt
[`skills-listing-restore-20260928`](../../receipts/skills-listing-restore-20260928.json).
All runs were on host `nativestack-5975wx-20260925` on 2026-09-28, from the root of a checkout at
`3058b237`, with `TMPDIR=/var/tmp`, gh 2.101.0 and Python 3.13.15.

`scripts/skills_status.py` reports this folder only as `folder_tree` `drift`. That state is
informational, and every use of the skill brings it back. [`tree_drift_check.py`](tree_drift_check.py)
names each differing blob and fails on any difference outside an explicit `--allow` set. It
imports `git_tree_sha`, `_git_blob_sha`, `RUNTIME_ARTIFACT_DIRS`, `check_folder_tree`,
`check_canonical` and `check_lock_entry` from the checkout's `scripts/skills_status.py` (sha256
`adf89cd8…`, recorded in each output) instead of re-implementing them.

## Runs

| Output | Exact argv | Exit | Result |
| --- | --- | --- | --- |
| [`tree-drift-check.json`](tree-drift-check.json) | `python3 evidence/artifacts/skills-listing-restore-20260928/tree_drift_check.py --checkout . --skill supply-chain-risk-auditor --allow scripts/uv.lock` | 0 | pass |
| [`control-no-allowance.json`](control-no-allowance.json) | the same without `--allow` | 1 | fail: `scripts/uv.lock` is outside the empty allowed set, and the unsubstituted tree `ec3f7c42…` is not the pin |
| [`control-planted-blob.json`](control-planted-blob.json) | the first argv plus `--folder /var/tmp/tdc-planted.uxLxAa/supply-chain-risk-auditor`, a `cp -a` copy of the installed folder with one newline appended to `scripts/model.py`; the copy was removed after the run | 1 | fail: `scripts/model.py` is outside the allowed set, and the substituted tree `4b371703…` is not the pin |

Each output also records its own `gh api` argument vectors with their exit codes, byte counts and
stdout sha256. Every `gh api` call exited 0, and every run wrote nothing to stderr. The home
directory is written as `~` in every file.

## Result

- `gh api 'repos/trailofbits/skills/git/trees/0cc1c73a5e96749ab32d7ea5e14892fafa6972ae?recursive=1'`
  returned `truncated: false`. The manifest path
  `plugins/supply-chain-risk-auditor/skills/supply-chain-risk-auditor` is tree `954cc68e05e24a2a14447b60d1e8946b53323b1b`,
  with 13 blobs, all mode `100644`, and 3 subtrees: `agents` `c1d1a4ab…`, `assets` `b1735ba7…` and
  `scripts` `eaedb5d0…`.
- The installed folder `~/.agents/skills/supply-chain-risk-auditor` holds the same 13 paths once
  `scripts/.venv/` and `scripts/__pycache__/` are left out. There is no extra or missing file and
  no mode change. 12 blobs match. `scripts/uv.lock` differs: `ab864a16ac3b38bf469205ee65831b6737b4c867`
  on disk, `2fb44882a94a99013d613493e38bb372dfbbdd84` upstream. Without runtime artifacts the
  folder hashes to `ec3f7c42f2a5d57c33c70f66c380b5c3abb445b2`, and `scripts/` to `3a48432338d4c46a482e05a768c9340145b73421`.
- The upstream `scripts/uv.lock` blob (337 bytes, fetched with `gh api repos/trailofbits/skills/git/blobs/2fb44882a94a99013d613493e38bb372dfbbdd84`)
  hashes to its own SHA. Written into a copy of the folder, it gives `scripts/` `eaedb5d0840e7b155657478dd547e66abec537d1`
  and a folder tree of `954cc68e05e24a2a14447b60d1e8946b53323b1b`. That equals the manifest
  `tree_sha` and the upstream row, and all three subtrees equal their upstream rows.
- The installed `SKILL.md` sha256 and the lock entry both read `ok`. `tools/adoption/install_skills.py`
  therefore classifies the skill as `ok` and does not reinstall it (`classify_skill`, L117-135).

This matches the 2026-09-26 per-blob check
(`evidence/artifacts/skills-agents-layer-20260926/delta.json`, `host_observations.supply_chain_risk_auditor_drift`).

## Re-check

The allowed difference set is `{scripts/uv.lock}`. The check runs at the 2026-10-25 review on each
trial host, and before any reinstall or re-pin of this skill. A `drift` state from
`skills_status.py` does not trigger it on its own, because every use of the skill recreates that
state.

- Exit 0: every difference is in the set, and the substituted tree equals the manifest `tree_sha`.
- Exit 1: some other path differs, is missing or is extra, or the tree does not match. This
  reopens the reinstall path in the addendum.
- Exit 2: an error, a truncated listing, no upstream blob under the path or no local blob. This
  is never read as a pass.

## Evidence class

- The `gh api` reads of the pinned tree and blob are native-measurement: the acceptance-evidence
  policy's "upstream example or native operation", with the actual returned output hashed in
  each file.
- The per-blob comparison and the substitution are our-integration, the policy's "local
  integration check". Their two failing controls above are the discriminating runs for the
  passing one.
- The results cover this host's folder at the time of the runs, not another host's.
