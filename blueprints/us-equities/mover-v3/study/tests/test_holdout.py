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
from core.params import ACCESS_LOG, DEVIATIONS, RESULTS_DIR, RUN_LOG
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
                        mock.patch.object(run, "transports", lambda *_: transports(m)), \
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
            # review round 13, F1 and Codex P2: void deviations recorded after the gate opened (a holdout-window read
            # found late, as after watching paper results, and a validation read) cannot cancel the read; before the
            # fix the 'holdout' one turned it into the not-read label and the 'validation' one was ignored
            from core.calendar import iso_utc
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [
                {"number": 1, "kind": "void", "scope": "holdout", "cause": "synthetic: a read found late",
                 "read_utc": iso_utc(cal.at(n0, "12:00"))},
                {"number": 2, "kind": "void", "scope": "validation", "cause": "synthetic: a read found late"}]}))
            push()
            pinned_ctx = runner_ctx(repo)
            self.assertEqual(pinned_ctx["voids"], frozenset())
            main("read", "--authorization", rid, "--snapshot-root", root)     # step 1: fetch and seal
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())
            fetch_line = logs.read_lines(repo / RUN_LOG)[-1]
            self.assertEqual(fetch_line["purpose"], "read_fetch")
            # review round 12, Codex P2: the fetch line pins the ordered base snapshots and collection batches
            self.assertEqual(len(fetch_line["collection_batches"]), 4)
            self.assertEqual(fetch_line["base_snapshots"], [list(r) for r in holdout.sealed_refs(pinned_ctx)])
            push()

            def boom(*a, **k):
                raise RuntimeError("synthetic failure after the seal")
            with mock.patch.object(holdout.STG, "evaluate_stage", boom), self.assertRaises(RuntimeError):
                main("read", "--authorization", rid, "--snapshot-root", root)     # step 2 fails after the seal
            self.assertEqual((access()[-1]["record_kind"], access()[-1]["status"]), ("completion", "failed"))
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())
            push()
            # Codex P2: a collection batch completed after the seal enumerates a new symbol; it must not reach the
            # retry's plan or rows (before the fix the retry needed unsealed screen requests for DDD)
            m.assets += [{"symbol": "DDD", "status": "active", "class": "us_equity"}]
            collect(cal.offset(last2, 8))
            # F1 (second review): the retry comes after the read deadline; a sealed read is still evaluated
            deadline = holdout.read_deadline(runner_ctx(repo), last2)
            push(cal.at(cal.offset(last2, 16), "20:00"))
            self.assertGreater(clock_now["t"], deadline)
            main("authorize", "--purpose", "read", "--retry-of", rid)
            self.assertEqual(access()[-1]["decision"], "granted", access()[-1])
            rid2 = access()[-1]["authorization_id"]
            push()
            calls, seen = len(m.calls), {}

            def evaluate_b200(*a, **k):
                seen["signs"] = k.get("validation_signs")
                return ORIG_EVAL(*a, **{**k, "B": 200})
            with mock.patch.object(holdout.STG, "evaluate_stage", evaluate_b200):
                main("read", "--authorization", rid2, "--snapshot-root", root)    # step 2 of the retry: the read
            # review round 12, F2: the validation file's H3-c estimate sets the sign the holdout H3-c must have
            self.assertEqual(seen["signs"], {"H3-c": 0.004})
            self.assertEqual(len(m.calls), calls)                                   # no new provider data
            res = json.loads((repo / RESULTS_DIR / "holdout-read.json").read_text())
            self.assertEqual(res["input_snapshot_sha256"], fetch_line["input_snapshot_sha256s"][0])
            # M-1: only the carried items are computed; the others have no estimate and are 'not carried'
            for i in ("H1-D", "H1-D-b_lane-low", "H3-b"):
                self.assertEqual(res["labels"][i], "not carried")
                self.assertNotIn("estimate", res["items"][i])
            self.assertNotIn("H1", res["verdicts"])        # review round 10, F8: no carried H1 item, no H1 verdict
            self.assertEqual(res["items"]["H3-a"]["n"], 1)
            self.assertEqual(res["items"]["H3-a"]["paper_exposed_fraction"], 1.0)    # the accrual log's order
            # review round 11, C8: the holdout's untouched status names its failed conditions; round 13: the late voids
            self.assertEqual(res["holdout_label"][-1], "paper-exposed fraction above 0.05: H3-a, H3-c")
            self.assertEqual(len(res["holdout_label"]), 3)
            self.assertTrue(all("reported, not applied" in x for x in res["holdout_label"][:2]))
            self.assertEqual([(v["number"], v["scope"]) for v in res["voids_late"]], [(1, "holdout"), (2, "validation")])
            # Codex P2 (round 13): the read's line records the dates whose fee rows its exits can use; review round
            # 15 (fee-date item): through the T+1 settlement date of its last sale session, last + 5
            reads = [x for x in logs.read_lines(repo / RUN_LOG) if x.get("purpose") == "read"]
            self.assertEqual([x["fee_span"] for x in reads], [[n0, cal.offset(last2, 6)]] * 2)
            self.assertEqual((res["late_read"], res["void_after_seal"]), (True, []))     # F1; late: the retry
            self.assertEqual(res["labels"]["H3-a"], "underpowered")
            self.assertNotIn("b_lane:filled", res["counts"]["trades_by_arm_status"])
            self.assertEqual(access()[-1]["record_kind"], "completion")
            push()
            with self.assertRaises((holdout.HoldoutRefused, gate.NoAuthorization)):   # the holdout is read once
                main("read", "--authorization", rid2, "--snapshot-root", root)


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
            write_validation(repo, fx)
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "granted"))
            # review round 11, F1: an authorization that reached main after the deadline and sealed nothing
            late = ctx["cal"].close(ctx["cal"].offset(last, 16))
            FR.commit_push(repo, FR.git_date(late))
            ctx = runner_ctx(repo)
            out = holdout.read(ctx, "read-001", str(Path(tmp) / "snap"), {}, late + 60)
            self.assertFalse(out["read"])
            body = json.loads((repo / RESULTS_DIR / "holdout-read.json").read_text())
            self.assertEqual(body["labels"]["H3-a"], "not supported (holdout not read)")
            self.assertEqual(body["labels"]["H3-c"], "not carried")
            self.assertEqual(body["verdicts"]["H3"]["verdict"], "not supported (holdout not read)")
            self.assertEqual(logs.read_lines(repo / ACCESS_LOG)[-1]["record_kind"], "completion")

    def test_carried_items_must_equal_the_validated_items_at_the_read(self):
        """Review round 12, F1: read() and count() recheck the authorization's items against the governing
        validation file; a committed record listing a strict subset, or a malformed record, is refused."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [ctx["n0_pinned"], last]})
            write_validation(repo, fx, screened=("H3-a", "H3-c"))
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "granted", items=("H3-a",),
                                                         val=validation_sha(("H3-a", "H3-c"))))
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "not the validated items"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 120)
            logs.append_line(repo / ACCESS_LOG, gate.completion("read-001", "x", "failed", None, 0, None, []))
            logs.append_line(repo / ACCESS_LOG, auth_rec("count-002", "count", "granted", items=("H3-c",),
                                                         val=validation_sha(("H3-a", "H3-c"))))
            FR.commit_push(repo, FR.git_date(deadline + 180))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "not the validated items"):
                holdout.count(runner_ctx(repo), "count-002", root, {}, deadline + 240)
            logs.append_line(repo / ACCESS_LOG, gate.completion("count-002", "x", "failed", None, 0, None, []))
            bad = {k: v for k, v in auth_rec("read-003", "read", "granted", items=("H3-a", "H3-c")).items()
                   if k not in ("code_revision", "study_code_tree")}
            logs.append_line(repo / ACCESS_LOG, bad)
            FR.commit_push(repo, FR.git_date(deadline + 300))
            with self.assertRaisesRegex(gate.NoAuthorization, "malformed"):
                holdout.read(runner_ctx(repo), "read-003", root, {}, deadline + 360)
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())

    def test_a_read_result_left_by_a_hard_kill_is_recomputed(self):
        """Review round 14, Codex P2: holdout-read.json written but its run-log line lost to a hard kill is not
        final; the rerun recomputes the same bytes, replaces it and logs it. Once a line cites it, the read is final."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [ctx["n0_pinned"], last]})
            write_validation(repo, fx)
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "granted"))
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with mock.patch.object(logs, "append_line", side_effect=SystemError("power loss")):
                with self.assertRaises(SystemError):
                    holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 120)
            path = repo / RESULTS_DIR / "holdout-read.json"
            orphan = sha256_file(path)
            out = holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 180)
            self.assertEqual(out["results_sha256"], orphan)
            line = logs.read_lines(repo / RUN_LOG)[-1]
            self.assertEqual((line["results_sha256"], line["replaced_uncited_results_sha256"]), (orphan, orphan))
            FR.commit_push(repo, FR.git_date(deadline + 240))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "read once"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 300)

    def test_the_validation_file_is_bound_at_authorization(self):
        """Review round 14, Codex P1: a count or read refuses when the working validation file differs from the
        sha256 its authorization recorded (a local edit of the H3-c estimate's sign after the gate opened), and when
        the authorization bound other bytes than the governing run-log line names; nothing is written."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [ctx["n0_pinned"], last]})
            bound = write_validation(repo, fx, screened=("H3-a", "H3-c"))
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "granted", items=("H3-a", "H3-c"),
                                                         val=bound))
            FR.commit_push(repo, FR.git_date(deadline + 60))
            path = repo / RESULTS_DIR / "validation.json"
            body = json.loads(path.read_text())
            body["items"]["H3-c"]["estimate"] = -0.5        # the sign the read's H3-c pass uses
            path.write_text(json.dumps(body))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "changed after the authorization"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 120)
            with self.assertRaisesRegex(holdout.HoldoutRefused, "changed after the authorization"):
                holdout.require_validated_carried(runner_ctx(repo), auth_rec("count-009", "count", "granted",
                                                                            items=("H3-a", "H3-c"), val=bound))
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())
            # the committed bytes restored: the bound read goes ahead (here to the not-read label, as the
            # authorization reached origin/main after the deadline)
            FR.write(path, validation_body(("H3-a", "H3-c")).decode("utf-8"))
            out = holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 180)
            self.assertFalse(out["read"])
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [ctx["n0_pinned"], last]})
            write_validation(repo, fx)
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "granted", val="f" * 64))
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "changed after the authorization"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 120)
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())

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
            logs.append_line(repo / ACCESS_LOG, auth_rec("count-001", "count", "granted", items=()))
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
            write_validation(repo, fx)
            FR.commit_push(repo, FR.git_date(deadline - 7200))
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "granted"))
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with self.assertRaises(guards.Refused):          # a clock before the tip commit
                holdout.read(runner_ctx(repo), "read-001", str(Path(tmp) / "snap"), {}, deadline - 3600)
            out = holdout.read(runner_ctx(repo), "read-001", str(Path(tmp) / "snap"), {}, deadline + 120)
            self.assertFalse(out["read"])
            self.assertTrue(out["reason"].startswith("the read authorization reached origin/main at or after"))


FINAL_COUNT = {"utc_start": "2027-12-10T00:00:00Z", "stage": "holdout", "purpose": "count", "status": "complete",
               "results_sha256": "c" * 64, "block": 0,
               "extension": {"extend": False, "below_minimum": [], "underpowered": []}, "void": False}


def validation_body(screened=("H3-a",)) -> bytes:
    """The bytes FR.write gives a governing validation results file whose validated items are `screened`."""
    ids = ("H1-D", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c")
    val = {"labels": {i: ("screened" if i in screened else "underpowered") for i in ids},
           "items": {i: {"p_stage": 0.01 if i in screened else 1.0} for i in ids}}
    return json.dumps(val).encode("utf-8")


def validation_sha(screened=("H3-a",)) -> str:
    from core.canon import sha256_bytes
    return sha256_bytes(validation_body(screened))


def auth_rec(aid, purpose, decision, refusal=None, retry_of=None, items=("H3-a",), val=None):
    """A well-formed authorization record (every gate.AUTH_FIELDS field; review round 12, F1). val: the validation
    results sha256 it binds (review round 14, Codex P1); by default the one write_validation writes for `items`."""
    return {"utc": "x", "record_kind": "authorization", "authorization_id": aid, "actor_role": "committed automation",
            "protocol_id": "p", "protocol_sha256": "a" * 64, "code_revision": "c", "study_code_tree": "t",
            "runtime_lock_sha256": "r", "data_file_sha256s": {},
            "validation_results_sha256": val if val is not None else validation_sha(tuple(items) or ("H3-a",)),
            "requested_items": list(items), "purpose": purpose, "decision": decision, "refusal": refusal,
            "retry_of": retry_of}


def write_validation(repo, fx, screened=("H3-a",)):
    """A governing validation results file whose validated ('screened') items are `screened`."""
    FR.write(repo / RESULTS_DIR / "validation.json", validation_body(screened).decode("utf-8"))
    logs.append_line(repo / RUN_LOG, {"stage": "validation", "purpose": "evaluate", "status": "complete",
                                      "results_sha256": sha256_file(repo / RESULTS_DIR / "validation.json"),
                                      "study_tree": fx["tree"], "protocol_sha256": fx["protocol_sha256"]})
    return sha256_file(repo / RESULTS_DIR / "validation.json")


class ReadDecidedBeforeOutcome(unittest.TestCase):
    """Review round 11, F1: whether the holdout is read never depends on its outcome. A refused 'read' authorization
    cannot be held back and spent once a later granted read has sealed its snapshot (the exit quotes), and a sealed
    read is evaluated even when its evaluation comes after the deadline."""

    def test_a_held_back_refusal_cannot_be_spent_after_a_granted_read_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [ctx["n0_pinned"], last]})
            write_validation(repo, fx)
            FR.commit_push(repo, FR.git_date(deadline - 10 * 86400))
            # the manufactured refusal: a 'read' requested while a granted collect has no completion
            logs.append_line(repo / ACCESS_LOG, auth_rec("collect-001", "collect", "granted"))
            logs.append_line(repo / ACCESS_LOG, auth_rec(
                "read-002", "read", "refused", "an earlier granted authorization has no committed completion record"))
            logs.append_line(repo / ACCESS_LOG, gate.completion("collect-001", "x", "complete", "b" * 64, 0, None, []))
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-004", "read", "granted"))
            FR.commit_push(repo, FR.git_date(deadline - 6 * 86400))
            # step 1 of the granted read sealed its snapshot and its line is on origin/main
            logs.append_line(repo / RUN_LOG, {"utc_start": "x", "stage": "holdout", "purpose": "read_fetch",
                                              "status": "complete", "authorization_id": "read-004",
                                              "input_snapshot_sha256s": ["a" * 64], "snapshot_dir": "read-read-004",
                                              "enumeration_fetch_date": "2027-12-20", "results_sha256": None,
                                              "base_snapshots": [], "collection_batches": []})
            FR.commit_push(repo, FR.git_date(deadline - 5 * 86400))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "sealed its snapshot"):
                holdout.read(runner_ctx(repo), "read-002", root, {}, deadline - 4 * 86400)
            FR.write(repo / "marker.txt", "after the deadline\n")
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "sealed its snapshot"):
                holdout.read(runner_ctx(repo), "read-002", root, {}, deadline + 120)
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())
            # after the deadline the sealed read goes on to its evaluation (here it stops at the missing collection
            # batches of this bare fixture), never to the not-read label
            with self.assertRaisesRegex(holdout.HoldoutRefused, "collection batch"):
                holdout.read(runner_ctx(repo), "read-004", root, {}, deadline + 120)
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())

    def test_a_refusal_is_spent_only_when_latest_after_a_signed_deadline_and_no_granted_read_is_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            deadline = holdout.read_deadline(ctx, last)
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [ctx["n0_pinned"], last]})
            write_validation(repo, fx)
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-001", "read", "refused", "x"))
            FR.commit_push(repo, FR.git_date(deadline - 6 * 86400))
            # before the deadline a refusal is a failed attempt, not a label
            with self.assertRaisesRegex(holdout.HoldoutRefused, "only after the read deadline"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline - 5 * 86400)
            # a clock set forward past the deadline is not enough: no signed commit is at or after it
            with self.assertRaisesRegex(holdout.HoldoutRefused, "only after the read deadline"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 3600)
            # a granted read that is open decides the read; the earlier refusal is not the latest
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-002", "read", "granted"))
            FR.commit_push(repo, FR.git_date(deadline - 4 * 86400))
            FR.write(repo / "marker.txt", "after the deadline\n")
            FR.commit_push(repo, FR.git_date(deadline + 60))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "not the latest"):
                holdout.read(runner_ctx(repo), "read-001", root, {}, deadline + 120)
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())


class SignedDueTimes(unittest.TestCase):
    """Review round 11, F2: due times are judged by the signed time the authorization reached origin/main, and a
    record whose time is later than its commit's recorded time (a clock set forward) is refused."""

    def test_an_early_read_or_count_authorization_is_not_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo, root = fx["repo"], str(Path(tmp) / "snap")
            ctx = runner_ctx(repo)
            cal = ctx["cal"]
            _, last = holdout.window(ctx, 0)
            write_validation(repo, fx)
            logs.append_line(repo / ACCESS_LOG, auth_rec("count-001", "count", "granted"))
            FR.commit_push(repo, FR.git_date(cal.close(last) - 3600))
            with self.assertRaisesRegex(holdout.HoldoutRefused, "not due"):
                holdout.count(runner_ctx(repo), "count-001", root, {}, cal.close(last) + 7200)
            logs.append_line(repo / ACCESS_LOG, gate.completion("count-001", "x", "failed", None, 0, None, []))
            logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "utc_start": FR.git_date(cal.close(last) + 600)[:19] + "Z",
                                              "sessions": [ctx["n0_pinned"], last]})
            logs.append_line(repo / ACCESS_LOG, auth_rec("read-002", "read", "granted"))
            FR.commit_push(repo, FR.git_date(cal.close(cal.offset(last, 2))))
            # a local clock set to after the terminal-search windows does not make the read due
            with self.assertRaisesRegex(holdout.HoldoutRefused, "not due"):
                holdout.read(runner_ctx(repo), "read-002", root, {}, cal.close(cal.offset(last, 6)))
            self.assertFalse((repo / RESULTS_DIR / "holdout-read.json").exists())

    def test_a_record_later_than_its_commit_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            t = ctx["cal"].close(last)
            rec = dict(auth_rec("count-001", "count", "refused", "x"), utc=FR.git_date(t + 86400)[:19] + "Z")
            logs.append_line(repo / ACCESS_LOG, rec)
            FR.commit_push(repo, FR.git_date(t))
            with self.assertRaisesRegex(guards.Refused, "clock was set forward"):
                holdout.authorize(runner_ctx(repo), "count", t + 60)


