# Readiness evidence binding across landings

Date: 2026-10-09 UTC. Status: recommendation for CC decision ([C], lines 32–36).
Recommendation: **less-volatile-binding**. This record authorizes no builder,
workflow, ruleset, publication or landing change.

## Decision and inverse

Recommend binding readiness to the evidence registrations and artifact digests
that its claims actually consume, rather than the bytes of the entire shared
evidence index. Keep exact digests of the selected artifacts, the source
specification and all other claim inputs. Define and version the selected
registration representation before implementation; merely omitting
`/receipts/evidence/sha256` and `bytes` would discard provenance. The existing
builder already resolves supporting receipts by ID, path and declared digest
([B], lines 183–228). The reference shape for consumed inputs is SLSA Build
Provenance v1.2 `buildDefinition.resolvedDependencies`: an unordered collection
of artifacts needed at build time, represented by ResourceDescriptors with
digest fields ([P]). In this build model, in-toto Statement v1 `subject` names
the readiness output, rather than its consumed inputs ([I], [P]). The proposed
scoped registration binding remains a local design, not an
upstream feature or a claim of signed-attestation compliance.

The inverse is to retain the exact whole-index binding and accept a bounded
refresh after each index-changing landing. That preserves proof of which
complete index snapshot was read, including registrations outside readiness's
selected inputs. Prefer this inverse if whole-index identity is an owner
requirement, or if a scoped representation cannot detect every relevant change,
removal, ambiguity and digest mismatch. It requires an explicitly accepted
stale interval and a refresh owner; those decisions have not been made here.

An implementation would overturn this recommendation if replay shows that an
unrelated registration changes a scoped build, or that a relevant registration
or artifact change leaves it unchanged. No prototype or scoped-binding replay
was run for this record. Genuine input changes must still invalidate readiness;
this recommendation concerns unrelated index churn.

## Reproduced evidence

At repository pin `ebe6c223f65bf20d04c56858e8669e0bd76ef3aa`, sources.json
declares `manifests/evidence.json` ([S], line 6). `Receipts.get` hashes its raw
bytes ([B], lines 71–105); `build` exports all declared source records
(lines 340–343); `--check` compares the complete rendered output with the
committed output and returns 1 on a difference (lines 497–506).

The last ten first-parent landings ending at that pin span 2026-10-08 19:39:06Z
to 2026-10-09 02:05:23Z. Six changed the index; eight resulting trees had a
whole-index digest mismatch. These are direct Git-blob measurements, **not**
eight observed CI failures or a full builder replay with host-state receipts.

| Landing | Commit prefix | Index changed from parent | Committed index binding matches |
| --- | --- | --- | --- |
| #883 | af7a4fe65 | no | no |
| #880 | 586a31e38 | yes | no |
| #877 | c9ab22121 | yes | no |
| #881 | e48de2e6f | yes | no |
| #888 | 9f7b38b23 | no | no |
| #889 | aba02ec34 | yes | no |
| #890 | 72e1f943d | no | yes |
| #900 | 36e36ea49 | yes | no |
| #897 | 2489b8481 | yes | no |
| #907 | ebe6c223f | no | yes |

The retained landing reports corroborate two repair cycles ([L]): #890's
candidate bound `55c2977680bd041bf2b62a9e33d227469760341427e6aa7dd3f000db50bc9063`,
while #889 had advanced main to
`d07bbce85f1f4f3eee404771a80e3b79e2333ea50de49c90e56f855babb43b98`.
After rebase and regeneration, #890 matched. #900 and #897 then advanced the
index to `211df213899a2284dba589155094995bd1508ed01f84547b7213b8dc86145762`;
#907 was rebased and regenerated to match that snapshot. Its landed tree
matches this digest. The reports separate this two-field index delta from
unavailable host-state receipts on the other validation host.

Reproduce the table from immutable Git objects, without reading local receipts:

```python
import hashlib, json, subprocess
pin = "ebe6c223f65bf20d04c56858e8669e0bd76ef3aa"
def git(*args):
    return subprocess.check_output(["git", *args])
commits = git("log", "--first-parent", "-10", "--format=%H", pin).decode().split()
for commit in reversed(commits):
    path = "manifests/evidence.json"
    changed = git("rev-parse", f"{commit}^:{path}") != git("rev-parse", f"{commit}:{path}")
    actual = hashlib.sha256(git("show", f"{commit}:{path}")).hexdigest()
    readiness = json.loads(git("show", f"{commit}:catalogs/north-star/readiness.json"))
    print(commit, changed, readiness["receipts"]["evidence"]["sha256"] == actual)
```

## Options from primary sources

