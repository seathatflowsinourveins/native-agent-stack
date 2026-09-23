#!/usr/bin/env python3
"""Write the per-gap receipts, results.json (derived from the receipts) for this layer.

Receipt facts are written here from the executed runs; raw outputs cited by each
receipt are hashed from disk at build time so the recorded sha256 matches the
committed bytes. results.json is generated from the receipts, never by hand.
"""
import datetime
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LAYER = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine"
PREREG = json.loads((LAYER / "preregistration.json").read_text())
FIX1 = json.loads((LAYER / "preregistration-fix1.json").read_text())
FIX2 = json.loads((LAYER / "preregistration-fix2.json").read_text())
HELPERS = "blueprints/gap-wave2-20260923/us-equities__backtesting-engine"
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(path):
    return hashlib.sha256((REPO / path).read_bytes()).hexdigest()


def raw(*names):
    out = []
    for n in names:
        p = f"evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/raw/{n}"
        if not (REPO / p).is_file():
            raise FileNotFoundError(p)
        out.append({"path": p, "sha256": sha(p)})
    return out


def gaps():
    return {g["index"]: g for g in json.loads((LAYER / "inputs" / "gaps.json").read_text())["gaps"]}


BWRAP_NAUTILUS = ("bwrap --unshare-all --die-with-parent --new-session --clearenv --ro-bind /usr /usr --symlink usr/bin /bin "
                  "--symlink usr/lib /lib --symlink usr/lib64 /lib64 --proc /proc --dev /dev --tmpfs /tmp "
                  "--ro-bind $NENV $NENV --ro-bind $REPO /repo --ro-bind {data} /data --bind {out} /out --chdir /repo "
                  "--setenv LANG C.UTF-8 --setenv PATH /usr/bin:/bin --setenv PYTHONDONTWRITEBYTECODE 1 "
                  "--setenv OPENBLAS_NUM_THREADS 1 --setenv OMP_NUM_THREADS 1 $NENV/bin/python -I {script}")
ENV_NOTE = ("NENV=$HOME/.local/share/codex-ecosystem/tools/nautilus-2.0.0rc5; REPO=$HOME/code/nas-wt-g2-backtesting-engine; "
            "C=$HOME/.cache/gap-wave2-20260923/backtesting-engine")

PEER_GATES = "catalogs/us-equities/gates-20260922.json"


