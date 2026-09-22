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

Two accepted fresh-process runs each returned 10,000 iterations, 1,804 events, 902 simulated orders/fills, 451 closed positions and 903 account rows. All 902 fills reconcile to ending cash, and aggregate realized PnL from 451 flat positions equals the cash change. Both economic reports match, and account CSV bytes match exactly. Fill/position CSVs contain generated UUIDs; comparison validates and normalizes only the explicitly named UUID fields, with every other field equal. One stable non-snapshot position ID is preserved. This is fixture reproducibility, not investment performance.

Two initial attempts exited zero but collected empty reports after disposal, so they failed useful-result acceptance and remain retained. The corrected before-dispose observation captures the reports and verifies original cleanup. No credentials, host home or network interface beyond loopback were available in the Bubblewrap runs. No broker or model request was made.

The [equity replay and broker acceptance plan](acceptance-plan.md) freezes the retained SPY inputs, exact first-case oracle, mapping requirements, offline failure outcomes and separate IBKR/Alpaca paper procedures. Subsequent work completed a bounded [AAPL diagnostic replay](equity-replay/receipt.json) and the separate Alpaca paper smoke linked by the [target catalog](../../../catalogs/us-equities/runtime-target.json). SPY/LEAN economic parity, broader broker fault recovery and IBKR operation remain open. These later results do not expand the synthetic quickstart's acceptance scope above.

The [native CI workflow](../../../.github/workflows/native-foundation-e2e.yml) performs a fresh Linux install, checks the downloaded engine wheel and source hashes, runs the unchanged example twice in mandatory network namespaces, and retains command outputs and failures. Its [independent verifier](../../../scripts/verify_nautilus_ci.py) checks exact distributions, isolation, cleanup and the report comparisons above. A green artifact qualifies that specific synthetic engine workflow; it does not qualify broker execution or a new PC's private accounts.

The [fresh hosted run](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35531326386) passed all steps on September20. The coordinator rehashed all46 downloaded artifacts and reproduced the full verifier result. [Returned upstream outputs and hashes](../../../evidence/receipts/native-nautilus-ci-20260920.json) preserve the earlier runner-path failure and its scoped correction. Both CI economic hashes match the original Linux/WSL acceptance.