class RetrySnapshot(unittest.TestCase):
    def test_same_snapshot_is_computed_from_the_retry_chain(self):
        """Review round 11, C15/F5: same_snapshot comes from the committed '_fetch' lines along retry_of, and a line
        that sealed a snapshot is reused by the retry even when its status is failed."""
        access = [auth_rec("count-001", "count", "granted"), auth_rec("count-002", "count", "granted", retry_of="count-001"),
                  auth_rec("count-003", "count", "granted", retry_of="count-002")]
        line = {"stage": "holdout", "purpose": "count_fetch", "status": "failed", "authorization_id": "count-001",
                "input_snapshot_sha256s": ["a" * 64], "snapshot_dir": "count-count-001"}
        ctx = {"access_log": access, "run_log": [line]}
        self.assertTrue(holdout.same_snapshot(ctx, "count", "count-002"))
        self.assertIs(holdout.fetch_line_of(ctx, "count", access[2]), line)
        other = dict(line, authorization_id="count-002", input_snapshot_sha256s=["b" * 64],
                     snapshot_dir="count-count-002")
        ctx["run_log"].append(other)
        self.assertFalse(holdout.same_snapshot(ctx, "count", "count-002"))
        self.assertTrue(holdout.same_snapshot(ctx, "count", None))

    def test_a_retry_that_completes_over_a_first_attempts_seal_reads_that_directory(self):
        """Review round 13, Codex P2: count-001 sealed its snapshot into count-count-001 and failed in _rate() (its
        failed completion names no snapshot); retry count-002 completed over the same snapshot. The base snapshot
        is read from the directory it was sealed into, not from count-<completing authorization>."""
        access = [auth_rec("collect-001", "collect", "granted"),
                  gate.completion("collect-001", "2027-01-01T00:00:00Z", "complete", "c" * 64, 0, None, []),
                  auth_rec("count-002", "count", "granted"),
                  gate.completion("count-002", "2027-01-02T00:00:00Z", "failed", None, 0, None, []),
                  auth_rec("count-003", "count", "granted", retry_of="count-002"),
                  gate.completion("count-003", "2027-01-03T00:00:00Z", "complete", "a" * 64, 5, "r" * 64, [])]
        line = {"stage": "holdout", "purpose": "count_fetch", "status": "failed", "authorization_id": "count-002",
                "input_snapshot_sha256s": ["a" * 64], "snapshot_dir": "count-count-002"}
        ctx = {"access_log": access, "run_log": [line]}
        self.assertEqual(holdout.sealed_refs(ctx), [("collect-collect-001", "c" * 64), ("count-count-002", "a" * 64)])


