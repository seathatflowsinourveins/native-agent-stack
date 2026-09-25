"""Re-check the committed 2026-09-24 macOS paper artifacts (stdlib, offline, read-only).

Checks trial a (pass, cancel-replace, reconciliation, rate ceilings, P&L agreement),
the STOP drill b (no intent or submit after STOP, working entry canceled unfilled,
recover flat, release conditions), the native-faults receipt, and that the frozen
file hashes match a fresh `git archive` of 6f7a77c. Prints one short line per part and
exits 1 on the first failed check. It never contacts the broker or reads credentials.
Run from the repository root: python3 <this file>
"""
import io
import json
import subprocess
import sys
import tarfile
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

TRIALS = Path("blueprints/us-equities/adaptive-paper/trials")
A, B, N = (TRIALS / name for name in ("mac-2026-09-24-a-passed", "mac-2026-09-24-b-stop-drill",
                                       "mac-2026-09-24-native-faults"))
CONFIG_SHA = "3587653104e68fdfc9bbb9170825c611abcf7e2e1be1004327a056031c34555a"


def load(path):
    return json.loads(path.read_text())


def check(ok, what):
    if not ok:
        print("FAILED:", what)
        sys.exit(1)


def reconciled(rec):
    return (rec and rec["cash_match"] is True and rec["positions_match"] is True
            and rec["open_orders"] == 0 and rec["positions"] == 0)


def peak(times, window=60.0):
    times = sorted(times)
    return max((sum(1 for t in times if s <= t < s + window) for s in times), default=0)


def trial_a():
    out, led, pre = load(A / "paper-output.json"), load(A / "ledger-readback.json"), load(A / "preflight.json")
    check(pre["status"] == "ready" and pre["open_order_count"] == 0 and pre["position_count"] == 0
          and pre["endpoint"] == "https://paper-api.alpaca.markets", "a: preflight ready, paper, flat and idle")
    check(out["status"] == "passed" and out["flat"] is True and out["feed"] == "sip"
          and out["config_sha256"] == CONFIG_SHA and out["elapsed_seconds"] >= 300, "a: passed, flat, sip, frozen config")
    check(reconciled(out["reconciliation"]) and not out["adapter_errors"] and out["native_rejections"] == 0,
          "a: reconciled flat, no adapter errors or rejections")
    kinds = Counter(r["kind"] for r in out["requests"])
    submits = [r["timestamp"] for r in out["requests"] if r["kind"] == "submit"]
    trading = [r["timestamp"] for r in out["requests"] if r["kind"] != "data_read"]
    check(peak(submits) <= 180 and peak(trading) <= 200, "a: request ceilings 180 submits / 200 total per 60 s")
    intents = led["intents"]
    check(kinds["submit"] == len(intents) == sum(1 for e in out["events"] if e["type"] == "intent"),
          "a: every submit has one journaled intent")
    check(all(Decimal(i["qty"]) == 1 for i in intents), "a: one-share orders")
    replaced = 0
    for n, intent in enumerate(intents):
        if intent["status"] == "canceled":
            check(Decimal(intent["filled_qty"]) == 0, "a: canceled order unfilled")
            check(any(j["symbol"] == intent["symbol"] and j["side"] == intent["side"] and j["status"] == "filled"
                      for j in intents[n + 1:]), "a: canceled order replaced and filled")
            replaced += 1
    check(replaced >= 1 and kinds["cancel"] == replaced == led["request_reservations"]["cancel"]["count"],
          "a: cancel-replace observed and every cancel attributed")
    totals, acct = led["totals"], out["accounting"]
    check(totals["unpaired_filled_buys"] == 0 and totals["filled_buys"] == totals["filled_sells"]
          and totals["filled_buys"] + totals["filled_sells"] == out["native_fill_events"], "a: fills pair into round trips")
    check(Decimal(totals["round_trip_pnl_usd"]) == Decimal(acct["realized_pnl_usd"])
          == Decimal(out["reconciliation"]["cash_delta_usd"]), "a: round trips = ledger realized = broker cash delta")
    print("a: passed flat; %d submits %d cancels %d fills %d round trips %d cancel-replace; peak/60s %d/%d; "
          "realized %s" % (kinds["submit"], kinds["cancel"], out["native_fill_events"], totals["round_trips"],
                           replaced, peak(submits), peak(trading), acct["realized_pnl_usd"]))


def drill_b():
    trig, out, led = load(B / "stop-drill-trigger.json"), load(B / "paper-output.json"), load(B / "ledger-readback.json")
    rec, rel = load(B / "recover-output.json"), load(B / "stop-release.json")
    stop = trig["stop_created_epoch"]
    check(trig["trigger"] == "first_buy_intent", "b: STOP triggered by the first buy intent")
    events = [json.loads(line) for line in (B / "events.jsonl").read_text().splitlines()]
    check(not [e for e in events if e["type"] == "intent" and e["at"] > stop], "b: no intent after STOP")
    check(not [r for r in out["requests"] if r["kind"] == "submit" and r["timestamp"] > stop], "b: no submit after STOP")
    cancels = [r["timestamp"] for r in out["requests"] if r["kind"] == "cancel"]
    check(len(cancels) == 1 and cancels[0] > stop, "b: one cancel, sent after STOP")
    (entry,) = led["intents"]
    check(entry["side"] == "buy" and entry["status"] == "canceled" and Decimal(entry["filled_qty"]) == 0
          and "new" in [o["status"] for o in entry["observed"]], "b: working entry canceled unfilled")
    check(out["flat"] is True and reconciled(out["reconciliation"]) and out["elapsed_seconds"] < 300,
          "b: run ended early, flat and reconciled")
    check(rec["status"] == "passed" and rec["flat"] is True and not rec["unresolved_orders"]
          and rec["buy_submissions"] == 0 and reconciled(rec["reconciliation"]), "b: recover passed flat")
    check(all(rel["conditions"].values()), "b: STOP released only after both conditions")
    print("b: STOP +%.1f ms after intent, cancel +%.0f ms; 0 intents/submits after; ended %.1f s; recover %s flat"
          % (trig["stop_after_intent_ms"], (cancels[0] - stop) * 1000, out["elapsed_seconds"], rec["status"]))


def faults():
    r = load(N / "receipt.json")
    cases = {c["id"]: (c["outcome"], c["evidence_class"]) for c in r["cases"]}
    check(r["status"] == "native_faults_incomplete" and r["cleanup"]["flat"] is True
          and r["cleanup"]["broker_open_orders"] == 0 and r["posts_reserved"] == 1, "faults: incomplete, cleaned flat")
    check(cases == {"C01": ("passed", "native_paper"), "C02": ("passed", "native_paper"),
                    "C05": ("passed", "engine_short_circuit"), "C04": ("unobserved", "none")}, "faults: case outcomes")
    print("faults: C01 C02 native_paper; C05 short-circuit; C04 unobserved; flat")


def frozen():
    expected = {}
    for line in (A / "frozen-6f7a77c.SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        expected[name[2:]] = digest
    archive = subprocess.run(["git", "archive", "6f7a77c", "--", "blueprints/us-equities",
                              ":(exclude)blueprints/us-equities/mover-v3"], check=True, capture_output=True).stdout
    actual = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            if member.isfile():
                actual[member.name] = sha256(tar.extractfile(member).read()).hexdigest()
    check(actual == expected, "frozen: SHA256SUMS equal git archive 6f7a77c")
    print("frozen: %d files match git archive 6f7a77c" % len(actual))


if __name__ == "__main__":
    trial_a()
    drill_b()
    faults()
    frozen()
    print("all checks passed")
