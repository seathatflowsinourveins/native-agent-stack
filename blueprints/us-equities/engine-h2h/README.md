# Alpaca engine head-to-head (paper only)

This directory holds a preregistered comparison of three ways to trade the Alpaca
paper lane:

- the incumbent: NautilusTrader 2.0.0rc5 with our adapter;
- LEAN with the official Alpaca brokerage;
- Lumibot 4.6.0.

It never trades live. It never uses paper-2/3/4, the adaptive lane's account, or the
live incentive engine.

| File | Role |
| --- | --- |
| `research.md` | Research convergence refresh: pins, maintenance, licences, source-cited coverage and known issues. |
| `protocol.json` | Draft preregistered protocol: cases, sessions, metrics, decision rule and accounts. Its `frozen_files` hashes bind the files below. |
| `order_script.json` | The frozen, deterministic order script (21 counted cases plus the E01 reconciliation), shared by every engine. |
| `h2h_common.py` | Shared stdlib helpers: script validation, Decimal prices, paper-credential guard, step machine, metrics, `decide()`. |
| `run_nautilus.py` | Incumbent runner: a real rc5 LiveNode with our adapter, against the synthetic port or `AlpacaPaperTransport`. |
| `run_lean/` | `H2HOrderScriptAlgorithm.cs` plus `run.py`: compile with the SDK's own csc, sandboxed backtest, plugin probe, paper mode. |
| `run_lumibot.py` | Lumibot runner: `PandasDataBacktesting` over LEAN's bundled SPY bars, or Lumibot's own Alpaca broker. |
| `receipts/offline-20260925.json` | Sanitized offline verification: commands, hashes, repeat runs, per-case results and preserved failed attempts. |

## Offline verification (no broker, no credentials, no network)

The paths below use two placeholders. `$STACK` is `~/.local/share/codex-ecosystem/tools`,
and `$RUN` is a fresh private scratch directory.

```sh
# LEAN: compile and backtest in execution-realism's no-network sandbox.
ecosystem-bounded-run python3 -B run_lean/run.py backtest --lean-source $STACK/lean-985ef30-r20260925/Lean \
  --dotnet $STACK/dotnet-equity10/dotnet --out $RUN/lean-backtest

# LEAN plugin compatibility: the remediated Alpaca build loaded as plugin-directory.
ecosystem-bounded-run python3 -B run_lean/run.py probe-alpaca --lean-source $STACK/lean-985ef30-r20260925/Lean \
  --dotnet $STACK/dotnet-equity10/dotnet --plugin $STACK/lean-alpaca-1973f61-remediated/source/QuantConnect.AlpacaBrokerage/bin/Debug \
  --out $RUN/lean-probe

# Lumibot and the incumbent: inside bwrap --unshare-all with a read-only root
# (the exact argv is in the receipt).
$STACK/lumibot-4.6.0-r20260925/bin/python -B run_lumibot.py backtest \
  --lean-data $STACK/lean-985ef30-r20260925/Lean/Data/equity/usa/minute/spy --out $RUN/lumibot-backtest
$STACK/adaptive-paper-r20260925/bin/python -B run_nautilus.py synthetic --out $RUN/nautilus-synthetic
```

Results on 2026-09-25, repeated once with identical per-case results. The LEAN journal
was byte-identical across the two runs.

| Engine (offline mode) | Covered of 21 | Without our glue | Not covered |
| --- | --- | --- | --- |
| LEAN (backtest, Alpaca model) | 14 | 14 | R07-R09: no contingent orders at the pin |
| Lumibot (backtest) | 14 | 14 | R11, R12, X04: the backtest accepted or filled what Alpaca refuses |
| Incumbent (synthetic port) | 7 | 0 | Limit/DAY only; R07 stops the node |

In every run, F01-F03 need a live process and a broker, and R10 needs a partial fill.
These offline modes are different evidence classes and are not the head-to-head
result. The unit tests are `python3 -m unittest tests.test_engine_h2h_protocol tests.test_engine_h2h_guards`.

## Account plan

The paper run needs three dedicated Alpaca paper accounts, one per engine, never shared.
Each has its own file in the private credential store (`docs/secret-storage.md`),
written with `tools/credentials/set_credential.py`:

- `alpaca-paper-h2h-nautilus.env`
- `alpaca-paper-h2h-lean.env`
- `alpaca-paper-h2h-lumibot.env`

Each file holds `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`. The optional
`APCA_API_BASE_URL` may only be `https://paper-api.alpaca.markets`. Each runner refuses
the following:

- any other file name, including paper-1 to paper-4 and the other engines' names;
- a non-paper host;
- a file that fails the adaptive-paper credential guard.

**LEAN needs a separate user decision.** The official plugin validates a QuantConnect
product license before any Alpaca call (`AlpacaBrokerage.cs:167, 994-1119`). That
needs a QuantConnect account and organization with the subscription, and the plugin
sends host identifiers (machine and user name, OS, and interface IP and MAC addresses)
to QuantConnect. If the user declines, LEAN cannot run on paper, two accounts
suffice, and the comparison is Lumibot against the incumbent.

## Paper runs: not started

The paper modes exist and refuse without the dedicated files, but none has run.
Before session 1, three pieces are still missing:

- the read-only broker observer;
- the fault orchestrator (kill, SIGTERM, restart, network-namespace stream drop);
- the backtest-replay tooling for the fill-delta metric.

`protocol.json` specifies all three. Freeze `protocol.json` after they are built and
reviewed, and before the first paper order.