class StaleBase(unittest.TestCase):
    def test_a_per_event_request_fetched_before_its_data_end_is_fetched_again(self):
        """Review round 14, F1: the count fetches per-event bars and prints at the close of the window's last session;
        their 'end' is 5 sessions later, so the read must not reuse that response (a delayed exit after the last
        session would find no bar and drop out as 'undefined_factor'). A base response fetched after its data end
        is reused; the live copy governs once fetched; screen requests are never stale."""
        from core import driver
        from core.holdout_store import HoldoutStore
        cal = synth.calendar()
        t, last = "2020-06-01", "2020-06-05"
        end = cal.offset(last, 5)
        early = [r for r in plan.event_requests(cal, "AAA", t, end, holdout=True)]
        done = [r for r in plan.event_requests(cal, "AAA", t, last, holdout=True)]
        screen = plan.screen_requests(cal, last, ["AAA"])
        at_count = synth.iso_us(cal.close(last) + 60)[:19] + "Z"
        base = Store()
        for r in early + done + screen:
            base.put(r, True, [b'{"bars": {}}'], at_count)
        hs = HoldoutStore([base], Store(), cal)
        self.assertTrue(all(not hs.has(r["key"]) for r in early))
        self.assertTrue(all(hs.has(r["key"]) for r in done + screen))
        calls = []

        class Stub:
            def get(self, endpoint, params):
                calls.append(params["end"])
                return {"complete": True, "pages": [b'{"bars": {}}'], "error": None}
        driver.to_fixpoint(lambda st: early + done + screen, {"data": Stub(), "trading": Stub()}, hs, "2020-06-15",
                           clock=lambda: synth.iso_us(cal.close(end) + 60)[:19] + "Z")
        self.assertEqual(len(calls), len(early))
        self.assertTrue(all(hs.has(r["key"]) and hs._holder(r["key"]) is hs.live for r in early))
        # without the calendar (the pre-round-14 store) the count's response was reused as held
        self.assertTrue(all(HoldoutStore([base], Store()).has(r["key"]) for r in early))


