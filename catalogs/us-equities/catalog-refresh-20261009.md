# Trading catalog scope reconciliation — October 9, 2026

The selected NativeStack2604 runtime uses **EdgarTools 5.61.1 / skfolio 1.7.0**
on lock **`f451ef979cdb1ae3686a30df1c883c257402b32753478c1f9c686c057e9c3989`**.
The isolated SEC recipe remains **5.60.0** and the frozen chronological study
remains **1.2.9**. These scopes coexist; replacing their pins would relabel
historical execution without establishing acceptance at the replacement version.
The [structured supplement](catalog-refresh-20261009.json) records the full
maintainer pins, primary fetch times, source hashes, current decisions and limits.
Register it with the repository's native decision tool:

```sh
python3 scripts/catalog_decisions.py --write --supplement catalogs/us-equities/catalog-refresh-20261009.json#/entries
```

This T19 unit serves the north star's reproducible historical research and
simulation by making source, installation and acceptance scopes unambiguous.
It reviews source and retained evidence. It installs nothing, acquires no SEC or
market data, runs no model, and changes no strategy, broker or paper gate.

## Runtime and accepted recipe scopes

| Record | Version / identity | What the evidence establishes |
| --- | --- | --- |
| Current published runtime | EdgarTools 5.61.1 at `7338aa335f6442c52dfa0695422cf1cd27e946e0`; skfolio 1.7.0 at `8a399757200d46b1ac1bff1b3daa71d9f0fa4170` | Published lock/package metadata; retained October 8 installed observation and separate offline integration acceptance |
| Isolated SEC recipe | EdgarTools 5.60.0 at `1e7a61b3a142dbf5d19bc82444f85239c1786348` | October 4 bounded SEC index request and local parser acceptance, with historical availability still separate |
| Initial filing wave | EdgarTools 5.58.0 at `abe44344c56cf4bfb5443e0debca7e39342f6e7a` | Dated fixture/initial execution receipts, including their failures and limits |
| Frozen chronological study | skfolio 1.2.9 at `c99fcf71349e2df4a7a1033ee85ca2e9ced9abee` | Historical WalkForward/control study only; no portfolio-optimizer acceptance |
| Newly discovered skfolio releases | 1.7.1 at `6aa7cf38cf99799d383e3544f839c3ca4cf14a15`; 1.8.0 at `33923e050083eb82c5996a16e3293343baa16689` | Currency/source review only; neither was installed or accepted by T19 |

The component cards in `manifests/stack.json` retain their accepted isolated
recipe/study pins. Current deployed-bundle metadata is maintained in
[runtime-target.json](runtime-target.json) and the [runtime recipe](../../blueprints/us-equities/runtime-2604/README.md).
The published runtime manifest hash is
`aa370e42e29dc2419e586358254ff2e821df48a693aa9a3ee16b65d30036ee0b`.
The two isolated lock hashes are recorded separately in the supplement.

The [final-lock acceptance receipt](../../evidence/receipts/runtime-final-native-24-acceptance-20261008.json)
records **2026-10-08 17:48:39Z–17:49:09Z, 24/24 PASS, rc 0**. Its returned stdout
printed the actual full `f451…` lock hash immediately before and after that run.
Its evidence class is **`local_integration`**, with an independent run-binding
critic retained by the original receipt. T19 reuses that evidence; it does not
describe it as a new host run or an upstream test-suite pass.

The earlier **06:20:48Z–06:21:25Z** run keeps receipt-reported `1fb9f8ca…`;
the **13:45:33.120Z–13:45:58.886Z** run keeps writer-reported `17221888…`.
Neither printed a lock in its acceptance stdout. The **14:09:06Z** `--inexact`
dependency verification and **15:29:03.791496Z** installed-metadata observation
remain separate from acceptance. A hash-only substitution into an older receipt
would create a false execution binding.