| Option | Supported behavior and evidence | Trade-off for this binding |
| --- | --- | --- |
| GitHub merge queue | GitHub combines the latest base and preceding queued PRs into a temporary merge group and requires the applicable required checks to pass ([G]). Actions requires the separate `merge_group` trigger; its `GITHUB_SHA` is the merge-group SHA ([A]). | Checks the combined candidate. The reviewed GitHub documentation does not establish regeneration of committed readiness bytes; repair is a separate concern. A digest mismatch still fails this builder. Furthermore, the current public repository's owner has API type `User` ([R]); documented queue availability covers organization-owned repositories ([G]), so queue is unavailable under the documented current ownership. Adopting it would require separate owner and workflow decisions. |
| Less volatile binding | The builder selects registered supporting receipts and verifies their declared artifact digests ([B], lines 183–228). SLSA Build Provenance v1.2 `buildDefinition.resolvedDependencies` supplies the reference shape for consumed inputs as ResourceDescriptors with digest fields ([P]). | Targets the dependency causing unrelated churn while retaining artifact-byte integrity. Gives up exact identity of the complete aggregate index; selector completeness and deterministic representation need implementation evidence. Recommended direction, not an implemented solution. |
| Accepted post-landing refresh | The installed builder supports `--write` followed by `--check` ([B], lines 483–506), on a host with its named retained receipts (lines 307–332). | Repairs the current whole-index binding without changing its semantics, but the next index-changing landing can stale it again. It cannot satisfy an already failing pre-landing check retroactively. A finite stale interval, refresh ordering, designated reads and explicit acceptance must be specified before adopting it. |

The current whole-index contract has no hosted check of the committed readiness
manifest. No workflow invokes `build_readiness.py --check`, `scripts/validate.py`
does not run it, and the readiness tests run their drift check on a temporary
root ([E], fixture lines 155–162 and check lines 336–354). Enforcement of this
binding currently depends on a lane running `--check` locally against committed
readiness. Main's committed readiness was stale after 8 of the 10 sampled
landings, with no hosted failure for that stale binding; pages reading the
committed manifest retain it until the next refresh. Required landing checks
therefore do not protect this binding. The source reports for #890/#907
demonstrate rebase and regeneration before landing. Queue enablement, scoped
binding, scheduled refresh and acceptance of post-landing staleness remain
unexecuted alternatives pending a separate implementation cue.

## SOTA sources

- [B] [seathatflowsinourveins/native-agent-stack builder at ebe6c223f65bf20d04c56858e8669e0bd76ef3aa](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ebe6c223f65bf20d04c56858e8669e0bd76ef3aa/tools/north-star/build_readiness.py): raw source binding, selected supporting receipts, exported provenance and supported `--write`/`--check` interface. Graph coverage excludes `tools/`; cited source ranges were read directly.
- [S] [Source declarations at the same pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ebe6c223f65bf20d04c56858e8669e0bd76ef3aa/tools/north-star/sources.json#L6).
- [C] [Command-center decision authority at the same pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ebe6c223f65bf20d04c56858e8669e0bd76ef3aa/docs/command-center.md#L26): reserved acts at lines 26–30; evidence-settled decisions inside CC authority at lines 32–36.
- [G] [GitHub Docs: Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue), fetched 2026-10-09 UTC: “Who can use this feature?”, “How merge queues work”, “Triggering merge group checks with GitHub Actions” and “Failing CI”.
- [A] [GitHub Docs: `merge_group` event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#merge_group), fetched 2026-10-09 UTC.
- [P] [SLSA Build Provenance v1.2](https://slsa.dev/spec/v1.2/build-provenance#builddefinition), Approved specification, fetched 2026-10-09 UTC: `buildDefinition.resolvedDependencies` is an unordered collection of artifacts needed at build time, represented by ResourceDescriptors with digest fields. This is the reference shape for consumed inputs; it does not ship this repository's scoped index adapter.
- [I] [in-toto/attestation Statement v1 at fd2609c16bcb0ac53443e2b4612977f997e8f9a5](https://github.com/in-toto/attestation/blob/fd2609c16bcb0ac53443e2b4612977f997e8f9a5/spec/v1/statement.md), `subject` requirements, fetched 2026-10-09 UTC. This identifies the attestation's subject artifacts and their digests; in the SLSA build model those are outputs ([P]).
- [E] [Hosted workflows at ebe6c223](https://github.com/seathatflowsinourveins/native-agent-stack/tree/ebe6c223f65bf20d04c56858e8669e0bd76ef3aa/.github/workflows), [validation script at that pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ebe6c223f65bf20d04c56858e8669e0bd76ef3aa/scripts/validate.py) and [readiness tests at that pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ebe6c223f65bf20d04c56858e8669e0bd76ef3aa/tests/test_north_star_readiness.py#L155), inspected 2026-10-09 UTC: no workflow or validation-script invocation of the committed readiness check; the tested drift check at lines 336–354 uses the temporary fixture at lines 155–162. Graph coverage excludes `scripts/`; the validation source was searched directly.
- [R] GitHub REST repository metadata, queried 2026-10-09 UTC with `gh api repos/seathatflowsinourveins/native-agent-stack --jq '{owner_type:.owner.type,visibility:.visibility,default_branch:.default_branch}'`: `User`, `public`, `main`. Ownership metadata plus [G] establishes the documented availability boundary; no ruleset was modified or queue executed.
- [L] Local coordination ledger `coordination/command-center/ledger.jsonl`, retained report IDs `report-native-agent-stack-5f-20261008T2354-890-held`, `report-ns2604-coop-20261009T001735Z`, `report-native-agent-stack-5f-20261009T011356-landed-890` and `report-ns2604-coop-20261009T020327Z`. Historical reported executions are attributed to those reports; the Git-blob measurements above were independently reproduced for this record.

Evidence classes: Git history and repository metadata were measured locally;
builder/specification/queue behavior is source review; previous builder runs
are retained historical reports. No new queue execution, scoped build, refresh,
host acceptance or improvement benchmark is claimed.