def receipts():
    R = {}
    R[0] = dict(slug="spy-lean-parity-peer", outcome="covered_elsewhere", evidence_class="source_review",
        commands=[f"python3 -c \"read {PEER_GATES} gates spy-lean-parity, dividend-sim-module\"",
                  "sha256sum blueprints/us-equities/engine-nautilus/spy-parity/verdict.json"],
        results={"spy-lean-parity": {"owner": "peer:sota-workflow-resolution", "status": "blocked",
                                     "flip_condition": "/verdict == PASS in spy-parity/verdict.json"},
                 "dividend-sim-module": {"owner": "peer:sota-workflow-resolution", "status": "not_established"},
                 "verdict_sha256_at_base": "b7b898a861492348ae864de25551c127a0367e4638ef5dfa65152f233a6b0d10",
                 "incidental_observation": "Gap 6's fresh bwrap replay and three comparator modes on 2026-09-23 reproduced BLOCKED (25 PASS / 4 FAIL, 0 unattributed) byte-identically; the stress/margin comparison statuses were not touched."},
        remaining="Owned by peer:sota-workflow-resolution under its preregistration: model or resolve costs_and_rounding_stress and margin_and_adaptive_state and rerun the blocked comparisons.",
        limits=["No mapping-manifest, tolerance, gate or verdict file was changed by this unit (hard rule: gate rows belong to the peer)."],
        raw_outputs=raw("6-compare-lean-data.verdict.json"))
    R[1] = dict(slug="nautilus-alpaca-bars-corporate-actions", outcome="advanced", evidence_class="local_integration",
        commands=[ENV_NOTE,
                  BWRAP_NAUTILUS.format(data="$HOME/codex-ecosystem/state/authenticated-data-20260920/alpaca-run-1",
                                        out="$C/ca-window", script=f"/repo/{HELPERS}/ca_window_replay.py --run /data --out /out/native"),
                  "gh api 'repos/nautechsystems/nautilus_trader/git/trees/1b0a49d2792a9432a3aca3fcb617ce7a630d905e?recursive=1' --jq '.tree[].path'",
                  "gh api 'repos/nautechsystems/nautilus_trader/contents/docs/concepts/instruments/equity.md?ref=1b0a49d2792a9432a3aca3fcb617ce7a630d905e' --jq .content | base64 -d",
                  "rg -n -i 'dividend|stock.?split|corporate.?action' --glob '*.pyi' <rc5 site-packages>/nautilus_trader",
                  f"python3 {HELPERS}/detection_probe.py  (fix round 1, synthetic)"],
        results={
            "exit_code": 0,
            "input": "Retained authenticated Alpaca AAPL 1Day SIP raw bars, 25 sessions 2020-08-03..2020-09-04, verified by the existing collector against receipt a59c6ed7 (no new data request, no credential read).",
            "actions_in_window": [{"type": "cash_dividend", "ex_date": "2020-08-07", "payable_date": "2020-08-13", "rate": "0.82"},
                                  {"type": "forward_split", "ex_date": "2020-08-31", "old_rate": "1", "new_rate": "4"}],
            "fills": [{"side": "BUY", "qty": 10, "avg_px": "435.7500", "ts": "2020-08-03T20:00:00Z (16:00 NY), raw close"},
                      {"side": "SELL", "qty": 10, "avg_px": "120.9600", "ts": "2020-09-04T20:00:00Z (16:00 NY), raw close"}],
            "account_totals_usd": ["100000.00", "95642.50", "96852.10"],
            "position": {"peak_qty": "10", "realized_pnl": "-3147.90 USD", "adjustments": []},
            "corporate_action_handling_observed": "none: net position stayed 10 on every held bar including 2020-08-31 (close 499.23 on 08-28 -> 129.04 on 08-31), cash stayed 95642.50 through the 08-07 ex-date and 08-13 payable date, no account event besides the two fills, and the position report shows adjustments [].",
            "reconciliation_checks": {"fill_count": True, "fill_BUY_at_raw_close": True, "fill_SELL_at_raw_close": True,
                                      "fill_BUY_at_bar_instant": True, "fill_SELL_at_bar_instant": True,
                                      "native_final_cash_equals_fill_only_ledger": True, "account_events_equal_fills_plus_initial": True,
                                      "one_mark_per_bar": True, "terminal_flat": True,
                                      "position_quantity_constant_10_while_held": True, "cash_constant_while_held": True},
            "fix_round_1": "After the independent review the runner was hardened (fill timestamps, one mark per bar, flat terminal state, explicit refusal without a qualified dividend and split in the window; runner sha256 d4e0bd73...). The rerun in a fresh private directory reproduced the same fills, account totals and economic reference with all 13 checks true.",
            "fix_round_2": "The Codex re-review found fill instants compared at whole-second precision (a +1 ms shift passed). The check now compares exact integer nanoseconds (runner sha256 099519fb...); the rerun in a fresh private directory again reproduced the same fills, totals and all 13 checks true. The cited raw stdout and published excerpt are from this fix-round-2 run.",
            "detection_probe": "Synthetic (no engine, no provider data): reconcile() on a clean synthetic result passes all checks; a synthetic +5 USD dividend credit on held bars fails cash_constant_while_held; a synthetic 10->40 quantity change after the split fails position_quantity_constant_10_while_held; a synthetic BUY fill stamped 1 ms after its bar instant fails fill_BUY_at_bar_instant (exit 0, fix round 2).",
            "economic_reference": {"split_ratio": "4", "dividend_cash_usd": "8.20", "final_cash_usd": "100489.10",
                                   "native_minus_economic_usd": "-3637.00", "missing_split_adjustment_usd": "3628.80",
                                   "unposted_dividend_usd": "8.20"},
            "upstream_example_search": "At pin 1b0a49d the upstream tree (5,645 paths) has no equity backtest example: examples/backtest holds FX, crypto, Architect AX, Databento futures/options/order-book and Tardis examples only; the wheel ships no examples package. docs/concepts/instruments/equity.md mentions no split, dividend, corporate action or adjustment (grep: 0 matches).",
            "rc5_stub_scan": "No split or dividend data type in the rc5 .pyi stubs; the only matches are options-greeks flat_dividend_yield parameters and an IB_DIVIDENDS tick type."},
        remaining="The 'unchanged Nautilus equity backtest example' arm cannot be met at pin 1b0a49d because no upstream equity backtest example exists; the run uses the repo's own minimal strategy on native engine APIs, so the evidence stays local integration. Corporate-action handling is measured as absent; an engine-supported path is the peer-owned dividend-sim-module gate.",
        limits=["Detection method: per-bar native net_position and account balance marks plus the account report; a native credit or quantity change would show as a delta on a bar without a fill. Because rc5 exposes no dividend or split data type, no action data could be fed, so 'absent' means the engine does not act on price discontinuities by itself.",
                "Daily bars with a declared 16:00 New York publication convention; market orders fill at the completed bar close (not a realizable closing auction).",
                "Raw provider rows and native report CSVs stay private under $HOME/.cache/gap-wave2-20260923/backtesting-engine/ca-window; a curated excerpt with the private summary sha256 is committed.",
                "Preregistered numeric expectation said roughly three quarters of the entry notional would be lost; the measured total realized loss is 3147.90 USD on 4357.50 notional (72%), consistent. Of the 3637.00 USD gap to the economic reference, 3628.80 is the missing split adjustment (30 extra shares x 120.96) and 8.20 the unposted dividend.",
                "Scope of 'absent': this replay fed raw bars only, because rc5 exposes no dividend or split data type to feed; it shows the engine makes no adjustment by itself and that no engine-supported ingestion path was found in the rc5 stubs, not that every possible custom-data or module route is impossible."],
        raw_outputs=raw("1-8-ca-window-replay-published.json", "1-8-ca-window-replay.stdout.txt", "1-8-ca-window-replay.stderr.txt",
                        "1-8-detection-probe.stdout.txt", "1-8-detection-probe.exit.txt",
                        "1-8-ca-window-replay.exit.txt", "1-8-ca-window-replay.started_at.txt", "1-8-rc5-stub-corporate-action-scan.txt",
                        "1-upstream-equity-doc-1b0a49d.md", "1-upstream-tree-1b0a49d.txt"))
    R[2] = dict(slug="nautilus-latest-stable-release", outcome="settled", evidence_class="native_proven",
        commands=["gh release list --repo nautechsystems/nautilus_trader --exclude-pre-releases --limit 3",
                  "gh release view v1.231.0 --repo nautechsystems/nautilus_trader --json tagName,name,isPrerelease,publishedAt,targetCommitish"],
        results={"exit_code": 0, "gh_version": "gh version 2.101.0 (2026-09-15)",
                 "output": ["NautilusTrader 1.231.0 Beta\tLatest\tv1.231.0\t2026-08-02T18:53:49Z",
                            "NautilusTrader 1.230.0 Beta\t\tv1.230.0\t2026-06-29T12:06:45Z",
                            "NautilusTrader 1.229.0 Beta\t\tv1.229.0\t2026-06-26T05:06:18Z"],
                 "release_view": {"tagName": "v1.231.0", "isPrerelease": False, "publishedAt": "2026-08-02T18:53:49Z"},
                 "conclusion": "v1.231.0 is the latest non-prerelease on 2026-09-23, matching the packet metadata; the selected 2.0.0rc5 (runtime-target.json line 29 prerelease true) remains a prerelease, now backed by this retained dated receipt."},
        remaining=None,
        limits=["A release listing is a point-in-time GitHub observation; a later stable 2.x release would supersede it.",
                "Disclosed: a discovery call 'gh release list --limit 3' (without --exclude-pre-releases) ran at about 06:18Z before the preregistration; it showed rc5/rc4/rc3 as Pre-release and is not the cited evidence."],
        raw_outputs=raw("2-gh-release-list.txt", "2-gh-release-list.stderr.txt", "2-gh-release-list.exit",
                        "2-gh-release-list.checked_at", "2-gh-version.txt", "2-gh-release-view-v1.231.0.json"))
    R[4] = dict(slug="lean-oracle-alpaca-brokerage-model", outcome="advanced", evidence_class="local_integration",
        commands=[f"python3 {HELPERS}/lean_alpaca_brokerage_oracle.py --lean-source $HOME/.local/share/codex-ecosystem/tools/lean-985ef30 --dotnet $HOME/.local/share/codex-ecosystem/tools/dotnet-equity10/dotnet --out $HOME/.cache/gap-wave2-20260923/backtesting-engine/lean-alpaca",
                  "(each LEAN compile/launch runs inside the existing execution-realism bwrap sandbox: --unshare-all, --cap-drop ALL, --clearenv, read-only engine/data/SDK; exact per-command argv, with $HOME substituted, is retained in raw/4-fix1-lean-report.json from the fix-round rerun; the first run's report did not record argv)"],
        results={"helper_exit_code": 0, "wall_seconds": 36,
                 "variant_diff": "one inserted line after SetTimeZone: SetBrokerageModel(QuantConnect.Brokerages.BrokerageName.Alpaca, AccountType.Margin);",
                 "control_unchanged_algorithm": {"one_zero": "exit 0, 2 fills, end equity 90734.08", "one_stress": "exit 0, 2 fills, 90358.00",
                                                 "two_zero": "exit 0, 5 fills, 3 margin calls, 76310.34", "two_stress": "exit 0, 5 fills, 3 margin calls, 75607.75",
                                                 "adaptive_stress": "exit 0, 3 fills, 95324.10", "over_limit": "exit 0, 0 fills, 1 Invalid (insufficient buying power)",
                                                 "matches_retained_receipt": "all six end equities and the 381/390/202-byte stderr sizes equal the retained historical-simulation receipt"},
                 "alpaca_brokerage_model": {
                     "one_zero|one_stress|two_zero|two_stress|adaptive_stress": "exit 1, 0 fills, entry MarketOnOpen order Invalid: 'BrokerageModel declared unable to submit order: [1] Warning - Code: NotSupported - MarketOnOpen submission time is invalid. Valid local times are  07:00– 09:28. Consider setting DailyPreciseEndTime = false or using Schedule.On.'; the algorithm then threw 'Expected a nonzero stress order.' at 2020-04-29 16:00 (native Status RuntimeError).",
                     "over_limit": "exit 0, 0 fills, 1 Invalid with the same insufficient-buying-power message as the control (buying-power validation precedes the brokerage-model check).",
                     "source_explanation": "AlpacaBrokerageModel at LEAN 985ef30 accepts MarketOnOpen only between 19:00 and 2 minutes before the regular open (09:28) New York; the oracle submits at the 16:00 bar. The rejection text prints the 19:00 start as '07:00' (12-hour format)."}},
        remaining="(a) Alpaca adapter initialization against paper endpoints is broker contact: deferred, owner peer:sota-workflow-resolution. (b) The frozen oracle cannot run unchanged under the Alpaca brokerage model; a schedule that submits MOO inside 19:00-09:28 needs a newly preregistered plan. (c) The data remains bundled LEAN sample files, not an accepted vendor dataset.",
        limits=["Offline backtest only; no network, broker, adapter or credential.",
                "The explicit per-security fee, slippage, fill and buying-power models set after AddEquity override the brokerage model's defaults, so only order-submission validation differs between the variants.",
                "Preregistered expectation (MOO rejected at 16:00, lifecycle check fails) held for the five non-reject cases; over_limit was not predicted separately and is reported as observed.",
                "Fix round 1 reran the helper with argv recording: identical exit codes, ledgers, analysis results and native states for all 12 launches. One log line differed: the Alpaca adaptive_stress stderr lacked the rejection log line in the rerun (1712 vs 1992 bytes; first-run file retained), while the order-event ledger still recorded the Invalid rejection. Per-case LEAN logs cited are from the rerun, with the machine hostname replaced by $HOSTNAME."],
        raw_outputs=raw(*(["4-lean-report.json", "4-helper.stdout.txt", "4-helper.stderr.txt", "4-helper.exit.txt", "4-helper.started_at.txt",
                           "4-fix1-lean-report.json", "4-fix1-helper.stdout.txt", "4-fix1-helper.stderr.txt", "4-fix1-helper.exit.txt",
                           "4-fix1-helper.started_at.txt", "4-lean-alpaca-adaptive_stress.stderr.first-run.txt",
                           "4-alpaca-variant-HistoricalSimulationAlgorithm.cs"]
                          + [f"4-fix1-lean-{v}-{c}.{s}.txt" for v in ("control", "alpaca") for c in
                             ("compile", "one_zero", "one_stress", "two_zero", "two_stress", "adaptive_stress", "over_limit") for s in ("stdout", "stderr")])))
    R[6] = dict(slug="comparator-modes-and-review-count", outcome="settled", evidence_class="local_integration",
        commands=[ENV_NOTE + "; LEAN=$HOME/.local/share/codex-ecosystem/tools/lean-985ef30/Data; SP=blueprints/us-equities/engine-nautilus/spy-parity",
                  BWRAP_NAUTILUS.format(data="$LEAN", out="$C/spy-parity-run", script="/repo/blueprints/us-equities/engine-nautilus/spy-parity/run.py --lean-data /data --out /out/native"),
                  "python3 $SP/compare.py --receipt $SP/receipt.json --bars $C/spy-parity-run/native/converted-rows.private.json --verdict $C/spy-parity-run/cmp/bars.verdict.json",
                  "python3 $SP/compare.py --receipt $SP/receipt.json --verdict $C/spy-parity-run/cmp/neither.verdict.json",
                  "python3 $SP/compare.py --receipt $SP/receipt.json --lean-data $LEAN --verdict $C/spy-parity-run/cmp/lean-data.verdict.json",
                  "python3 $SP/compare.py --receipt $C/spy-parity-run/native/receipt.json --bars $C/spy-parity-run/native/converted-rows.private.json --verdict $C/spy-parity-run/cmp/bars-fresh-receipt.verdict.json",
                  "sed '0,/\"c\": \"313.0900\"/s//\"c\": \"313.0901\"/' converted-rows.private.json > tampered-rows.json; python3 $SP/compare.py --receipt $SP/receipt.json --bars tampered-rows.json --verdict ...",
                  "git -C $HOME/code/agent-lab show HEAD:docs/tasks/2026-09-22-executed-comparisons.md | sed -n 407,423p",
                  "(fix round 1) python3 -m unittest tests.test_spy_parity -v",
                  "(fix round 1) python3 -m unittest tests.test_nautilus_equity_replay -v",
                  "(fix round 1, per mode) python3 -c \"import json;v=json.load(open(VERDICT));print(v['verdict'],v['complete'],v['failed'],v['blocking_mappings'],v['unattributed_failures'],v['skipped'],v['rejected_attributions'])\""],
        results={"replay": {"exit_code": 0, "stdout": "{\"case\": \"one_zero\", \"dividend_cash_usd\": \"428.64\", \"fills\": 2, \"native_end_cash_usd\": \"90078.96\", \"processed_bars\": 725, \"two_run_records_equal\": true, ...}",
                            "converted_rows_sha256": "6c6fcf4ae2b6d26521d0e0218501d94f7fcfa7571e902309f0f83ac2a68845cc (equals the committed receipt's attribution_evidence value)",
                            "fresh_vs_committed_receipt": "only observed_utc and the raw fills/positions report hashes (generated identities) differ; normalized economic hashes equal"},
                 "modes": {"--bars (fresh rows, committed receipt)": "exit 1, BLOCKED, 25 PASS / 4 FAIL, complete true, unattributed []",
                           "--bars (fresh rows, fresh receipt)": "exit 1, identical verdict bytes",
                           "neither": "exit 1, FAIL, 25 PASS / 4 FAIL / 1 SKIPPED, complete false, 4 unattributed (entry/exit fill price, reconciled and native end cash)",
                           "--lean-data (control)": "exit 1, BLOCKED, identical verdict bytes",
                           "verdict_sha256": {"note": "the two complete modes (--bars, --lean-data) write bytes identical to the committed verdict.json; the incomplete no-evidence verdict differs by design",
                                              "--bars": "b7b898a861492348ae864de25551c127a0367e4638ef5dfa65152f233a6b0d10 (= committed verdict.json)",
                                              "--lean-data": "b7b898a8...0d10", "neither": "64df3ffa097cc9c162941551f0c490c17253806b765dba7b9cd9d841bfc22cf2"},
                           "negative_control": "--bars with a one-digit tampered close: exit 1, ValueError: converted_rows_sha256_mismatch, no verdict written"},
                 "acceptance_set": {"source": "The review excerpt describes five acceptance commands: two unit suites (92 and 8 tests), the verdict line, the comparator re-derivation and the replay; the verbatim five-command list is not retained, so it is reconstructed from that description.",
                                    "test_spy_parity": "Ran 92 tests, OK (exit 0)", "test_nautilus_equity_replay": "Ran 8 tests, OK (exit 0)",
                                    "replay": "run.py exit 0 (above)",
                                    "verdict_lines": {"--bars": "BLOCKED True 4 ['distributions_and_cash', 'market_on_open_proxy'] [] [] []",
                                                      "--bars (fresh receipt)": "BLOCKED True 4 ['distributions_and_cash', 'market_on_open_proxy'] [] [] []",
                                                      "--lean-data": "BLOCKED True 4 ['distributions_and_cash', 'market_on_open_proxy'] [] [] []",
                                                      "neither": "FAIL False 4 [] ['entry_fill.fill_price_usd#12', 'exit_fill.fill_price_usd#16', 'end_cash.reconciled_end_cash_usd#21', 'native_end_cash.native_end_cash_usd#22'] ['attribution_evidence.converted_bars#30'] []"},
                                    "note": "The two unit suites are synthetic fixtures and do not depend on comparator mode, so one run covers every mode; the mode-dependent commands (comparator and verdict line) were run in each mode."},
                 "review_count": "Committed: verbatim excerpt of agent-lab docs/tasks/2026-09-22-executed-comparisons.md lines 407-423 (commit cf714105c3ec1921339343cd3dc949b0893b640e, blob 017df541523f73283239883dfce03bb8d83ffc85) retained as raw/6-agent-lab-parity-final-review-excerpt.md; it records 'Opus verifier: **21/24 claims confirmed, 2 corrected, 1 unverifiable**'. The spy-parity README now points to it and marks review item 5 resolved."},
        remaining=None,
        limits=["Local integration on bundled LEAN sample data (evidence class HIST in the harness); the BLOCKED verdict itself is unchanged and peer-owned.",
                "The converted rows and raw native reports stay private in $HOME/.cache/gap-wave2-20260923/backtesting-engine/spy-parity-run; their sha256 values are recorded.",
                "The review excerpt is a copy of an agent-lab task record; the underlying workflow transcript wf_88f01a45-eeb is not retained here."],
        raw_outputs=raw("6-run.stdout.txt", "6-run.stderr.txt", "6-run.exit.txt", "6-run.started_at.txt", "6-fresh-receipt.json",
                        "6-compare-bars.verdict.json", "6-compare-bars.stdout.txt", "6-compare-bars.stderr.txt", "6-compare-bars.exit.txt",
                        "6-compare-neither.verdict.json", "6-compare-neither.stdout.txt", "6-compare-neither.stderr.txt", "6-compare-neither.exit.txt",
                        "6-compare-lean-data.verdict.json", "6-compare-lean-data.stdout.txt", "6-compare-lean-data.exit.txt",
                        "6-compare-bars-fresh-receipt.verdict.json", "6-compare-bars-fresh-receipt.exit.txt",
                        "6-compare-bars-tampered.stderr.txt", "6-compare-bars-tampered.exit.txt", "6-agent-lab-parity-final-review-excerpt.md",
                        "6-acceptance-test_spy_parity.txt", "6-acceptance-test_nautilus_equity_replay.txt", "6-acceptance-exits.txt",
                        "6-acceptance-verdict-lines.txt", "6-acceptance-started_at.txt"))
    R[7] = dict(slug="one-zero-distributions-fill-rule-peer", outcome="covered_elsewhere", evidence_class="source_review",
        commands=[f"python3 -c \"read {PEER_GATES} gates spy-lean-parity, dividend-sim-module\""],
        results={"spy-lean-parity": "owner peer:sota-workflow-resolution, status blocked",
                 "dividend-sim-module": "owner peer:sota-workflow-resolution, status not_established; closes market_on_open_proxy and distributions_and_cash",
                 "incidental_observation": "The 2026-09-23 fresh replay in gap 6 reproduced native_end_cash 90078.96 and dividend_cash 428.64 unchanged."},
        remaining="Owned by peer:sota-workflow-resolution: post distributions, align the fill-price rule, rerun one_zero and report the delta against -655.12 USD.",
        limits=["No fill rule, distribution posting or manifest change was attempted here (peer-owned; the manifest forbids an invented balancing cash entry)."],
        raw_outputs=raw("6-run.stdout.txt"))
    R[8] = dict(slug="aapl-action-window-replay", outcome="advanced", evidence_class="local_integration",
        commands=R[1]["commands"][:2],
        results={"shared_run": "Same native run as gap 1 (ca_window_replay.py).",
                 "fills": R[1]["results"]["fills"], "account_totals_usd": R[1]["results"]["account_totals_usd"],
                 "position_cash_reconciliation": R[1]["results"]["reconciliation_checks"],
                 "economic_reference": R[1]["results"]["economic_reference"],
                 "fill_basis": "bar-based: market orders filled at the completed daily bar close (liquidity_side TAKER), no quote data."},
        remaining="Quote-based fills: needs a new authenticated Alpaca quote acquisition for AAPL around 2020-08-07/2020-08-31; this wave forbids credential reads, and no retained Alpaca quote payload exists on this host (only the 25 daily bars and 2 action pages in alpaca-run-1).",
        limits=["Unlimited modeled depth remains (default fill model on bars).",
                "Corporate actions are not applied by the engine; the reconciliation proves the native ledger equals a fills-only ledger, and the -3637.00 USD gap to the economic reference is the unhandled split plus the 8.20 USD unposted dividend."],
        raw_outputs=raw("1-8-ca-window-replay-published.json", "1-8-ca-window-replay.stdout.txt", "1-8-ca-window-replay.exit.txt",
                        "1-8-detection-probe.stdout.txt"))
    R[9] = dict(slug="stress-margin-adaptive-parity-peer", outcome="covered_elsewhere", evidence_class="source_review",
        commands=[f"python3 -c \"read {PEER_GATES} gate spy-lean-parity\""],
        results={"spy-lean-parity": "owner peer:sota-workflow-resolution; the one_stress, two_stress, adaptive_stress and over_limit comparisons are its blocked statuses",
                 "incidental_observation": "Gap 4's control run re-executed the LEAN side of all six cases on 2026-09-23 and reproduced the retained end equities (90358.00, 75607.75, 95324.10, 100000); no Nautilus side or comparison was run here."},
        remaining="Owned by peer:sota-workflow-resolution: run the stress and adaptive/margin cases in Nautilus and compare margin and cost outcomes. Realistic liquidity stays unqualified; corporate-action semantics advanced by gaps 1/8 (measured as absent in rc5).",
        limits=["No Nautilus stress or margin replay was attempted (peer-owned parity lane)."],
        raw_outputs=raw("4-lean-report.json"))
    return R