class DiscardedAttempt(unittest.TestCase):
    def test_a_sealed_ledger_without_its_committed_line_is_not_fetched_again(self):
        """Review round 14, F3: a fetch step whose directory already holds a sealed ledger that no committed line
        names (a discarded local attempt) is refused before any request, for a holdout count or read and for a stage
        fetch under its open start line."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "snap"
            FR.write(root / "read-read-001" / "ledger.jsonl", "")
            with self.assertRaisesRegex(holdout.HoldoutRefused, "discarded attempt"):
                holdout._fetch_step({"repo": Path(tmp)}, "read", {"authorization_id": "read-001"}, [], str(root),
                                    None, "plan", "2027-12-20", {}, None, 0.0, ["2027-01-02", "2027-12-10"], {})
            self.assertFalse((Path(tmp) / RUN_LOG).exists())
            ctx = {"repo": Path(tmp), "tree": "t", "protocol_sha256": "p",
                   "run_log": [{"stage": "validation", "purpose": "fetch_start", "study_tree": "t",
                                "protocol_sha256": "p"}]}
            FR.write(root / "validation" / "ledger.jsonl", "")
            with self.assertRaisesRegex(runner.RunRefused, "discarded attempt"):
                runner.stage_fetch_run(ctx, "validation", root / "validation", None, {}, None)


class OpenList(unittest.TestCase):
    def test_no_count_is_authorized_while_the_open_list_has_an_entry(self):
        """Review round 14: open_before_first_holdout_count must be empty before the first holdout count; authorize
        refuses a 'count' and writes no record while it has an entry."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            ctx["protocol"] = dict(ctx["protocol"], open_before_first_holdout_count=[{"id": "R14-open-1"}])
            with self.assertRaisesRegex(holdout.HoldoutRefused, "R14-open-1"):
                holdout.authorize(ctx, "count", ctx["cal"].close(last) + 60)
            self.assertEqual((repo / ACCESS_LOG).read_text(), "")


