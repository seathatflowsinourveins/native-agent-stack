# NautilusTrader declares no equity adjustment handling for Layer 1.5

Date: 2026-10-10. Status: proposed correction to the trading rules; co-op GPT read and CC micro required.

`blueprints/us-equities/AGENTS.md` listed "NautilusTrader's data catalog and adjustment handling" among the Layer 1.5 candidates (line 44 at `fcdeae42c82b2279ccd5a0ee3867fd70ba1beff2`). That reads as if the selected engine already adjusts equity prices for splits and dividends, which is the gap Layer 1.5 exists to close. The selected release is NautilusTrader 2.0.0rc5 (`catalogs/us-equities/runtime-target.json:9`, `:32`). This record checks the claim against the upstream releases, rc5 and the later rc6, and corrects the sentence. Evidence class: `source_review` of the upstream sources, plus a local read of the released artifacts.

## What the two releases declare

Three independent reads of the same two releases agree: no equity corporate-action or price-adjustment type exists in either.

### 1. The public stubs of the wheels

The CPython 3.12 manylinux wheels of both releases were downloaded and checked against the sha256 that PyPI publishes for each file. Every `.py`, `.pyi`, `.pyx` and `.pxd` member (95 in each wheel) was then read for declarations (`class`, `def`, `cdef class`, assignments and enum lines) matching `adjust`, `dividend`, `corporate action`, `stock split`, `reverse split`, a split-factor pattern or `ex-date`. The script is at the end of this record.

| Release | Wheel | Bytes | sha256 | Wheel uploaded | Tag commit in `nautechsystems/nautilus_trader` |
| --- | --- | ---: | --- | --- | --- |
| 2.0.0rc5 | `nautilus_trader-2.0.0rc5-cp312-cp312-manylinux_2_34_x86_64.whl` | 69,963,442 | `eab45fafd2312deda1236554c49a9798bfc76bc8465af864878e2f70189ebebe` | 2026-09-15T06:08:05Z | `v2.0.0rc5` = `1b0a49d2792a9432a3aca3fcb617ce7a630d905e` (2026-09-15T02:13:21Z) |
| 2.0.0rc6 | `nautilus_trader-2.0.0rc6-cp312-cp312-manylinux_2_34_x86_64.whl` | 69,828,675 | `9b4002a7bf5e6399c51073039b740ccf3ca7a1e2584ff72c7d479f03eaa9658d` | 2026-10-05T02:57:21Z | `v2.0.0rc6` = `7b766f8825b2539c5b2ac1375e9d97b41c509edb` (2026-10-04T22:24:44Z) |

Each time in the Wheel uploaded column is PyPI's per-file `upload_time_iso_8601` for the wheel in that row, cut to the second (rc5 06:08:05.461517Z, rc6 02:57:21.386880Z), and the source distributions of the two releases were uploaded later, at 2026-09-15T06:13:57Z (rc5) and 2026-10-05T02:59:49Z (rc6).

The rc5 tag commit is the one `catalogs/us-equities/runtime-target.json` records as `engine.source_commit` for the selected release, and the rc5 wheel's size, sha256 and upload time are the ones `blueprints/us-equities/runtime-2604/trading-2604-runtime/uv.lock` records for that file (its `wheels` row of the `nautilus-trader` package, `upload-time = "2026-09-15T06:08:05.461Z"`, currently line 1538), and the lock's `sdist` row gives `upload-time = "2026-09-15T06:13:57.781Z"` for the rc5 source distribution (currently line 1534); a test compares each with the record. That lock pins rc5 only, so the rc6 upload times have no second source in this repository, and the test checks only that each wheel time is earlier than its source distribution's.

Both scans return the same 13 declarations. Line numbers are in `nautilus_trader/model/__init__.pyi` unless another file is named.

| Declaration | rc5 line | rc6 line | What it is |
| --- | --- | --- | --- |
| `ContinuousFutureAdjustmentType` (enum) and its `from_str` | 7812, 7831 | 7770, 7789 | How a rolled futures series is adjusted: backward or forward spread, backward or forward ratio |
| `PositionAdjustmentType` (enum) and its `from_str` | 8141, 8154 | 8099, 8112 | Position adjustments for commission and funding |
| `PositionAdjusted` with `adjustments`, `apply_adjustment`, `adjustment_type` and `from_dict` | 5963; 5943, 5951, 5990, 6004 | 5871; 5851, 5859, 5898, 5912 | The event and methods that record those position adjustments |
| `AccountAdjustmentOutcome` in `nautilus_trader/backtest/__init__.pyi` | 38 | 38 | The result (`applied`, `error`) of an account adjustment in a backtest |
| `GreeksConvention.PRICE_ADJUSTED` | 7879 | 7837 | An options-greeks convention |
| `IbHistoricalWhatToShow.ADJUSTED_LAST` in `nautilus_trader/adapters/interactive_brokers/__init__.pyi` | 429 | 429 | One of the ten historical-data request types the adapter lists (`TRADES`, `MIDPOINT`, `BID`, `ASK`, `BID_ASK`, `HISTORICAL_VOLATILITY`, `OPTION_IMPLIED_VOLATILITY`, `FEE_RATE`, `SCHEDULE`, `ADJUSTED_LAST`). It names a series the broker serves; the stub declares no adjustment in NautilusTrader |
| `IbTickType.IB_DIVIDENDS` in the same file | 658 | 658 | An Interactive Brokers generic tick type |