def main():
    G = gaps()
    R = receipts()
    results = {}
    for idx, r in sorted(R.items()):
        pre = PREREG["gaps"][str(idx)]
        text_sha = hashlib.sha256(G[idx]["text"].encode()).hexdigest()
        if text_sha != pre["gap_text_sha256"]:
            raise ValueError(f"gap text changed for {idx}")
        name = f"{idx}-{r['slug']}.json"
        receipt = {"id": f"gap-wave2-20260923/us-equities/backtesting-engine/{idx}-{r['slug']}", "gap_index": idx,
                   "gap_text_sha256": text_sha,
                   "preregistration": {"written_at": PREREG["written_at"], "expectation": pre["expectation"], "criteria": pre["criteria"],
                                       "source": "evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/preregistration.json (committed in 2b93d4d before any check ran)"},
                   "next_check": G[idx]["next_check"], "commands": r["commands"], "results": r["results"],
                   "raw_outputs": r["raw_outputs"], "outcome": r["outcome"], "evidence_class": r["evidence_class"],
                   "remaining": r["remaining"], "limits": r["limits"], "checked_at": NOW}
        fix2 = FIX2["gaps"].get(str(idx))
        if fix2:
            receipt["fix_round_2"] = {"preregistration_written_at": FIX2["written_at"], "label": FIX2["label"],
                                      "expectation": fix2["expectation"], "criteria": fix2["criteria"],
                                      "source": "evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/preregistration-fix2.json (committed in e1fa1b3 before the fix-round-2 run)"}
        fix = FIX1["gaps"].get(str(idx))
        if fix:
            receipt["fix_round_1"] = {"preregistration_written_at": FIX1["written_at"], "label": FIX1["label"],
                                      "expectation": fix["expectation"], "criteria": fix["criteria"],
                                      "source": "evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/preregistration-fix1.json (committed in 43a2f90 before the fix-round runs)"}
        if r["outcome"] == "covered_elsewhere":
            receipt["covered_by"] = {"owner": "peer:sota-workflow-resolution", "gate_file": PEER_GATES,
                                     "rule": "SPY/LEAN parity and the dividend sim module are covered_elsewhere under the peer's preregistration (unit brief)."}
        (LAYER / name).write_text(json.dumps(receipt, indent=2) + "\n")
    # results.json derived from the receipts on disk
    for p in sorted(LAYER.glob("[0-9]*-*.json"), key=lambda p: int(p.name.split("-")[0])):
        d = json.loads(p.read_text())
        results[str(d["gap_index"])] = {"outcome": d["outcome"], "receipt": p.name}
    (LAYER / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