Prospective **28-case/dev-probe acceptance**, exact legacy migration, Layer 1.5
historical E2E, point-in-time information availability, portfolio/risk acceptance
and strategy/broker gates remain separate. skfolio 1.7.1's weighted-risk/VaR/NaN
fixes and October 9's 1.8.0 sample-weight extension feed the next currency sweep;
the selected 1.7.0 smoke did not qualify those algorithms.

## Current adoption dispositions

| Candidate | Current scope | Preserved history and overturn condition |
| --- | --- | --- |
| DVC 3.67.1 | **Held; absent from selected runtime** after October 5 dependency-security removal | September provisional source-review winner and September 23 fixture remain historical. Rejudge safe dependency closure and the full equity snapshot contract before adoption. No replacement is selected. |
| vectorbt public | **Excluded from current north-star adoption** under the owner-routed GRAND licence rejection | Historical optional research and destination-engine decisions keep their distinct scope. Reconsider only under an explicit owner adoption disposition and a native comparison for a demonstrated research need. |
| atilaahmettaner/tradingview-mcp | **Reject automated/non-display north-star data use** | September unqualified/proposal/do-not-wire verdicts remain dated. Entitled source-data permission and a separately accepted as-of contract would be needed to reconsider. |
| tradesdontlie/tradingview-mcp | **Same scoped ToS rejection; separate repository identity** | Historical Desktop-CDP alternative remains dated. MIT source-code permission does not supply provider-data permission. |

DVC's [removal evidence](../../evidence/artifacts/trading-runtime-2604-20261004/diskcache-removal-20261005.json)
records the diskcache advisory and runtime dependency removal. The current lock
contains neither DVC nor diskcache. This refresh does not conduct a new advisory
audit or lift the hold. The [September 23 four-store comparison](../../evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/4-four-store-comparison.json)
did execute `dvc checkout` restoration and correction retention. That real
`local_integration` fixture used five observations/two universe rows and did not
execute the full specified layer overturn comparison. “DVC never executed”
would erase valid, limited historical evidence. The sealed September layer
winner and its source fields remain intact, with their actual review date.
The current `data-dvc` card and registered supplement explicitly hold adoption;
they take precedence over the dated winner label for setup. The layer ledger's
`current_adoption_status` and `verdict_scope` make that distinction explicit.
This source refresh does not claim a new paired layer verdict.