class TerminalRecords(unittest.TestCase):
    """Review round 15, N02 (R14-open-1): a count and a read fetch their own terminal-record request (every corporate
    action to their own fetch date) and the trade walk uses its records, while the enumeration, the screen and its
    dedup keep the first count's. At e7529b47 the read reused the first count's enumeration_fetch_date as the only
    corporate-action end date, so a merger or split effective after it (inside the extension blocks or the terminal
    search windows through last + 5) was never fetched for the read and a merger exit booked terminal-zero."""

    def test_the_plan_and_the_spec_carry_the_actions_own_terminal_records(self):
        from core import plan as P
        from core.records import MERGER_TYPES
        cal = synth.calendar("2026-06-01", "2028-12-29")
        ctx = {"cal": cal, "fees": None, "cells": {}}
        merger = {"type": "cash_merger", "acquiree_symbol": "AAA", "acquirer_symbol": "BIGCO",
                  "effective_date": "2028-06-05", "rate": 12.0}
        enum_date, terminal_date = "2027-12-20", "2028-06-20"
        live = Store()
        for req, body in ((P.assets_requests()[0], [{"symbol": "AAA", "status": "active", "class": "us_equity"}]),
                          (P.assets_requests()[1], []),
                          (P.corporate_actions_request("2016-01-01", enum_date), {"corporate_actions": {}}),
                          (P.terminal_actions_request(terminal_date),
                           {"corporate_actions": {"cash_mergers": [{k: v for k, v in merger.items() if k != "type"}]}})):
            synth.put_json(live, req, body)
        store = holdout.HoldoutStore([], live, cal)
        spec = holdout._spec_factory(ctx, "2027-01-04", "2027-12-31", frozenset(), frozenset(), ("H3-a",),
                                     terminal_date)(store)
        self.assertEqual(spec.actions, [])                              # the enumeration's records
        self.assertEqual([r["type"] for r in spec.terminal_actions], ["cash_merger"])
        self.assertEqual(spec.symbols, ["AAA"])                         # BIGCO is never enumerated
        self.assertEqual(len(list(spec.ctx("read").records(MERGER_TYPES, acquiree_symbol="AAA"))), 1)
        reqs = holdout._planner(lambda st: spec, "plan", enum_date, terminal_date)(Store())
        ends = sorted((r["kind"], r["params"]["end"]) for r in reqs if r["endpoint"] == "/v1/corporate-actions")
        self.assertEqual(ends, [("corporate_actions", enum_date), ("terminal_actions", terminal_date)])
        self.assertEqual(holdout.enumeration([live])["actions"], [])     # never an enumeration input
        self.assertEqual(holdout._terminal_date(None, cal.at("2028-06-20", "12:00")), "2028-06-20")   # UTC date
        with self.assertRaises(holdout.HoldoutRefused):
            holdout._terminal_date({"enumeration_fetch_date": enum_date}, 0.0)