No declaration is a split, dividend, corporate-action or ex-date type for equities.

### 2. The Rust source at the tag commits

The model enum stubs are generated from the Rust definitions (`pyo3_stub_gen::derive::gen_stub_pyclass_enum`, `enums.rs:615` to `:618` at rc5), so the definitions are the upstream source of the enum declarations above. In `crates/model/src/enums.rs`:

| Release | Blob | Bytes | `ContinuousFutureAdjustmentType` | `GreeksConvention` / `PriceAdjusted` | `PositionAdjustmentType` |
| --- | --- | ---: | --- | --- | --- |
| rc5 | `328ec262647dedbea3f56854987b5533070bd088` | 92,135 | line 619: `BackwardSpread`, `ForwardSpread`, `BackwardRatio`, `ForwardRatio` ("Additive adjustment, anchored on the most recent contract" and the three siblings) | 1144 / 1149 | line 1481: `Commission`, `Funding` |
| rc6 | `c06c00bcbd3fe3b0562607ad203b70c759312201` | 95,635 | line 665 | 1204 / 1209 | line 1541 |

Among the 5,645 (rc5) and 5,889 (rc6) tree entries at the tag commits, the only paths that mention adjust, dividend, corporate or split, outside `tests/` and `assets/`, are `crates/model/src/events/position/adjusted.rs` and its Python binding `crates/model/src/python/events/position/adjusted.rs`: the position adjustment event.

### 3. The documentation at the tag commits

Reading the Markdown under `docs/` (213 files at rc5, 214 at rc6) for corporate action, stock split, dividend, split adjustment, adjusted price, adjusted bar, reverse split and ex-dividend gives 20 lines in each release, and none of them describes a split or dividend adjustment of equity prices:

- Price adjustment is documented only for continuous futures: `docs/concepts/continuous_futures.md:4` and `:10` ("computes its cumulative price adjustment, and feeds the adjusted source data") and `docs/concepts/index.md:32` ("Splicing consecutive futures contracts into one adjusted bar series via an explicit roll").
- Dividends appear as an options-pricing input (`docs/concepts/greeks.md:279`, `:319`, `:320`) and as Bybit settlement record types (`docs/integrations/bybit.md:335` to `:340` at rc5, `:421` to `:426` at rc6). The other hits are venue order-price adjustments (`docs/concepts/execution/index.md`, `docs/integrations/deribit.md`), which concern orders, not data.
- The Databento adapter page says it directly (`docs/integrations/databento.md:105` to `:109` in both releases): "Databento also documents reference schemas, including corporate actions, adjustment factors, and security master data. This adapter maps only the schemas listed above to Nautilus data types."

## The data catalog

`ParquetDataCatalog` (`nautilus_trader/persistence/__init__.pyi:101` at rc5, `:146` at rc6) stores and queries market data: `write_quote_ticks`, `write_trade_ticks`, `write_order_book_deltas`, `write_bars`, `write_order_book_depths`, `write_mark_price_updates`, `write_index_price_updates`, `write_option_greeks`, `write_instruments`, `write_custom`, `instruments`, the consolidate and delete methods, and in rc6 also status and close writers, a legacy-path migration and Arrow queries. No method adjusts prices. The catalog stays a candidate for what it does, which is storage and query of retained bars.

## Limits of the claim

- It is an absence claim about what the two releases declare: the public stubs of the CPython 3.12 manylinux wheels, the model enums at the tag commits and the documentation. The compiled modules were not read, and a behavior with no declaration, no enum and no documentation would not show.
- It says nothing about how Interactive Brokers builds `ADJUSTED_LAST` or what a data vendor adjusts; the Interactive Brokers documentation was not read here.
- Only rc5 is the selected release. rc6 was read because it is the latest candidate and the claim should not rest on a release that is about to be replaced.

## Decision

The sentence names the data catalog for what it is, storage and query, states that rc5, the selected release, and rc6 declare no equity corporate-action or price-adjustment type, and points at this record. Equity adjustment stays open and is covered by the other candidates in the same sentence: EdgarTools' CIK and ticker maps, alpaca-py's corporate-actions endpoint, Lean's map and factor files and an available vendor feed. The paragraph's other rules are unchanged: build the glue from cited SOTA references, name each action's source, accept it only by a historical-data end-to-end backtest through the upstream engine, and cite no strategy number until that backtest passes.

