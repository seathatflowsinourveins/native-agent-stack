# NautilusTrader v2 engine acceptance

The user-selected destination is NautilusTrader **2.0.0rc5** with IBKR plus a separately validated Alpaca boundary. This isolated Linux acceptance uses the unchanged upstream synthetic EUR/USD quickstart. It does not replace the accepted LEAN comparison or qualify equity data, strategy performance, broker connectivity or paper execution.

Upstream source: commit `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, `docs/getting_started/quickstart.py`; SHA256 `487e6807dedd1a38062638eb671f6110799451611819542bf0f0c10646cb2c53`. Official [installation](https://nautilustrader.io/docs/latest/getting_started/installation/) supports vanilla CPython 3.12–3.14. The accepted host used Python 3.12.3, uv 0.12.17, Bubblewrap 0.9.0 and glibc 2.39.

Choose new owned paths outside existing environments:

```sh
uv venv --python /usr/bin/python3.12 "$NAUTILUS_ENV"
uv pip install --python "$NAUTILUS_ENV/bin/python" --index-url https://pypi.org/simple --pre nautilus_trader==2.0.0rc5 numpy==2.5.3 pandas==3.0.6
uv pip check --python "$NAUTILUS_ENV/bin/python"
curl -fsSL https://raw.githubusercontent.com/nautechsystems/nautilus_trader/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py -o "$UPSTREAM_QUICKSTART"
sha256sum "$UPSTREAM_QUICKSTART"
```

The linked [observer](observe_quickstart.py) calls documented native report methods immediately before the original `engine.dispose()`, then allows upstream cleanup. It changes no strategy or generated input. Run it with the exact read-only mounts, cleared environment, isolated network and owned output directory recorded in the [native receipt](../../../evidence/receipts/native-nautilus-v2-20260920.json). Paths are portable placeholders. The upstream source and observer are mounted at `/input/quickstart.py` and `/input/observe_quickstart.py`; outputs go to `/out`.

Two accepted fresh-process runs each returned 10,000 iterations, 1,804 events, 902 simulated orders/fills, 451 closed positions and 903 account rows. All cash and position rows reconcile, all positions finish flat, and both economic reports match. Account CSV bytes match exactly. Fill/position CSVs contain generated UUIDs; comparison validates and normalizes only the explicitly named UUID fields, with every other field equal. This is fixture reproducibility, not investment performance.

Two initial attempts exited zero but collected empty reports after disposal, so they failed useful-result acceptance and remain retained. The corrected before-dispose observation captures the reports and verifies original cleanup. No credentials, host home or network interface beyond loopback were available in the Bubblewrap runs. No broker or model request was made.

The next scope is retained equity replay and independent cash/order comparison. Broker-specific risk, ambiguous submissions, partial fills, cancels and restart reconciliation remain separate acceptance work. The [target catalog](../../../catalogs/us-equities/runtime-target.json) records current IBKR and Alpaca boundaries.