def _gap_fees(n0, cal):
    """Fee rows with an SEC Section 31 gap from the session after N0 (cost_model.fees)."""
    from core import costs
    return costs.Fees(synth.fee_document([("2016-01-01", n0, 8.0)], [("2016-01-01", "2030-12-31", 0.000166, 8.3)]),
                      cal=cal)


def _granted(tmp, purpose, aid, final_count=False):
    """A frozen fixture repository with the governing validation file and a granted authorization that reached
    origin/main after its due time (the close of the window's last session for a count; the end of the last
    terminal-search window, before the read deadline, for a read). Returns (repo, ctx, now, setup), setup being
    what _setup returns for block 0."""
    fx = FR.build(tmp)
    repo = fx["repo"]
    ctx = runner_ctx(repo)
    cal, n0 = ctx["cal"], ctx["n0_pinned"]
    _, last = holdout.window(ctx, 0)
    write_validation(repo, fx)
    if final_count:
        from core.calendar import iso_utc
        logs.append_line(repo / RUN_LOG, {**FINAL_COUNT, "sessions": [n0, last],
                                          "utc_start": iso_utc(cal.close(last) + 30)})
    logs.append_line(repo / ACCESS_LOG, auth_rec(aid, purpose, "granted"))
    t = cal.close(cal.offset(last, 5) if purpose == "read" else last) + 60
    FR.commit_push(repo, FR.git_date(t))
    ctx = runner_ctx(repo)
    auth = holdout._authorization(ctx, aid)
    return repo, ctx, t + 60, (auth, 0, n0, last, frozenset(), frozenset(), [], None, {})


