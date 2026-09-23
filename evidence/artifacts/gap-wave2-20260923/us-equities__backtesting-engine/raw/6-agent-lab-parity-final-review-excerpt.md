- **Parity final review (`wf_88f01a45-eeb`, Opus inventory variant, 3 agents, 273,308 tokens)**: script result
  `rejected` on a **mechanical label mismatch only** (the inventory recorded each check as `rtk proxy <cmd> (cwd …)`, so the
  exact-string match failed); the independent recheck re-ran all five acceptance commands verbatim, exit 0 each
  (`Ran 92 tests OK`, `Ran 8 tests OK`, verdict line `BLOCKED True 4 ['distributions_and_cash','market_on_open_proxy'] [] [] []`,
  comparator re-derivation exit 1 as documented for non-PASS with the re-derived verdict identical). Opus verifier: **21/24
  claims confirmed, 2 corrected, 1 unverifiable**; 6 defects, none changing the BLOCKED verdict, logged for the G-a follow-up
  round: (1) `fixture_strategy.py:266` substitutes a zero commission when `OrderFilled.commission` is None instead of
  refusing; (2) `convert.py:116-123` value-level record validation only on in-window rows; (3) `fixture_strategy.py:109`
  iteration-equality check conditional on non-None; (4) `convert.py:239` nonpositive derived distribution dropped silently;
  (5) README states `--bars` and no-evidence modes as observed but only `--lean-data` is in the acceptance set; (6) inventory
  metadata (13 vs 17 test classes). Gaps: no engine execution observed in review (receipt is the run's own word for
  `two_run_records_equal`); `probes/` outside the scope list; upstream Nautilus source at the pin not on host (wheel stubs +
  local probes only); cash reconstruction consumes the receipt's distribution ledger rather than the frozen factor file;
  `__pycache__` untracked inside the directory. Disposition: **G-a sealed as interim BLOCKED evidence** with these six
  hardening items and the dividend `SimulationModule` / open-fill path as the named next round.
- **Row 4 workers/SDK runner (builder a4916f1, 333,406 tokens, 257 tool uses)**: integrated
  (`tools/compare/workers/{run-arms.mjs e434b0bb…, arm_c_driver.py a3abea84…, lib/*.mjs}`, five
