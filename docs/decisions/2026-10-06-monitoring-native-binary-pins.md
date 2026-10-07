# Monitoring binary pins, 2026-10-06

The command center assigned mcp-grafana 2.0.1 and AgentsView 0.44.0 as the
operational pins for monitoring the north-star R&D foundation (item190639Z).
The alternatives are retaining the older operational metadata or using the
maintainers' supported release artifacts. The selected artifacts follow the
explicit version direction and the observed runtime compatibility.

Grafana's official archive passed both its published checksum check and the
independently pinned SHA256 check before extraction. Version2.0.1 and the owned
binary link read back at2026-10-06T19:31:44Z. This install ran ahead of the pin PR.
It establishes binary placement, not a real Grafana MCP client call. The new
template is CC-only; the user-scope template is unchanged. The future native
list_datasources smoke remains UNRUN until the CC supplies its rendered config.
No promptfoo A/B or local remeasurement campaign gates these pins.

AgentsView's previously authorized native upgrade already runs0.44.0. The
portable plan and known-alias migration now follow that release. Frozen G5
labels and results at0.43.0 remain historical; this metadata update neither
reruns nor promotes them to0.44.0 upstream acceptance. The prior B2 observation
that CODE-MODE attribution remains incomplete also stands.

Sources: [Grafana v2.0.1 release](https://github.com/grafana/mcp-grafana/releases/tag/v2.0.1),
[binary installation at c8fe9032](https://github.com/grafana/mcp-grafana/blob/c8fe90320a03e213ee6ce0a033e7492f1082aca6/README.md#L731),
[read-only mode](https://github.com/grafana/mcp-grafana/blob/c8fe90320a03e213ee6ce0a033e7492f1082aca6/README.md#L426),
and [AgentsView supported installer at413a87f7](https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/scripts/install.sh#L142).
The archive/read-back receipt is
[receipt.json](../../evidence/artifacts/monitoring-binary-pins-20261006/receipt.json).
Release assets list no downloadable signature or attestation; the artifact
attestation lookup returned404, so no broader absence or verification is claimed.

Three local integration attempts before the paper window exited 1. The last
remaining failure was the generated catalog join for the new component. The
maintained `scripts/catalog_decisions.py --write` render exited 0 under A58's
explicit light-render exception. The draft publishes with remote CI; the
post-render tests remain pending until the paper window ends at
2026-10-07T00:10Z. J807c separately authorized the light validator now; it exited
0 after the profile-membership and receipt-projection repair (70 components,
10360 hashed files, 4 profiles, 215 receipts). This render and integrity check
are not a native acceptance pass.

Remote native-token CI on 5257647d ran 52 tests and failed two fixture controls.
The operational manifest selected 0.44.0 while `scripts/native_token_ci.py`
still required 0.43.0, so its manifest preflight stopped before either injected
failure reached the fixtures. Aligning that harness pin to the verified release
keeps every existing assertion and fixture intact. The failed run remains in the
receipt; its new-head remote retry is pending.

An upstream release regression, a changed supported interface, or a failed
native client smoke overturns the affected operational pin. Owner decisions
and prior evidence remain distinct from that future observation.

## Post-render integration addendum, 2026-10-07

J807's P2/P3 fixes already exist in head d406cc8c: the PR is shared, its two
trading-path files are maintained regeneration only, and the vendor release
pages/checksum-document URLs and document hashes are recorded. Its actual
source merge-base is b4e1fa6df6048436e3f756965de38d9507dd5722.

The first post-render106-test retry failed on missing current-role coverage for
the selected Grafana MCP component. The second failed on current selection
projection coverage. Both attempts remain failed in the receipt. A dated
source-review candidate now explains the CC-only read-only interface using
the pinned vendor documentation above; no recorded layer winner or verdict
was changed. A selection-only addendum projects the current two pins and
retains the exact previous AgentsView selection. All historical API checks,
release/source observations, dates, summaries and public-star metadata remain
unchanged; the new MCP row declares zero API checks and no native observation.

The maintained catalog renderer regenerated typed references. The final four
touched modules ran201 tests in10.156s with3existing skips, exit0. This is local
integration, not an upstream suite or live MCP/profile qualification. The
original pending states and failed outputs remain dated predecessor evidence.

The integrity validator then exposed a stale limitations projection for this
receipt. Synchronizing that one owned registry entry with the receipt fixed it;
the retry exited0. No parallel registry history was merged.

## J807b rebase addendum, 2026-10-07

The branch rebased from dcec14e6 onto current main
79619936926576576e5d011eec19e3790e55f457. Main's Worktrunk recipe and added
observability limitations remain intact. Main's evidence registry was taken
unchanged, then this PR's own receipt/files were re-registered; every existing
receipt and convergence record remains exactly equal. The maintained catalog,
component-matrix and grand-list renders exited0. The four touched modules ran
245tests in27.633s,3existing skips, exit0; check_plan.py also exited0. These are
local integration observations, not host or upstream acceptance. Stack pins,
the regenerated trading files and the evidence registry are committed last.
The earlier base, results and failed attempts remain dated predecessor records.

The first rebased integrity check failed on the two regenerated trading-file
digests. The maintained catalog renderer writes those files without registering
them; explicitly registering both files fixes that metadata gap. Its failed
attempt is retained rather than replaced.