vectorbt's [public licence at 1.1.2](https://github.com/polakowo/vectorbt/blob/f0d2afba7af8a6e6c1b02afde27c9a16413e86ff/LICENSE.md)
is Apache-2.0 with Commons Clause. Its bytes match the historical architecture
pin. That source fact is distinct from the owner's current adoption policy;
this record infers no universal legal prohibition on internal research.
The [current README](https://github.com/polakowo/vectorbt/blob/f0d2afba7af8a6e6c1b02afde27c9a16413e86ff/README.md#L68)
supports multi-asset analysis and the public `vectorbt[rust]` extra; its
[package metadata](https://github.com/polakowo/vectorbt/blob/f0d2afba7af8a6e6c1b02afde27c9a16413e86ff/pyproject.toml#L51)
pins `vectorbt-rust==1.1.2`. The already disputed single-asset/PRO-only Rust
arguments remain incorrect. Private PRO source and licence acceptance were
not examined. Version 1.1.2 is fresh source review, not an upgraded installation.

[TradingView Terms of Use §3](https://www.tradingview.com/policies/#terms-of-use)
licenses its content/data for **“exclusive display-only use”** and prohibits
automated trading, algorithmic decision-making and machine-driven non-display
processes. The official page returned HTTP 200 at **2026-10-09T19:36:28.520518Z**;
the exact response hash/length is recorded in the supplement. The current
[atila source](https://github.com/atilaahmettaner/tradingview-mcp/blob/b04513ece51dd21a60b0a1e05964aee5957b7a69/pyproject.toml)
still declares the unofficial TradingView screener/TA dependencies. A no-login
README claim does not grant provider-data rights. The
[distinct Desktop bridge LICENSE](https://github.com/tradesdontlie/tradingview-mcp/blob/c05b8f5755ed8e64ea242de88ddbf46aa24d56a4/LICENSE)
exists and grants MIT source-code permission with an explicit exclusion of
TradingView software/data/IP rights. The historical null/NOASSERTION finding is
corrected. The owner-routed rejection is scoped to the north-star automated
data use; this evidence does not forbid every human-readable chart interaction.

## LEAN source and build identities

| Scope | Build / full source | Evidence boundary |
| --- | --- | --- |
| CC-declared protocol record | 18176 / `80e7843f645673bcbeaab963049f76f20f6785e1` | Dispatch identifies the protocol mapping; maintainer commit resolves. T19 did not reproduce that build association or execute the protocol engine. |
| Current local runtime recipe | 18149 / `33e3945f2faa95308d972dfd3d7b762f7743d1d5` | Install recipe records this mapping and image digest `sha256:70071d1bbb90385deb60c7d20bc3830c7f4c79f6c09c5d1ade9196c009f68861`; image inspect has no revision/version labels. Source-to-image reproduction remains open. |
| September source build/sample | `985ef30ad3ac774218c5ac516b4cb0aa2655730f` | Retained native source-build/sample execution, with its original date and inputs |

The [maintainer source at 80e7843f](https://github.com/QuantConnect/Lean/commit/80e7843f645673bcbeaab963049f76f20f6785e1),
[Dockerfile at 33e3945f](https://github.com/QuantConnect/Lean/blob/33e3945f2faa95308d972dfd3d7b762f7743d1d5/Dockerfile)
and [historical source](https://github.com/QuantConnect/Lean/commit/985ef30ad3ac774218c5ac516b4cb0aa2655730f)
resolve as distinct commits. GitHub status reads for the two newer commits
returned no statuses; those responses supply no missing build-provenance proof.
The [local runtime recipe](../../blueprints/us-equities/runtime-2604/README.md)
already keeps source-to-image reproducibility and retained-oracle parity open.
No version association relabels the historical execution or overrides the
selected NautilusTrader destination.

## GRAND views and dates

| View | Authority and refresh method |
| --- | --- |
| Current trading catalog / runtime target | Maintained current selections, registered decision supplements and scoped receipts |
| `docs/grand-catalog-handbook.md` / `layer-verdicts-20260922.json` | Frozen September 22 layer decisions; preserve the actual original dates |
| `catalogs/landscape/us-equities.json` | Current maintained ledger, with original verdict dates plus explicit October 9 correction scope |
| `docs/new-host-grand-list.md` / corresponding JSON | Derived host-setup projection from canonical ledgers, component matrix, pins and profiles; regenerate with `scripts/new_host_grand_list.py --write` |
| Offline ecosystem explorer | Generated, uncommitted view through `scripts/build_ecosystem.py --write`; inclusion is not installation or acceptance |

The two GRAND presentations are historical/derived views of the same canonical
records, not independent adoption decisions. No separate owner-authored GRAND
file was named in the scoped repository prose. This refresh does not rewrite
September 22 as October 9 for the whole landscape or claim new all-layer reads.

The independent critic also checked the generator's inherited pin/currency
fields. The new-host EdgarTools winner cards still carry **v5.58.0** as both
`pin` and `upstream_latest`, with `pin_behind_upstream=false`; skfolio's
`upstream_latest` remains the dated **v1.3.0** snapshot. These fields are not
October 9 currency and do not describe the **5.60.0** SEC recipe or
**5.61.1 / 1.7.0** runtime. Their `host_verified` labels retain the original
receipt scope; they do not establish a new host run at a replacement pin.
The generated DVC winner also belongs to that sealed September verdict and
does not lift the current dependency hold. Consult the current catalog card
and registered supplement before any prospective installation.
The current identities and latest discovered releases are explicit above and
in the supplement. Reconciliation of canonical pin/latest projections feeds
the next sweep; this unit changes no generator code or frozen verdict bytes.

## Anti-pattern corrections and next sweep

| Proven mistake | Correction and prevention | Verification |
| --- | --- | --- |
| Calling the earlier `1fb…` acceptance current, or updating only its hash | Link the separate same-stream `f451…` run; keep all original receipts/timestamps | Exact lock/manifest bytes and final receipt reproduce the full recorded hashes |
| Treating recipe pins as deployed-runtime disagreement | Name isolated SEC, frozen splitter and published-runtime scopes separately | Native lock bytes plus maintainer tags, package metadata and retained run records |
| Presenting held DVC as an installable winner, or claiming it never ran | Make the current hold explicit and preserve the dated paired winner and bounded `dvc checkout` fixture | Current lock has no DVC/diskcache; current supplement takes precedence over the dated label |
| Single-asset/PRO-only Rust claims used against vectorbt | Use current maintainer capabilities; attribute the current rejection to the owner adoption disposition | v1.1.2 README and `pyproject.toml`; historical correction remains dated |
| Inferring no licence from a missing response | Correct the Desktop bridge's pinned LICENSE classification without inferring data rights | Actual MIT text plus explicit TradingView rights exclusion at full c05b8f57 pin |
| Dropping the source-root prefix from a pinned locator | Correct the atila screener URL to `src/tradingview_mcp/core/services/screener_service.py` | The independent critic measured HTTP 404 for the shortened path and found the file in the maintainer tree at the same full pin |
| Collapsing TradingView names or treating MIT as data permission | Register both repositories; apply one scoped current ToS rejection | Separate full pins/README/LICENSE and official Terms §3 |
| Inferring LEAN source/image equivalence from version labels | Record declared associations and missing proof separately | Distinct maintainer commits, empty status responses and absent local revision labels |
| Treating a generated GRAND view or scoped refresh as a new selection/all-layer review | Keep canonical sources and original dates explicit | Native generator inputs and registered supplement source pointers |
| Editing frozen v2 verdict fields while retaining the September 22 lane binding | Withdraw direct v2 edits; record current source/adoption conditions separately. A paired-verdict change needs fresh sealed returns and a new native wave | `build_verdicts.py --check` verifies the intact frozen wave; the verdict gate rechecks the final change |
| Using the catalog's `excluded` value in the landscape's narrower enum | Use native `out_of_scope` for current candidate source/adoption scope while preserving frozen alternative fields | The supported packet schema enumerates accepted dispositions; native landscape validation passes |

The completeness check surfaced both TradingView identities and same-day releases
of vectorbt 1.1.2 and skfolio 1.8.0. Their source review resolves currency and
capability facts; it establishes no native adoption. The next sweep should
rejudge DVC's safe dependency closure and full snapshot contract, and test the
skfolio fixes through upstream acceptance for the intended risk/portfolio use.
LEAN build provenance/parity and prospective runtime checks remain distinct
acceptance units. The inherited new-host pin/latest projections also feed that
sweep without being relabeled as current. The
[T19 review receipt](../../evidence/artifacts/t19-catalog-refresh-20261009/review-receipt.json)
records native catalog checks, prepublication FULL validation and the independent
completeness review. A final FULL check follows registration of the receipt before
commit; its returned result is retained in the PR and lane handoff.

The separate native verdict gate checks the frozen wave as well as landscape
schema validity. CI exposed invalid direct edits to the two September v2 rows;
those edits were withdrawn. Current adoption conditions are registered source
decisions, while the paired winner/alternative fields keep their original family
provenance. A future paired-verdict re-record uses fresh sealed family returns
and a new native wave; no such run is claimed here. The CC reads this source
refresh and lands the draft after #926. FULL artifact validation and the native
verdict gate are recorded separately.
