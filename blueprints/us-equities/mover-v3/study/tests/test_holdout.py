"""The holdout path through run.py on a frozen temporary repository (review round 9, H-1, F4, M-5 and M-6):
authorization records written by rule and required before each action, collection batches with different
enumerations and a rename-day re-fetch merged per (symbol, session), N0 and the window taken from the freeze commit,
counts with the extension decision, the read of the carried items only, and the not-read label after the deadline.
Every number is synthetic; no network call."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run
from core import gate, guards, holdout, logs, plan, runner
from core.canon import sha256_file
from core.params import ACCESS_LOG, RESULTS_DIR, RUN_LOG
from core.store import Store
from tests import fixture_repo as FR
from tests import synth
from tests.test_identity import transports

EVENT_T = "2027-02-01"        # AAA's holdout event
CCC_T = "2026-11-02"          # CCC's event, before N0 (a lookback session only)


def market(cal, rename_day):
    m = synth.FakeMarket(cal, page_size={"bars": 20000, "auctions": 20000, "quotes": 50})
    first, last = "2024-09-03", "2028-12-29"
    for k, (sym, names, t) in enumerate((("AAA", [("2015-01-01", "AAA")], EVENT_T),
                                         ("BBB", [("2015-01-01", "BBB")], None),
                                         ("OLD", [("2015-01-01", "OLDN"), (rename_day, "NEWN")], None),
                                         ("CCC", [("2015-01-01", "CCC")], CCC_T))):
        def close_fn(d, t=t, k=k):
            return (10.0 + k) * (1.3 if t and d >= t else 1.0)
        raw, split, allc = synth.series(cal, first, last, close_fn, volume=3_000_000)
        minute, quotes = [], []
        if t:
            for d in cal.range(cal.offset(t, -19), cal.offset(t, 8)):
                minute += synth.minute_rows(cal, d, close_fn(d), 50_000, start="04:00", n=16 * 60)
            for d in cal.range(cal.offset(t, 1), cal.offset(t, 8)):
                for hhmm in ("09:35", "15:55"):
                    quotes.append(synth.quote(cal.at(d, hhmm) - 0.2, close_fn(d) * 0.999, close_fn(d) * 1.001))
        m.add(sym, names, daily={"raw": raw, "split": split, "all": allc}, auctions=synth.prints_from(raw),
              minute=minute, quotes=quotes)
    m.assets = [{"symbol": s, "status": "active", "class": "us_equity"} for s in ("AAA", "BBB", "OLDN")]
    return m


class HoldoutPath(unittest.TestCase):
    def test_collect_count_extend_and_read_through_run_py(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            with FR.isolated_bytecode():
                ctx = runner.context(repo)
            cal = ctx["cal"]
            self.assertEqual((ctx["freeze_session"], ctx["n0_pinned"]), ("2026-10-05", cal.offset("2026-10-05", 40)))
            n0 = ctx["n0_pinned"]
            b1_last = "2026-12-31"
            m = market(cal, rename_day=b1_last)
            clock_now = {"t": cal.at("2026-10-05", "12:00")}

            def push(t=None):
                """Commit and push at t (the clock by default); the next run's clock is 60 s later."""
                t = clock_now["t"] if t is None else t
                FR.commit_push(repo, FR.git_date(t))
                clock_now["t"] = t + 60

            # the governing validation results, committed before 09:30 ET on N0 (carries H3-a and H3-c)
            val = {"labels": {"H1-D": "underpowered", "H1-D-b_lane-low": "underpowered", "H3-a": "screened",
                              "H3-b": "underpowered", "H3-c": "screened"},
                   "items": {i: {"p_stage": 1.0} for i in ("H1-D", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c")}}
            val["items"]["H3-c"]["estimate"] = 0.004
            val["items"]["H3-a"]["p_stage"] = val["items"]["H3-c"]["p_stage"] = 0.01
            FR.write(repo / RESULTS_DIR / "validation.json", json.dumps(val))
            logs.append_line(repo / RUN_LOG, {"stage": "validation", "purpose": "evaluate", "status": "complete",
                                              "results_sha256": sha256_file(repo / RESULTS_DIR / "validation.json"),
                                              "study_tree": fx["tree"], "protocol_sha256": fx["protocol_sha256"]})
            FR.commit_push(repo, "2026-11-20T12:00:00+00:00")

            def main(*argv):
                with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                        mock.patch.object(run, "transports", lambda: transports(m)), \
                        mock.patch.object(run, "now", lambda: clock_now["t"]), \
                        mock.patch.object(run, "clock", lambda: FR.git_date(clock_now["t"])[:19] + "Z"):
                    return run.main(list(argv))

            def access():
                return logs.read_lines(repo / ACCESS_LOG)

            accrual = Path(tmp) / "accrual.json"
            accrual.write_text("[]")

            def collect(last, exposed=()):
                accrual.write_text(json.dumps([{"symbol": s, "session": d, "order_id": "x", "strategy": "paper"}
                                               for s, d in exposed]))
                push(cal.at(last, "20:00"))
                main("authorize", "--purpose", "collect")
                aid = access()[-1]["authorization_id"]
                self.assertEqual(access()[-1]["decision"], "granted")
                with self.assertRaises(guards.Refused):        # the authorization is not yet pushed
                    main("collect", "--authorization", aid, "--last", last, "--accrual-log", str(accrual),
                         "--snapshot-root", root)
                push()
                self.assertEqual(main("collect", "--authorization", aid, "--last", last, "--accrual-log",
                                      str(accrual), "--snapshot-root", root), 0)
                self.assertEqual(access()[-1]["record_kind"], "completion")
                push()
                return aid

            # batch 1: the freeze session .. 2026-12-31, enumerating AAA, BBB and OLDN (renamed to NEWN that day)
            m.actions = []
            collect(b1_last)
            # batch 2 onward: CCC is listed and the rename record is retained; the batch re-fetches NEWN's rows of
            # the rename day, and CCC's earlier sessions are in no batch
            m.assets += [{"symbol": "CCC", "status": "active", "class": "us_equity"},
                         {"symbol": "NEWN", "status": "active", "class": "us_equity"}]
            m.actions = [{"type": "name_change", "old_symbol": "OLDN", "new_symbol": "NEWN", "process_date": b1_last}]
            _, last0 = holdout.window(ctx, 0)
            # a count before the end of the window is refused by rule, and the refusal is logged
            push(cal.at(cal.offset(last0, -1), "20:00"))
            main("authorize", "--purpose", "count")
            self.assertEqual(access()[-1]["decision"], "refused")
            push()
            collect(last0, exposed=[("AAA", EVENT_T)])
            # review round 10, M2: a clock set back below origin/main's tip time is refused
            clock_now["t"] -= 3600
            with self.assertRaisesRegex(guards.Refused, "earlier than origin/main's tip"):
                main("authorize", "--purpose", "count")
            clock_now["t"] += 3600

            def count(last, check_redraw=False):
                push(cal.at(last, "20:30"))
                main("authorize", "--purpose", "count")
                a = access()[-1]
                self.assertEqual((a["decision"], a["requested_items"]), ("granted", ["H3-a", "H3-c"]), a)
                push()
                # review round 10, H2: step 1 fetches and seals only; no results file and no completion yet
                before = sorted((repo / RESULTS_DIR).glob("holdout-count-*.json"))
                main("count", "--authorization", a["authorization_id"], "--snapshot-root", root)
                step1 = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((step1["purpose"], step1["status"]), ("count_fetch", "complete"))
                self.assertEqual(sorted((repo / RESULTS_DIR).glob("holdout-count-*.json")), before)
                self.assertEqual(access()[-1]["record_kind"], "authorization")
                with self.assertRaises(guards.Refused):        # step 2 needs step 1's line on origin/main
                    main("count", "--authorization", a["authorization_id"], "--snapshot-root", root)
                push()
                calls = len(m.calls)
                main("count", "--authorization", a["authorization_id"], "--snapshot-root", root)
                self.assertEqual(len(m.calls), calls)          # step 2 makes no request
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual(line["input_snapshot_sha256s"], step1["input_snapshot_sha256s"])
                self.assertGreater(access()[-1]["rows_read"], 0)            # F13
                self.assertIsNotNone(line["validation_results_reach_utc"])   # F13
                if check_redraw:
                    # discarding step 2's unpushed outputs and running again yields the same bytes from the same
                    # pushed snapshot, and no new provider data
                    path = repo / RESULTS_DIR / f"holdout-count-{line['block']}.json"
                    first = path.read_bytes()
                    FR.sh(repo, "checkout", "--", RUN_LOG, ACCESS_LOG)
                    path.unlink()
                    main("count", "--authorization", a["authorization_id"], "--snapshot-root", root)
                    self.assertEqual(path.read_bytes(), first)
                    self.assertEqual(len(m.calls), calls)
                push()
                return a["authorization_id"], logs.read_lines(repo / RUN_LOG)[-1]

            aid0, line0 = count(last0, check_redraw=True)
            self.assertEqual(line0["sessions"], [n0, last0])
            body0 = json.loads((repo / RESULTS_DIR / "holdout-count-0.json").read_text())
            self.assertEqual(set(body0["counts"]), {"H1-D:high", "H1-D:low", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c"})
            self.assertEqual(body0["counts"]["H3-a"], 1)
            self.assertTrue(body0["extension"]["extend"])
            # M-6: CCC's screen rows of batch-1 sessions were fetched by the count (asof = s); NEWN's rename-day
            # rows came from batch 2's re-fetch, and AAA's holdout sessions from the batches
            sealed = Store.read(Path(root) / f"count-{aid0}", line0["input_snapshot_sha256s"][0])
            screened = {(x, r["asof_session"]) for r in sealed.req.values() if r["kind"] == "screen_daily_raw"
                        for x in r["params"]["symbols"].split(",")}
            self.assertIn(("CCC", n0), screened)
            self.assertIn(("NEWN", n0), screened)
            self.assertNotIn(("NEWN", b1_last), screened)
            self.assertFalse(any(x in ("AAA", "BBB") and s >= cal.offset(n0, -1) for x, s in screened))
            self.assertTrue(all(r["params"]["asof"] == r["asof_session"] for r in sealed.req.values()
                                if r["kind"].startswith("screen")))
            # M-5: the window grows by 63 sessions from the committed extension decision only
            _, last1 = holdout.window(runner_ctx(repo), 1)
            self.assertEqual(len(cal.range(n0, last1)), 315)
            collect(last1)
            count(last1)
            _, last2 = holdout.window(runner_ctx(repo), 2)
            collect(last2)
            _, line2 = count(last2)
            self.assertEqual(line2["extension"]["extend"], False)
            self.assertEqual(line2["extension"]["underpowered"], ["H3-a", "H3-c"])
            # the read is not authorized before the terminal-search windows end; then it is granted by rule
            push(cal.at(cal.offset(last2, 2), "20:00"))
            with self.assertRaises(holdout.HoldoutRefused):
                main("authorize", "--purpose", "read")
            push(cal.at(cal.offset(last2, 6), "20:00"))
            main("authorize", "--purpose", "read")
            rid = access()[-1]["authorization_id"]
            push()
            with mock.patch.object(holdout.STG, "evaluate_stage", lambda *a, **k: ORIG_EVAL(*a, **{**k, "B": 200})):
                main("read", "--authorization", rid, "--snapshot-root", root)     # step 1: fetch and seal
                self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())
                self.assertEqual(logs.read_lines(repo / RUN_LOG)[-1]["purpose"], "read_fetch")
                push()
                main("read", "--authorization", rid, "--snapshot-root", root)     # step 2: the read
            res = json.loads((repo / RESULTS_DIR / "holdout-read.json").read_text())
            # M-1: only the carried items are computed; the others have no estimate and are 'not carried'
            for i in ("H1-D", "H1-D-b_lane-low", "H3-b"):
                self.assertEqual(res["labels"][i], "not carried")
                self.assertNotIn("estimate", res["items"][i])
            self.assertNotIn("H1", res["verdicts"])        # review round 10, F8: no carried H1 item, no H1 verdict
            self.assertEqual(res["items"]["H3-a"]["n"], 1)
            self.assertEqual(res["items"]["H3-a"]["paper_exposed_fraction"], 1.0)    # the accrual log's order
            self.assertEqual(res["labels"]["H3-a"], "underpowered")
            self.assertNotIn("b_lane:filled", res["counts"]["trades_by_arm_status"])
            self.assertEqual(access()[-1]["record_kind"], "completion")
            push()
            with self.assertRaises(holdout.HoldoutRefused):          # the holdout is read once
                main("read", "--authorization", rid, "--snapshot-root", root)


ORIG_EVAL = holdout.STG.evaluate_stage


def runner_ctx(repo):
    with FR.isolated_bytecode():
        return runner.context(repo)


class NotRead(unittest.TestCase):
    def test_after_the_deadline_every_carried_item_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            logs.append_line(repo / RUN_LOG, {"utc_start": "2027-12-10T00:00:00Z", "stage": "holdout",
                                              "purpose": "count", "status": "complete",
                                              "results_sha256": "c" * 64, "block": 0, "sessions": [ctx["n0_pinned"], last],
                                              "extension": {"extend": False, "below_minimum": [], "underpowered": []},
                                              "void": False})
            logs.append_line(repo / ACCESS_LOG, {"utc": "x", "record_kind": "authorization", "authorization_id":
                                                 "read-001", "purpose": "read", "decision": "granted", "refusal": None,
                                                 "requested_items": ["H3-a"], "retry_of": None})
            FR.commit_push(repo, "2027-12-20T00:00:00+00:00")
            ctx = runner_ctx(repo)
            late = ctx["cal"].close(ctx["cal"].offset(last, 16))
            out = holdout.read(ctx, "read-001", str(Path(tmp) / "snap"), {}, late)
            self.assertFalse(out["read"])
            body = json.loads((repo / RESULTS_DIR / "holdout-read.json").read_text())
            self.assertEqual(body["labels"]["H3-a"], "not supported (holdout not read)")
            self.assertEqual(body["labels"]["H3-c"], "not carried")
            self.assertEqual(body["verdicts"]["H3"]["verdict"], "not supported (holdout not read)")
            self.assertEqual(logs.read_lines(repo / ACCESS_LOG)[-1]["record_kind"], "completion")

    def test_refused_read_and_missing_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            ctx = runner_ctx(repo)
            # no validation results: the read authorization is refused by rule, and the read writes the fixed label
            g = holdout.gate_context(ctx, "count", ctx["cal"].at("2027-12-10", "20:00"))
            refusals = gate.evaluator_refusals(g)
            self.assertTrue(any("validation results file is missing" in r for r in refusals))
            self.assertTrue(any("validated items" in r for r in refusals))
            # a granted count with no collection batch is refused before any fetch
            logs.append_line(repo / ACCESS_LOG, {"utc": "x", "record_kind": "authorization", "authorization_id":
                                                 "count-001", "purpose": "count", "decision": "granted", "refusal": None,
                                                 "requested_items": ["H3-a"], "retry_of": None})
            _, last = holdout.window(ctx, 0)
            t0 = ctx["cal"].close(last) - 3 * 86400
            FR.commit_push(repo, FR.git_date(t0))
            with self.assertRaises(holdout.HoldoutRefused):
                holdout.count(runner_ctx(repo), "count-001", str(Path(tmp) / "snap"), {}, t0 + 60)
            logs.append_line(repo / ACCESS_LOG, gate.completion("count-001", "x", "failed", None, 0, None, []))
            FR.commit_push(repo, FR.git_date(t0 + 120))
            # with no final count, the read is authorized only after the deadline; refused by rule (no validated
            # item), it still writes the fixed not-read result (chronology.holdout.read_timing)
            ctx = runner_ctx(repo)
            with self.assertRaises(holdout.HoldoutRefused):
                holdout.authorize(ctx, "read", ctx["cal"].close(last))
            late = ctx["cal"].close(ctx["cal"].offset(last, 16))
            rec = holdout.authorize(ctx, "read", late)
            self.assertEqual(rec["decision"], "refused")
            FR.commit_push(repo, FR.git_date(late + 60))
            out = holdout.read(runner_ctx(repo), rec["authorization_id"], str(Path(tmp) / "snap"), {}, late + 120)
            self.assertFalse(out["read"])
            self.assertTrue(out["reason"].startswith("refused: "))
            # review round 10, F8: nothing validated, so the holdout is never labelled
            body = json.loads((repo / RESULTS_DIR / "holdout-read.json").read_text())
            self.assertNotIn("labels", body)
            self.assertNotIn("verdicts", body)
            self.assertIn("no_holdout", body)

    def test_a_read_authorization_that_reached_main_after_the_deadline_is_not_read(self):
        # review round 10, M2: the deadline is judged by the authorization's recorded reach time, so a clock set
        # back cannot make a late read timely
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {"utc_start": "2027-12-10T00:00:00Z", "stage": "holdout",
                                              "purpose": "count", "status": "complete",
                                              "results_sha256": "c" * 64, "block": 0, "sessions": [ctx["n0_pinned"], last],
                                              "extension": {"extend": False, "below_minimum": [], "underpowered": []},
                                              "void": False})
            FR.commit_push(repo, FR.git_date(deadline - 7200))
            logs.append_line(repo / ACCESS_LOG, {"utc": "x", "record_kind": "authorization", "authorization_id":
                                                 "read-001", "purpose": "read", "decision": "granted", "refusal": None,
                                                 "requested_items": ["H3-a"], "retry_of": None})
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with self.assertRaises(guards.Refused):          # a clock before the tip commit
                holdout.read(runner_ctx(repo), "read-001", str(Path(tmp) / "snap"), {}, deadline - 3600)
            out = holdout.read(runner_ctx(repo), "read-001", str(Path(tmp) / "snap"), {}, deadline + 120)
            self.assertFalse(out["read"])
            self.assertTrue(out["reason"].startswith("not completed"))


class Collection(unittest.TestCase):
    def test_late_batches_and_plan(self):
        cal = synth.calendar("2026-06-01", "2027-06-30")
        b = [{"sessions": cal.range("2026-10-05", "2026-10-09"), "reachable": cal.at("2026-10-12", "09:31")}]
        self.assertEqual(plan.late_collected(cal, b), cal.range("2026-10-05", "2026-10-09"))


if __name__ == "__main__":
    unittest.main()
