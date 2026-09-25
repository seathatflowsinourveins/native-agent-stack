# Alpaca execution engines: research convergence refresh (2026-09-25)

Scope: open-source engines that can place Alpaca paper orders for US equities from a
strategy and also backtest the same code. Evidence levels are kept apart: **source**
(file:line at the pin), **metadata** (GitHub and PyPI APIs read on 2026-09-25) and
**local integration** (this directory's offline runs, `receipts/offline-20260925.json`).
Nothing here places a paper order.

## Carried into the head-to-head

### 1. NautilusTrader 2.0.0rc5 with our adapter (incumbent)

- **Pin and maintenance.** `nautilus_trader` 2.0.0rc5, a prerelease of 2026-09-15. The
  repository was pushed on 2026-09-25 and is LGPL-3.0. The adapter is ours:
  `../adaptive-paper` at `origin/main` 428aba2a.
- **No upstream Alpaca adapter.** [RFC #3374](https://github.com/nautechsystems/nautilus_trader/issues/3374)
  is open (last updated 2026-05-08).
  [PR #3375](https://github.com/nautechsystems/nautilus_trader/pull/3375) closed unmerged
  nine minutes after it opened.
- **Engine versus adapter coverage.** The engine models market, limit, stop, stop-limit
  and trailing orders, at-the-open and at-the-close, and OTO/OCO/OUO contingencies (rc5
  enums). The adapter narrows this:
  - It accepts limit/DAY only (`native_adapter.py:721-723`) and rejects every modify
    (`768-774`).
  - It sets `extended_hours` from its session policy and the clock, not per order (`732-735`).
  - It starts only flat unless overnight holds are on (`381-385`).
  - It books fills per execution and closes fill gaps from FILL activities (`7-13`).
  - It limits submits to 180 per minute (`917-918`).
- **Known issue found here.** A bracket reaches the adapter's inherited
  `_submit_order_list`, which raises `NotImplementedError` in rc5
  (`nautilus_trader/live/clients.py:655-656`). `shutdown_on_error=True`
  (`native_adapter.py:913`) then stops the whole node.
- **Existing evidence.** Paper runs at 200/min with streamed fills and flat
  reconciliation. The native-faults cases C01, C02, C04 and C05 passed on paper
  (`../adaptive-paper/native-faults/README.md`).
- **Offline result.** 7 of 21 cases covered, 0 of them without glue.

### 2. LEAN with the official Alpaca brokerage (catalog default of 2026-09-19)

- **Pins and upstream drift.** LEAN is at 985ef30 (2026-09-18) with the recorded
  three-line remediation; upstream `master` is 16 commits ahead at e02972a6. The
  plugin is at 1973f61 (2026-09-15); upstream HEAD ee94d680 adds an Alpaca.Markets DLL
  with an order-class fix (#80), multi-leg options (#79) and index options (#82).
  Both are Apache-2.0, as declared in the README and source headers; GitHub detects no
  licence for the plugin.
- **Coverage at the pin.**
  - The Alpaca model allows market, limit, stop, stop-limit, trailing, MOO and MOC for
    equities (`Common/Brokerages/AlpacaBrokerageModel.cs:42-43`), and outside regular
    hours only limit orders with Day TIF (`100-105`).
  - The plugin maps MOO/MOC to opg/cls (`AlpacaBrokerageExtensions.cs:184-187`) and
    sends trailing percent × 100 (`236-238`).
  - It replaces orders through PatchOrder (`AlpacaBrokerage.cs:641-677`) and imports
    open orders at start (`312-314`).
- **Missing at the pin: bracket, OCO and OTO.** LEAN added them today
  ([Lean#9828](https://github.com/QuantConnect/Lean/pull/9828), 03514bb). The plugin's
  [PR #83](https://github.com/QuantConnect/Lean.Brokerages.Alpaca/pull/83) is open and
  requires #9828. An earlier OCO PR, #74, closed unmerged.
- **Known issues.**
  - [#78](https://github.com/QuantConnect/Lean.Brokerages.Alpaca/issues/78), open: the
    plugin sends no `client_order_id`, and an exception such as a timeout inside
    `PlaceOrder` marks the order Invalid (`AlpacaBrokerage.cs:460-494`). A broker order
    can therefore be orphaned.
  - On reconnect the plugin re-subscribes data but does not re-sync orders (`845-882`).
  - LEAN warns about price rounding once per process
    (`BrokerageTransactionHandler.cs:1994-2003`), so later roundings are silent.
- **Blocking prerequisite.** `ValidateSubscription()` runs inside `Initialize`
  (`AlpacaBrokerage.cs:167, 994-1119`).
  - It needs a QuantConnect user id, API token and organization licensed for product
    347.
  - It sends the machine name, user name, OS and every up interface's IP and MAC
    address to QuantConnect.
  - It exits the process if validation fails.
  - The README's local route is the LEAN CLI in an organization workspace
    (`README.md:41-43`).
- **Offline result.** 14 of 21 covered. The remediated plugin loads into the r20260925
  engine with every reference matching (receipt, `lean_alpaca_plugin_probe`).

### 3. Lumibot 4.6.0 (catalog: hold)

- **Pin and maintenance.** Released 2026-09-24; wheel sha256 `872e91cb…b7e7`, tag
  v4.6.0 = 231fd9e7. GPL-3.0. Pushed 2026-09-25, with 93 open issues and pull requests. The lock
  resolves 264 packages, including LLM/agent SDKs (google-adk, litellm, openai, mcp).
- **Coverage.**
  - `create_order` offers limit, stop, stop-limit, trailing, bracket, OCO and OTO
    (`strategies/strategy.py:546-575, 737-781`).
  - The Alpaca broker submits orders (`brokers/alpaca.py:1117-1303`), replaces only the
    limit or stop price (`1347-1418`) and cancels (`1331-1344`).
  - It passes the TIF through, so opg/cls reach Alpaca unmodelled (`1187`).
  - Extended hours need the raw `custom_params` passthrough (`1199-1203`).
- **Known issues (source).**
  - **Trailing-stop unit mismatch.** `trail_percent` is documented as a fraction, where
    0.05 means 5% (`strategy.py:671-675`), and backtested that way (`order.py:788-791`).
    The Alpaca broker forwards it unchanged (`alpaca.py:1156, 1171, 1192`) to Alpaca's
    percent field ([orders-at-alpaca.md:304](https://docs.alpaca.markets/us/docs/orders-at-alpaca.md)),
    so a documented 10% trail becomes 0.1%.
  - Bracket and OTO parents are sent as `type=market` (`alpaca.py:1141-1146`), although
    the docs give `limit_price` as the entry (`strategy.py:749-781`).
  - Sub-penny prices are rounded before sending (`1159-1171`).
  - No `client_order_id` is sent by default (`1181-1193`), so an exception during
    submit (`1269-1301`) can orphan an accepted order.
  - The stream ignores orders it does not track (`1926-1929`).
  - On import, Lumibot loads the first `.env` found from the script directory or cwd
    up to `/` (`credentials.py:118-173`). The runner disables this.
- **Offline result.** 14 of 21 covered. The backtest accepted a sub-penny limit, filled
  100,000 shares without a buying-power check, and filled an extended-hours market order.

## Screened out

| Project | State on 2026-09-25 | Reason |
| --- | --- | --- |
| [kumo-nautilus-alpaca-adapter](https://github.com/FALK-BRAUER/kumo-nautilus-alpaca-adapter) | LGPL-3.0, 0 stars, pushed 2026-09-20 | Pins `nautilus_trader==1.229.0` and Python 3.13; only market and limit (`exec_client.py:113-130`) |
| [gmatrunich/nautilus-alpaca](https://github.com/gmatrunich/nautilus-alpaca), [mutn3ja/nautilus-alpaca](https://github.com/mutn3ja/nautilus-alpaca) | 0 stars; no tests, or no licence | Not built for 2.0.0rc5 |
| [StrateQueue](https://github.com/StrateQueue/StrateQueue) | AGPL-3.0, v0.5.1, last commit 2025-12-30 | A signal bridge for backtest libraries; Alpaca bracket/OCO/OTO exist (`alpaca_broker.py:858-884`), but nothing has been committed for 9 months |
| [OpenAlice](https://github.com/TraderAlice/OpenAlice) | AGPL-3.0, TypeScript, active | Model-driven agent app; the project keeps order state in deterministic code |
| [Blankly](https://github.com/Blankly-Finance/Blankly) | LGPL-3.0, last push 2024-12-30 | Dormant |
| [alpaca-backtrader-api](https://github.com/alpacahq/alpaca-backtrader-api), [pylivetrader](https://github.com/alpacahq/pylivetrader) | Last commits 2022 | Deprecated by Alpaca |
| Vibe-Trading, FinRL-Trading | MIT, Apache-2.0 | Agent and RL toolkits with Alpaca connectors, not engines |
| StockSharp | Licence not detected by GitHub (NOASSERTION) | The Alpaca connector is not in the open repository |
| investing-algorithm-framework, aat, hikyuu, rqalpha, vectorbt, backtesting.py | Various | No Alpaca execution path |

Sources:
- The user's 347 stars.
- [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) README lines 196-229.
- [awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading)
  README lines 128-182.
- GitHub searches for "alpaca live trading framework" and "nautilus alpaca adapter".
- Commercial and closed-source platforms (QuantRocket, Zorro) are excluded.

## Where the evidence converges

- **Three candidates.** Only the three above are maintained, openly licensed, backtest
  capable and able to execute US equities on Alpaca. All three reach Alpaca through
  its official SDKs.
- **Different strengths.**
  - The incumbent is the only one with an idempotent client-id submit, per-execution
    booking, and paper fault evidence. It covers limit orders only.
  - LEAN has the broadest correct native coverage at its pins, except contingent orders.
    It cannot trade paper without a QuantConnect license decision.
  - Lumibot has the widest API. Its Alpaca path has defects visible in its source, which
    paper runs must confirm.
- **Decision state.** Keep-but-compare. The incumbent stays selected until the
  preregistered paper protocol (`protocol.json`) decides.
- **What would overturn this refresh.**
  - Lean.Brokerages.Alpaca#83 merging together with a LEAN release after 03514bb.
  - Lumibot fixing its trailing-stop unit and its bracket entry type.
  - An upstream NautilusTrader Alpaca adapter.