What would overturn it: a later release, or the documentation of rc5, that declares an equity corporate-action or price-adjustment type, or a run that shows the engine adjusting equity bars. Re-run the script below on that release.

## Regression tests

In `tests/test_install_claude_profile.py::StandingRuleSurfacesTests`:

- `test_layer_15_candidates_do_not_claim_nautilus_adjustment_handling` pins the corrected paragraph by the facts it must state, in any wording. `layer_15_drift()` lists what is missing: the NautilusTrader data-catalog candidate is named; its parenthetical says that the selected release (the version `catalogs/us-equities/runtime-target.json` selects) and rc6 were checked; a negation precedes both "equity corporate-action" and "price-adjustment" inside that parenthetical; the dated record is pointed at; the candidate says nothing else about adjustment (the earlier phrase "adjustment handling" fails anywhere in the paragraph); and the other four candidates are still listed. It fails on the earlier text.
- `test_layer_15_guard_accepts_the_current_form_and_meaning_preserving_rewordings` and `test_layer_15_guard_rejects_the_old_claim_and_each_lost_fact` run `layer_15_drift()` on sample paragraphs, so a later rewording of the real file cannot break them: the rewordings pass, and the earlier claim, a removed or reversed negative clause (key terms kept), a clause that negates only one term, a missing pointer, a missing or swapped release, an adjustment claim in other words, a renamed catalog and each dropped candidate fail.
- `test_layer_15_record_pins_the_scanned_releases_and_the_declared_adjustment_types` fails if this record is absent or loses a wheel name, size, sha256, tag commit or declared type, or if the rc5 commit differs from the runtime target's `engine.source_commit`.
- `test_layer_15_record_wheel_upload_times_match_the_lock_and_precede_the_sdists` fails if the wheel table's Wheel uploaded column holds anything but the wheels' times: the rc5 row must equal, to the second, the upload-time, size and sha256 that the repository's `uv.lock` records for that wheel file name, the rc5 source distribution time the record states must be the lock's, and each wheel time must be earlier than the source distribution time the record states for its release. It would have caught the first version of this table, which carried the source distributions' times. The lock holds rc5 only, so the rc6 seconds are held by this record alone.

## Measured context cost

The file is loaded for trading work, so the cost is measured: `blueprints/us-equities/AGENTS.md` goes from 5,778 to 5,941 bytes (+163), all in the Layer 1.5 paragraph.

## The scan

```python
#!/usr/bin/env python3
"""List the adjustment-related declarations in the public stubs of two NautilusTrader wheels.

Usage: scan_nt_stubs.py WHEEL_RC5 WHEEL_RC6

Each wheel is checked against the sha256 that PyPI publishes for that file, then every .py, .pyi, .pyx
and .pxd member is read as text. A declaration line is a `class`, `def`, `cdef class` or assignment line
(or one that mentions Enum) whose text matches the pattern below. The scan reads declarations only. It does
not execute the wheel and it does not see the compiled modules, so an absence is a claim about the public
stub surface of the release, not about every internal crate.
"""
import hashlib
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

PATTERN = re.compile(r"(?i)(adjust|dividend|corporate.?action|stock.?split|reverse.?split|\bsplit(?:s)?\b.*factor|ex.?date)")
MEMBER_SUFFIXES = (".py", ".pyi", ".pyx", ".pxd")


def published_digests(version):
    with urllib.request.urlopen("https://pypi.org/pypi/nautilus-trader/json", timeout=60) as response:
        releases = json.load(response)["releases"]
    return {f["filename"]: f["digests"]["sha256"] for f in releases[version]}


def is_declaration(text):
    return (text.startswith(("class ", "def ", "cdef class")) or re.match(r"^[A-Za-z_]+\s*=", text) is not None
            or "Enum" in text)


def scan(wheel):
    hits, scanned = [], 0
    with zipfile.ZipFile(wheel) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith(MEMBER_SUFFIXES):
                continue
            scanned += 1
            for number, line in enumerate(archive.read(name).decode("utf-8", "replace").splitlines(), 1):
                text = line.strip()
                if is_declaration(text) and PATTERN.search(text):
                    hits.append((name, number, text[:110]))
    return scanned, hits


def main(paths):
    for path in map(Path, paths):
        version = re.search(r"nautilus_trader-([0-9a-z.]+)-", path.name).group(1)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        published = published_digests(version)[path.name]
        scanned, hits = scan(path)
        print(f"== {path.name}: {path.stat().st_size} bytes, sha256 {digest}")
        print(f"   PyPI publishes {published}: {'match' if digest == published else 'MISMATCH'}")
        print(f"   {scanned} source and stub members scanned, {len(hits)} declaration hits")
        for name, number, text in hits:
            print(f"   {name}:{number}: {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
```