class FeeCoverageBeforeFetch(unittest.TestCase):
    def test_count_and_read_call_require_fee_coverage_before_the_fetch_step(self):
        """Review round 14, F2: count() and read() refuse a fee gap in their sessions (a read's fee_span) before
        the fetch step runs; with full coverage the same call reaches the fetch step."""
        for purpose, aid, final in (("count", "count-001", False), ("read", "read-001", True)):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as tmp:
                repo, ctx, now, setup = _granted(tmp, purpose, aid, final_count=final)
                act = getattr(holdout, purpose)
                fetched = []
                with mock.patch.object(holdout, "_setup", return_value=setup), \
                        mock.patch.object(holdout, "_fetch_step",
                                          side_effect=lambda *a, **k: fetched.append(a[1]) or {"step": "fetch"}):
                    with self.assertRaisesRegex(holdout.HoldoutRefused, "no governing fee row"):
                        act(dict(ctx, fees=_gap_fees(ctx["n0_pinned"], ctx["cal"])), aid, str(Path(tmp) / "snap"), {}, now)
                    self.assertEqual(fetched, [])
                    act(ctx, aid, str(Path(tmp) / "snap"), {}, now)
                    self.assertEqual(fetched, [purpose])


class Step2Recovery(unittest.TestCase):
    """Step 2 of a count or read over a sealed snapshot, with the sealed inputs stubbed (review round 14, Codex P2)."""
    FL = {"stage": "holdout", "status": "complete", "input_snapshot_sha256s": ["a" * 64],
          "enumeration_fetch_date": "2027-12-20", "terminal_actions_fetch_date": "2027-12-20"}

    def _mocks(self, setup, fl, sealed_error=None):
        from types import SimpleNamespace
        from core import count_unit as CU
        sealed = SimpleNamespace(bases=[], live=Store())
        return [mock.patch.object(holdout, "fetch_line_of", return_value=fl),
                mock.patch.object(holdout, "_setup", return_value=setup),
                mock.patch.object(holdout, "_spec_factory", return_value=lambda store: None),
                mock.patch.object(holdout, "_sealed", side_effect=sealed_error, return_value=(sealed, "a" * 64)),
                mock.patch.object(holdout, "_rate", return_value={"rate": 0.0, "void": False, "by_kind": {}}),
                mock.patch.object(holdout.STG, "count_stage", return_value={"H3-a": 3}),
                mock.patch.object(CU, "extension_decision",
                                  return_value={"extend": False, "below_minimum": [], "underpowered": ["H3-a"]})]

    def _run(self, patches, fn):
        import contextlib
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return fn()

    def test_count_step_2_recomputes_and_replaces_an_uncited_results_file(self):
        """A holdout-count file that no line cites (a hard kill after its rename) is recomputed and replaced; the
        line cites the new bytes and records the replaced sha256."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, ctx, now, setup = _granted(tmp, "count", "count-001")
            fl = {**self.FL, "purpose": "count_fetch", "authorization_id": "count-001",
                  "snapshot_dir": "count-count-001"}
            path = repo / RESULTS_DIR / "holdout-count-0.json"
            FR.write(path, json.dumps({"extension": {"extend": True}, "void": False, "left_by": "a hard kill"}))
            orphan = sha256_file(path)
            out = self._run(self._mocks(setup, fl),
                            lambda: holdout.count(ctx, "count-001", str(Path(tmp) / "snap"), {}, now))
            body = json.loads(path.read_text())
            self.assertNotIn("left_by", body)
            self.assertEqual((body["counts"], body["extension"]["extend"]), ({"H3-a": 3}, False))
            self.assertEqual(out["results_sha256"], sha256_file(path))
            self.assertNotEqual(out["results_sha256"], orphan)
            line = logs.read_lines(repo / RUN_LOG)[-1]
            self.assertEqual((line["purpose"], line["status"], line["results_sha256"],
                              line["replaced_uncited_results_sha256"]),
                             ("count", "complete", sha256_file(path), orphan))
            self.assertEqual(logs.read_lines(repo / ACCESS_LOG)[-1]["status"], "complete")

    def test_a_failed_count_or_read_does_not_adopt_an_uncited_file_it_did_not_write(self):
        """The 'finally' of count and read adopts a results file only when this run wrote it (its sha256 differs
        from the uncited one found at the start); a step 2 that fails before its write logs 'failed' and leaves
        the uncited file for the retry."""
        for purpose, aid, name in (("count", "count-001", "holdout-count-0.json"),
                                   ("read", "read-001", "holdout-read.json")):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as tmp:
                repo, ctx, now, setup = _granted(tmp, purpose, aid, final_count=purpose == "read")
                fl = {**self.FL, "purpose": f"{purpose}_fetch", "authorization_id": aid,
                      "snapshot_dir": f"{purpose}-{aid}"}
                ctx = dict(ctx, run_log=[*ctx["run_log"], fl])
                path = repo / RESULTS_DIR / name
                FR.write(path, json.dumps({"extension": {"extend": True}, "void": False, "left_by": "a hard kill"}))
                before = path.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "sealed snapshot unreadable"):
                    self._run(self._mocks(setup, fl, RuntimeError("sealed snapshot unreadable")),
                              lambda: getattr(holdout, purpose)(ctx, aid, str(Path(tmp) / "snap"), {}, now))
                self.assertEqual(path.read_bytes(), before)
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((line["purpose"], line["status"], line["results_sha256"]), (purpose, "failed", None))
                done = logs.read_lines(repo / ACCESS_LOG)[-1]
                self.assertEqual((done["record_kind"], done["status"]), ("completion", "failed"))


class SealedStoreCalendar(unittest.TestCase):
    def test_fetch_step_and_sealed_give_the_holdout_store_the_calendar(self):
        """Review round 14, F1 through its callers: _fetch_step's live store and the store its rate is taken over,
        and _sealed's store, date base responses by ctx['cal'], so a count's per-event response fetched before its
        data end is fetched again by the read and is never read from the base."""
        from core import driver
        cal = synth.calendar()
        t, last = "2020-06-01", "2020-06-05"
        end = cal.offset(last, 5)
        early = plan.event_requests(cal, "AAA", t, end, holdout=True)
        done = plan.event_requests(cal, "AAA", t, last, holdout=True)
        base = Store()
        for r in early + done:
            base.put(r, True, [b'{"bars": {}}'], synth.iso_us(cal.close(last) + 60)[:19] + "Z")
        calls, rated = [], []

        class Stub:
            def get(self, endpoint, params):
                calls.append(params["end"])
                return {"complete": True, "pages": [b'{"bars": {}}'], "error": None}

        def rate(ctx, sealed, planner):
            rated.append(sealed)
            return {"rate": 0.0, "void": False, "by_kind": {}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / RUN_LOG).parent.mkdir(parents=True)
            root = Path(tmp) / "snap"
            ctx = {"repo": Path(tmp), "cal": cal, "commit": "c", "tree": "t", "runtime_lock_sha256": "r",
                   "protocol_sha256": "p"}
            with mock.patch.object(holdout, "_planner", return_value=lambda st: early + done), \
                    mock.patch.object(holdout, "_rate", side_effect=rate):
                out = holdout._fetch_step(ctx, "read", {"authorization_id": "read-001"}, [base], str(root), None,
                                          "plan", "2020-06-20", {"data": Stub(), "trading": Stub()},
                                          lambda: synth.iso_us(cal.close(end) + 60)[:19] + "Z", cal.close(end) + 60,
                                          [t, last], {})
            self.assertEqual(len(calls), len(early))
            self.assertEqual(len(rated), 1)
            self.assertIs(rated[0].cal, cal)
            self.assertTrue(all(rated[0]._holder(r["key"]) is rated[0].live for r in early))
            # _sealed over a sealed snapshot that lacks the early responses: the stale base copy is not held
            empty = Store().write(root / "count-count-001")
            hs, sha = holdout._sealed(ctx, {"input_snapshot_sha256s": [empty], "snapshot_dir": "count-count-001"},
                                      [base], str(root))
            self.assertEqual(sha, empty)
            self.assertIs(hs.cal, cal)
            self.assertTrue(all(not hs.has(r["key"]) for r in early))
            self.assertTrue(all(hs.has(r["key"]) for r in done))
            self.assertIsNotNone(out["snapshot_sha256"])


class ValidationBinding(unittest.TestCase):
    def test_the_governing_line_must_name_the_working_bytes(self):
        """Review round 14, Codex P1, third clause alone: the working file equals the authorization's bound sha256,
        but the governing run-log line names other bytes; the count or read is refused."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            ctx = runner_ctx(repo)
            _, last = holdout.window(ctx, 0)
            bound = write_validation(repo, fx)
            FR.commit_push(repo, FR.git_date(ctx["cal"].close(last)))
            ctx = runner_ctx(repo)
            auth = auth_rec("count-009", "count", "granted", val=bound)
            carried, _ = holdout.require_validated_carried(ctx, auth)
            self.assertEqual(carried, ("H3-a",))
            other = dict(ctx, run_log=[dict(x, results_sha256="e" * 64) if x.get("stage") == "validation" else x
                                       for x in ctx["run_log"]])
            self.assertEqual(holdout.validation_state(other)["sha256"], bound)
            with self.assertRaisesRegex(holdout.HoldoutRefused, "changed after the authorization"):
                holdout.require_validated_carried(other, auth)


class Collection(unittest.TestCase):
    def test_late_batches_and_plan(self):
        cal = synth.calendar("2026-06-01", "2027-06-30")
        b = [{"sessions": cal.range("2026-10-05", "2026-10-09"), "reachable": cal.at("2026-10-12", "09:31")}]
        self.assertEqual(plan.late_collected(cal, b), cal.range("2026-10-05", "2026-10-09"))


if __name__ == "__main__":
    unittest.main()
