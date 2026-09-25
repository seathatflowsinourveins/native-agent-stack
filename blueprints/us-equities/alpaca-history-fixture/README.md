# Alpaca historical-data fixture

The user decided on 2026-09-25 to test Alpaca's historical data before buying any other data. This blueprint is
that test. It checks Alpaca Market Data (SIP, daily, 2016 onward) against the fixtures R1 named, under the frozen
definitions of the two gates that R1 left purchasable: `pre-2020-delisting` and `dated-security-identity`
(`catalogs/us-equities/gates-20260922.json`).

| File | Role |
| --- | --- |
| `protocol.json` | `alpaca-history-fixture-v1-20260925`. Frozen before any run: fixtures, metrics, pass and fail rules per gate, rate budget, feed and adjustments, and the verified plan facts |
| `fixture.py` | Deterministic runner. Standard library only; plain HTTPS GET to `data.alpaca.markets` |
| `../../../tests/test_alpaca_history_fixture.py` | 45 synthetic tests with a stubbed HTTP layer. No network and no keys |

**Status:** not yet run. The API keys are not stored yet, and the coordinator runs the fixture once they are.

## Plan facts (official pages, read 2026-09-25)

| Claim (the user's report) | What the official page says | Source (page date) |
| --- | --- | --- |
| Algo Trader Plus is free through Elite 100k | "Get Algo Trader Plus on us (value of $99/month) - only for personal use" | [alpaca.markets/elite](https://alpaca.markets/elite) (no date shown) |
| 9+ years of history | Historical data "Since 2016", on both Basic and Algo Trader Plus. The first SIP daily bar this repository observed is 2016-01-04 | [About Market Data API](https://docs.alpaca.markets/docs/about-market-data-api) (2026-07-16) |
| Real-time coverage of all exchanges | "All US Stock Exchanges" (Basic: IEX only) | same page |
| 10,000 API calls per minute | "10,000 / min" (Basic: 200). The `X-RateLimit-Limit` header read 10000 on 2026-09-21 and 2026-09-24 | same page |
| Unlimited WebSocket symbols | "Unlimited" (Basic: 30 symbols) | same page |

- **Marketing page conflicts.** [alpaca.markets/data](https://alpaca.markets/data) (no date shown) says "7+ years" and "Unlimited API calls". The protocol binds to the docs: history since 2016, and 10,000 calls per minute.
- **Endpoints.** The [bars](https://docs.alpaca.markets/reference/stockbars) and [auctions](https://docs.alpaca.markets/reference/stockauctions-1) references (both 2026-05-27) document:
  - `asof` symbol mapping, where `-` skips the mapping;
  - adjustment `raw` or `split`;
  - `feed=sip`, the only feed that auctions accept.
- **Mapping lag.** The [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) (2026-09-21) says `asof` mapping reaches the historical endpoints the day after a rename.
- **What the plan changes here.** Both plans serve SIP history since 2016. So for this test the plan changes only the call limit, and the receipt records the rate-limit header it observes.

## Fixtures

1. **Delistings, 2016 to 2019:** 1,236 Form 25-NSE common-equity rows (378, 296, 268 and 294 per year).
   - Source: `evidence/artifacts/pre-2020-delisting/classifications-2016-2019.json`, pinned by sha256 and by the sha256 of its accession list.
   - The rows carry no tickers, and Alpaca's data API cannot look up an issuer by name or CIK. Tickers therefore come from a separate map, `--delisting-tickers`, whose schema and allowed provenance classes the protocol fixes.
   - Only point-in-time classes count toward the gate: an EDGAR `dei:TradingSymbol`, an EDGAR cover-page symbol, or an exchange delisting notice. **No such map exists yet.**
2. **Collisions:** the 235 asset-master ticker collisions from `broad-universe`, recomputed with that blueprint's own `select_symbols`.
   - The supplied asset master (`--asset-master`) or `symbol-identities.json` (`--symbol-identities`) must reproduce 15,418 symbols, 235 collisions and the 17,456 OTC and 418 placeholder exclusions exactly.
   - The runner cannot fetch an asset master itself, because that endpoint is on the trading host.
3. **Reused tickers:** LOGC, TEN, BTX and CBIO, one row each from the extreme-gainer package (`--package-dir`, hash-checked by the audit's own `check_inputs`).
4. **Owed audit rows:** the 130 rows (84 mismatch, 45 recovered_mismatch, 1 package_uncomputed_mismatch) from the private results of audit run-20260924b (`--audit-results`, sha256 `7e8b6999…`).
   - The rows are never re-derived from a new fetch.

The private inputs for items 2 and 4 were written on another host and are not on the Mac that wrote this protocol.
Each input is optional. A fixture whose input is missing reads `not_evaluable`.

## Rules in brief (protocol.json has the full text)

- **pre-2020-delisting.**
  - A row counts toward the gate only if its symbol is point in time and its raw SIP bars pass every check:
    - they exist within 60 days before the filing;
    - they stop within 10 sessions after it;
    - they cover at least 90% of the sessions in the trading-year window, with at least min(20, window) bars. The window is clipped at 2016-01-04.
  - The run proposes `coverage_status: confirmed` only when every year from 2016 to 2019 reaches 95% of its rows. The 95% matches the audit's 5% overturn share.
- **dated-security-identity.**
  - The literal series (`asof=-`) is split at gaps of more than 10 sessions.
  - Each segment is probed with `asof` set to its last bar. A segment's entity is the probe's full response.
  - A collision is dated only when three conditions hold:
    - every segment is attributed;
    - no two tenures overlap;
    - the number of entities equals the number of asset ids.
  - The gate's title also requires a historical security type, and the Market Data API has none. So `unresolved_collisions` stays at 235 under the frozen definition. `undated_collisions` is reported beside it as partial evidence.
- **Reused tickers.**
  - A row passes when its official-close gain with `asof` set to the event date agrees with the catalogued gain and disagrees with the package's gain from the later holder of the ticker.
  - The official close follows audit rules v2.
  - All four rows must pass before the identity gate can pass.
- **Owed rows.**
  - Measured with the audit's own gain tolerance, max(0.5 pp, 0.5% of the gain), never a tolerance on price.
  - `reproduced` requires that at least 95% of rows reproduce the audit's 2026-09-24 Alpaca gain.
  - Agreement with the package reference is reported separately, on official-close, raw-bar and split-bar bases.
  - Alpaca is the audit's own second source, so none of this adjudicates an owed row.
- **Rate budget.**
  - 5,000 requests per minute (half the verified 10,000), sequential, with a 12,000-request ceiling for the run.
  - The cap drops to half of any lower `X-RateLimit-Limit`.
  - Backoff follows `Retry-After` and `X-RateLimit-Reset`, with at most 5 retries.
  - HTTP 401 or 403 stops the run.
  - The expected total is about 4,100 requests.

The runner never writes a gate receipt and never changes a gate status. Its receipt proposes values; flipping a gate
still needs manual qualification and a dated commit.

## Run

Check the inputs offline first; `plan` makes no network call and needs no keys:

```sh
python3 blueprints/us-equities/alpaca-history-fixture/fixture.py plan \
  --package-dir "$PACKAGE_DIR" --audit-results "$AUDIT_RESULTS" \
  --symbol-identities "$SYMBOL_IDENTITIES" --delisting-tickers "$DELISTING_TICKERS"
```

Then run it once, from the checkout root, with keys only from the login Keychain:

```sh
~/.local/bin/secret run APCA_API_KEY_ID APCA_API_SECRET_KEY -- \
  python3 blueprints/us-equities/alpaca-history-fixture/fixture.py run \
  --package-dir "$PACKAGE_DIR" --audit-results "$AUDIT_RESULTS" \
  --symbol-identities "$SYMBOL_IDENTITIES" --delisting-tickers "$DELISTING_TICKERS" \
  --out-dir "$PRIVATE_DIR/alpaca-history-fixture-run-1" \
  --receipt blueprints/us-equities/alpaca-history-fixture/receipt-run-1.json
```

- **Placeholders.**
  - `PACKAGE_DIR`: the private extreme-gainer package.
  - `AUDIT_RESULTS`: the audit's private `results-b.json`.
  - `SYMBOL_IDENTITIES`: the broad-universe run's `symbol-identities.json`. To use the asset master instead, pass `--asset-master ACTIVE.json INACTIVE.json`.
  - `DELISTING_TICKERS`: the frozen ticker map.
  - `PRIVATE_DIR`: a private directory outside every git checkout.
- **Leaving inputs out.** Drop any input that is not available; its fixture then reads `not_evaluable`.
- **Refusals.**
  - An `--out-dir` inside a git checkout.
  - An existing receipt.
  - Missing keys.
  - Any host other than `data.alpaca.markets`, any path other than `/v2/stocks/bars` and `/v2/stocks/auctions`, and any redirect.
- **Outputs.**
  - The private directory holds `snapshot.json` (every response) and `details.json` (per-row dates and gains), mode 0600.
  - The public receipt holds counts, verdicts and hashes. The runner refuses to write it if a credential value, a UUID or a local path would appear in it.
- **Reproduce.** Recompute from the snapshot alone; the output is byte-identical:

  ```sh
  python3 blueprints/us-equities/alpaca-history-fixture/fixture.py evaluate --snapshot "$PRIVATE_DIR/alpaca-history-fixture-run-1/snapshot.json" \
    <the same inputs> --out-dir "$PRIVATE_DIR/alpaca-history-fixture-eval-1" --receipt "$PRIVATE_DIR/receipt-eval-1.json"
  ```

## Tests

```sh
python3 -m unittest tests.test_alpaca_history_fixture
```

The tests are synthetic, and a stub stands in for Alpaca's documented `asof` semantics. They cover:
- the host, path and redirect refusals;
- environment-only keys and the public-output check;
- the rate budget, backoff, headroom and ceiling;
- pagination;
- every delisting verdict and the gate thresholds;
- ticker-map validation;
- collision dating: two issuers, a long halt, interleaved tenures and an unattributed segment;
- the reused-ticker test, reproduction of the owed rows and their pinned selection;
- an end-to-end run followed by `evaluate`, with byte-identical receipts and no key in any output.

These are local integration checks. They are not upstream acceptance and not a live run.

## Predictions recorded before any run

- `pre-2020-delisting`: `not_evaluable` until a point-in-time ticker map exists. With a map, Alpaca's history starts
  in 2016, so rows filed early in 2016 are judged on clipped windows.
- `dated-security-identity`: `fail` under the frozen definition, because the API has no security type. The dating count
  shows whether a new protocol that pairs Alpaca with a separate type source is worth writing.
- Owed rows: agreement with the package is expected to stay low, since these rows are the audit's mismatches.
  Reproduction measures whether Alpaca's history changed after 2026-09-24.
