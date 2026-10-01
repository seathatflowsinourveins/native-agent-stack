"""Independent read-only observation of one native-faults paper run.

Standalone: Python standard library only (urllib.request). It imports no
harness, engine, order-contract or alpaca-py code. Every broker request is an
HTTP GET to https://paper-api.alpaca.markets; redirects are refused and no
proxy is used. Modelled on observe-native-faults-20260924.py.

Credentials come from --env-file ('NAME=value' or 'export NAME=value' lines).
No key value, account id, account fingerprint, balance, broker order id or
host path is printed: the account is checked by comparing sha256(account id)
[:12] with --expect-fingerprint, broker order ids appear only as sha256[:12],
balances only as comparisons.

For the receipt's client_order_id prefix it lists every broker order with its
status and fills, repeats the client-id lookups the receipt claims, lists the
account's open orders and positions now and compares all of it with the
receipt. Optional read-only cross-checks: --plan (must match the receipt's
plan_sha256), --pre-run-probe (cash and equity recorded before the run) and
--ledger (the run's private ledger, opened read-only and immutable).

Exit codes: 0 every check matched, 1 at least one check did not match,
2 input or HTTP error, 3 the credentials belong to another account.
"""
import argparse
import collections
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

BASE_URL = "https://paper-api.alpaca.markets"
KEY_NAMES = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")
ORDER_PAGE = 500
ACTIVITY_PAGE = 100
MAX_PAGES = 20
TIMEOUT_SECONDS = 10


class ObserveError(Exception):
    pass


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def rfc3339_seconds(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts(value):
    return datetime.fromisoformat(value) if value else None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha12(text):
    return hashlib.sha256(str(text).encode()).hexdigest()[:12]


def num(value):
    """Decimal text without exponent ('0', '1', '385.67'); None when absent."""
    try:
        return None if value is None else format(Decimal(str(value)).normalize(), "f")
    except InvalidOperation:
        return str(value)


def shown_path(path):
    return os.path.basename(path) if os.path.isabs(path) else path


def load_keys(path):
    name = os.path.basename(path).lower()
    if "live" in name or "paper" not in name:
        raise ObserveError("--env-file must name a paper key file and must not name a live one")
    if os.stat(path).st_mode & 0o077:
        raise ObserveError("--env-file is accessible by group or others")
    keys = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, sep, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            if sep and key in KEY_NAMES:
                keys[key] = value
    if sorted(keys) != sorted(KEY_NAMES) or not all(keys.values()):
        raise ObserveError("--env-file lacks APCA_API_KEY_ID or APCA_API_SECRET_KEY")
    return keys


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # a 3xx surfaces as an HTTP error; credentials never follow it


class GetOnlyClient:
    """The observer's only network path: GET, fixed paper origin, logged without secrets."""

    def __init__(self, keys):
        self._headers = {"APCA-API-KEY-ID": keys["APCA_API_KEY_ID"],
                         "APCA-API-SECRET-KEY": keys["APCA_API_SECRET_KEY"],
                         "Accept": "application/json",
                         "User-Agent": "native-fault-observer/1 (python urllib)"}
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RefuseRedirect())
        self.log = []

    def get(self, path, params=None, allow=(200,), redact=()):
        params = dict(params or {})
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(BASE_URL + path + ("?" + query if query else ""),
                                         headers=self._headers, method="GET")
        entry = {"method": request.get_method(), "path": path,
                 "params": {k: ("sha256:" + sha12(v) if k in redact else v) for k, v in params.items()}}
        started = time.monotonic()
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                status, body = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, body = exc.code, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            entry.update(status=None, error=type(exc).__name__, ms=round((time.monotonic() - started) * 1000))
            self.log.append(entry)
            raise ObserveError(f"GET {path} failed: {type(exc).__name__}") from None
        entry.update(status=status, ms=round((time.monotonic() - started) * 1000))
        self.log.append(entry)
        try:
            data = json.loads(body) if body else None
        except ValueError:
            data = None
        if status not in allow:
            message = data.get("message") if isinstance(data, dict) else None
            raise ObserveError(f"GET {path} returned HTTP {status}" + (f": {str(message)[:160]}" if message else ""))
        return status, data


def list_orders(client, after_dt):
    orders, seen, after, pages = [], set(), rfc3339_seconds(after_dt), 0
    while pages < MAX_PAGES:
        _, page = client.get("/v2/orders", {"status": "all", "after": after, "direction": "asc", "limit": ORDER_PAGE})
        pages += 1
        if not isinstance(page, list):
            raise ObserveError("order listing is not a list")
        fresh = [o for o in page if o.get("id") not in seen]
        seen.update(o.get("id") for o in fresh)
        orders.extend(fresh)
        if len(page) < ORDER_PAGE:
            return orders, pages, True
        if not fresh:
            break
        after = page[-1]["submitted_at"]
    return orders, pages, False


def list_fills(client, params, redact=()):
    fills, token, pages = [], None, 0
    while pages < MAX_PAGES:
        query = dict(params, direction="asc", page_size=ACTIVITY_PAGE)
        if token:
            query["page_token"] = token
        _, page = client.get("/v2/account/activities/FILL", query, redact=redact)
        pages += 1
        if not isinstance(page, list):
            raise ObserveError("activity listing is not a list")
        fills.extend(page)
        if len(page) < ACTIVITY_PAGE:
            return fills, pages, True
        token = page[-1].get("id")
    return fills, pages, False


def receipt_claims(rc):
    """Per client id: the receipt's submit and read statuses and its final ledger state."""
    prefix, claims, submits = rc["client_id_prefix"], collections.OrderedDict(), 0
    for case in rc.get("cases") or []:
        detail, requests = case.get("detail") or {}, case.get("requests") or []
        submits += sum(1 for r in requests if r.get("kind") == "submit")
        cid = detail.get("client_order_id")
        if not cid:
            continue
        if not cid.startswith(prefix):
            raise ObserveError("a receipt case client id lacks the receipt's client_id_prefix")
        claim = claims.setdefault(cid, {"suffix": cid[len(prefix):], "cases": [], "submit_statuses": [],
                                        "read_statuses": [], "limit_price": None, "ledger": None})
        claim["cases"].append(case.get("id"))
        claim["submit_statuses"] += [r.get("status") for r in requests if r.get("kind") == "submit"]
        claim["read_statuses"] += [r.get("status") for r in requests if r.get("kind") == "read"]
        claim["limit_price"] = claim["limit_price"] or detail.get("limit_price")
        claim["ledger"] = detail.get("ledger_after") or detail.get("ledger") or claim["ledger"]
    for claim in claims.values():
        claim["accepted"] = any(isinstance(s, int) and 200 <= s < 300 for s in claim["submit_statuses"])
    return claims, submits


def order_view(order, prefix):
    cid = str(order.get("client_order_id") or "")
    return {"client_order_id": cid, "has_run_prefix": cid.startswith(prefix), "symbol": order.get("symbol"),
            "side": order.get("side"), "type": order.get("type") or order.get("order_type"),
            "time_in_force": order.get("time_in_force"), "qty": num(order.get("qty")),
            "limit_price": num(order.get("limit_price")), "extended_hours": order.get("extended_hours"),
            "status": order.get("status"), "filled_qty": num(order.get("filled_qty")),
            "filled_avg_price": num(order.get("filled_avg_price")), "submitted_at": order.get("submitted_at"),
            "canceled_at": order.get("canceled_at"), "filled_at": order.get("filled_at"),
            "broker_order_id_sha256_12": sha12(order.get("id"))}


def read_ledger(path, prefix):
    uri = "file:" + urllib.request.pathname2url(os.path.abspath(path)) + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    try:
        intents = {row[0]: row for row in con.execute(
            "SELECT client_id, status, filled_qty, broker_id, submit_attempted FROM intents")}
        executions = [row[0] for row in con.execute("SELECT client_id FROM executions")]
        positions = con.execute("SELECT count(*) FROM positions").fetchone()[0]
        kinds = collections.Counter(kind for (kind,) in con.execute("SELECT kind FROM events"))
    finally:
        con.close()
    return {"intents": intents, "executions_for_prefix": sum(1 for c in executions if str(c).startswith(prefix)),
            "executions_total": len(executions), "positions_rows": positions,
            "foreign_intents": sum(1 for c in intents if not str(c).startswith(prefix)),
            "event_kind_counts": dict(sorted(kinds.items()))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--expect-fingerprint", required=True, help="sha256(account id)[:12]; compared, never printed")
    ap.add_argument("--plan", help="plan.json (default: beside the receipt); used only if it matches plan_sha256")
    ap.add_argument("--pre-run-probe", help="GET probe JSON written before the run (cash/equity baseline)")
    ap.add_argument("--ledger", help="the run's ledger.sqlite3 (opened read-only, immutable)")
    ap.add_argument("--margin-seconds", type=int, default=300)
    a = ap.parse_args(argv)
    observed_started = datetime.now(timezone.utc)
    out = {"schema_version": 1, "kind": "native_fault_independent_observation",
           "evidence_class": "independent_observation",
           "method": ("Python stdlib urllib, HTTP GET only against " + BASE_URL + " (no harness, engine, "
                      "order-contract or alpaca-py import): account, clock, orders(status=all, after=receipt "
                      "started_at minus margin) filtered by the receipt's client_id_prefix, "
                      "orders:by_client_order_id for every receipt client id, FILL activities per prefix order "
                      "and account-wide, open orders, positions"),
           "script": os.path.basename(__file__), "script_sha256": sha256_file(__file__),
           "python": sys.version.split()[0], "observed_started_at": iso_z(observed_started)}
    try:
        receipt_sha = sha256_file(a.receipt)
        with open(a.receipt, encoding="utf-8") as fh:
            rc = json.load(fh)
        prefix, started, finished = rc["client_id_prefix"], ts(rc["started_at"]), ts(rc["finished_at"])
        claims, receipt_submits = receipt_claims(rc)
        out["receipt"] = {"path": shown_path(a.receipt), "sha256": receipt_sha, "gate": rc.get("gate"),
                          "status": rc.get("status"), "endpoint": rc.get("endpoint"), "symbol": rc.get("symbol"),
                          "client_id_prefix": prefix, "started_at": rc["started_at"],
                          "finished_at": rc["finished_at"], "posts_reserved": rc.get("posts_reserved"),
                          "submit_responses": rc.get("submit_responses"),
                          "client_ids": {c["suffix"]: {"cases": c["cases"], "submit_statuses": c["submit_statuses"],
                                                      "read_statuses": c["read_statuses"],
                                                      "final_ledger_status": (c["ledger"] or {}).get("status"),
                                                      "final_ledger_filled_qty": num((c["ledger"] or {}).get("filled_qty")),
                                                      "broker_id_recorded": (c["ledger"] or {}).get("broker_id_recorded")}
                                         for c in claims.values()}}
        plan_path = a.plan or os.path.join(os.path.dirname(a.receipt), "plan.json")
        plan = None
        if os.path.exists(plan_path):
            plan_sha = sha256_file(plan_path)
            out["plan"] = {"path": shown_path(plan_path), "sha256": plan_sha,
                           "equals_receipt_plan_sha256": plan_sha == rc.get("plan_sha256")}
            if plan_sha == rc.get("plan_sha256"):
                with open(plan_path, encoding="utf-8") as fh:
                    plan = json.load(fh)
        probe = None
        if a.pre_run_probe:
            with open(a.pre_run_probe, encoding="utf-8") as fh:
                probe = json.load(fh)
            out["pre_run_probe"] = {"sha256": sha256_file(a.pre_run_probe), "label": probe.get("label"),
                                    "started_at": probe.get("started_at"),
                                    "identity_matched": probe.get("account_fingerprint12_matches_expected")}
        ledger = read_ledger(a.ledger, prefix) if a.ledger else None

        client = GetOnlyClient(load_keys(a.env_file))
        _, account = client.get("/v2/account")
        identity = hashlib.sha256(str(account.get("id")).encode()).hexdigest()[:12] == a.expect_fingerprint.strip().lower()
        out["account"] = {"identity_matched": identity}
        if not identity:
            out.update(requests=client.log, error="credentials belong to another account; no further request made")
            print(json.dumps(out, indent=1))
            return 3
        cash, equity = Decimal(account["cash"]), Decimal(account["equity"])
        out["account"].update(status=account.get("status"), trading_blocked=account.get("trading_blocked"),
                              account_blocked=account.get("account_blocked"), multiplier=account.get("multiplier"),
                              long_market_value_zero=Decimal(account.get("long_market_value") or "0") == 0,
                              short_market_value_zero=Decimal(account.get("short_market_value") or "0") == 0,
                              cash_equals_equity=cash == equity)
        if probe:
            out["account"].update(cash_equals_pre_run_probe=cash == Decimal(probe["account"]["cash"]),
                                  equity_equals_pre_run_probe=equity == Decimal(probe["account"]["equity"]))
        _, clock = client.get("/v2/clock")
        out["clock"] = {"timestamp": clock.get("timestamp"), "is_open": clock.get("is_open")}

        list_after = started - timedelta(seconds=a.margin_seconds)
        orders, pages, complete = list_orders(client, list_after)
        mine = [o for o in orders if str(o.get("client_order_id") or "").startswith(prefix)]
        foreign = [o for o in orders if not str(o.get("client_order_id") or "").startswith(prefix)]

        def in_window(o):
            return o.get("submitted_at") is not None and started <= ts(o["submitted_at"]) <= finished

        since_start = [o for o in orders if o.get("submitted_at") is not None and ts(o["submitted_at"]) > started]
        out["orders_listing"] = {"after": rfc3339_seconds(list_after), "pages": pages, "complete": complete,
                                 "orders_listed": len(orders), "orders_since_receipt_started_at": len(since_start),
                                 "orders_in_run_window": sum(1 for o in orders if in_window(o)),
                                 "orders_with_prefix": len(mine),
                                 "foreign_orders_in_run_window": sum(1 for o in foreign if in_window(o)),
                                 "foreign_orders_listed": [{k: v for k, v in order_view(o, prefix).items()
                                                            if k in ("client_order_id", "symbol", "side", "status",
                                                                     "filled_qty", "submitted_at")} for o in foreign]}
        prefix_orders = {}
        for order in mine:
            view = order_view(order, prefix)
            view["suffix"] = view["client_order_id"][len(prefix):]
            fills, _, fills_complete = list_fills(client, {"order_id": order["id"]}, redact=("order_id",))
            view["fill_activities"] = len(fills)
            view["fill_activity_qty"] = num(sum((Decimal(str(f.get("qty") or "0")) for f in fills), Decimal(0)))
            view["fill_activities_complete"] = fills_complete
            prefix_orders[view["suffix"]] = view
        out["prefix_orders"] = list(prefix_orders.values())
        out["prefix_status_counts"] = dict(collections.Counter(v["status"] for v in prefix_orders.values()))

        lookups, lookup_ids = {}, {}
        for cid, claim in claims.items():
            status, body = client.get("/v2/orders:by_client_order_id", {"client_order_id": cid}, allow=(200, 404))
            entry = {"http_status": status, "found": status == 200}
            if status == 200:
                entry.update(status=body.get("status"), filled_qty=num(body.get("filled_qty")),
                             broker_order_id_sha256_12=sha12(body.get("id")),
                             same_order_as_listing=claim["suffix"] in prefix_orders
                             and sha12(body.get("id")) == prefix_orders[claim["suffix"]]["broker_order_id_sha256_12"])
                lookup_ids[cid] = body.get("id")
            lookups[claim["suffix"]] = entry
        out["client_id_lookups"] = lookups

        all_fills, _, all_fills_complete = list_fills(client, {"after": rfc3339_seconds(list_after)})
        order_cid = {o.get("id"): str(o.get("client_order_id")) for o in orders}
        out["account_fill_activities"] = {
            "after": rfc3339_seconds(list_after), "complete": all_fills_complete, "count": len(all_fills),
            "in_run_window": sum(1 for f in all_fills if f.get("transaction_time")
                                 and started <= ts(f["transaction_time"]) <= finished),
            "fills": [{"symbol": f.get("symbol"), "side": f.get("side"), "qty": num(f.get("qty")),
                       "transaction_time": f.get("transaction_time"),
                       "order_client_id": order_cid.get(f.get("order_id"), "<order not in listing>")}
                      for f in all_fills]}

        _, open_orders = client.get("/v2/orders", {"status": "open", "direction": "asc", "limit": ORDER_PAGE})
        _, positions = client.get("/v2/positions")
        out["open_orders_now"] = {"count": len(open_orders),
                                  "with_prefix": sum(1 for o in open_orders
                                                     if str(o.get("client_order_id") or "").startswith(prefix)),
                                  "orders": [{k: v for k, v in order_view(o, prefix).items()
                                              if k in ("client_order_id", "symbol", "side", "qty", "type", "status")}
                                             for o in open_orders]}
        out["positions_now"] = {"count": len(positions),
                                "positions": [{"symbol": p.get("symbol"), "side": p.get("side"), "qty": num(p.get("qty"))}
                                              for p in positions]}
    except (ObserveError, OSError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        out.update(requests=getattr(locals().get("client"), "log", []),
                   error=f"{type(exc).__name__}: {exc}"[:300])
        print(json.dumps(out, indent=1))
        return 2

    cleanup = rc.get("cleanup") or {}
    reconcile = cleanup.get("reconcile") or {}
    checks = []

    def check(name, expected, observed, basis):
        checks.append({"check": name, "expected": expected, "observed": observed,
                       "match": expected == observed, "basis": basis})

    accepted = [c for c in claims.values() if c["accepted"]]
    refused = [c for c in claims.values() if not c["accepted"]]
    check("receipt_submits_equal_posts_reserved_and_submit_responses", [receipt_submits, receipt_submits],
          [rc.get("posts_reserved"), rc.get("submit_responses")], "receipt-internal count of submit requests in cases")
    check("order_listing_complete", True, complete, "listing paginated to the end")
    check("broker_orders_with_prefix", len(accepted), len(prefix_orders),
          "receipt: client ids with a 2xx submit (" + ",".join(c["suffix"] for c in accepted) + ")")
    check("prefix_order_suffixes", sorted(c["suffix"] for c in accepted), sorted(prefix_orders),
          "receipt: accepted client ids")
    for c in accepted:
        ledger_claim, view, look = c["ledger"] or {}, prefix_orders.get(c["suffix"]) or {}, lookups[c["suffix"]]
        base = "receipt " + "/".join(c["cases"]) + " final ledger state"
        check(f"lookup_{c['suffix']}_found", True, look["found"], "receipt: accepted submit " + str(c["submit_statuses"]))
        check(f"lookup_{c['suffix']}_status", ledger_claim.get("status"), look.get("status"), base)
        check(f"listing_{c['suffix']}_status", ledger_claim.get("status"), view.get("status"), base)
        check(f"lookup_{c['suffix']}_filled_qty", num(ledger_claim.get("filled_qty")), look.get("filled_qty"), base)
        check(f"lookup_{c['suffix']}_same_order_as_listing", True, look.get("same_order_as_listing"),
              "client-id lookup and prefix listing return one broker order")
        check(f"fill_activities_{c['suffix']}", "0" if num(ledger_claim.get("filled_qty")) == "0" else ">0",
              "0" if view.get("fill_activities") == 0 else ">0", base + " filled_qty")
        check(f"order_{c['suffix']}_symbol_and_limit_price", [rc.get("symbol"), num(c["limit_price"])],
              [view.get("symbol"), view.get("limit_price")], "receipt symbol and case detail limit_price")
        check(f"order_{c['suffix']}_type", "limit", view.get("type"), "receipt case detail carries a limit_price")
        if plan:
            check(f"order_{c['suffix']}_plan_shape",
                  [plan.get("side"), num(plan.get("qty")), plan.get("time_in_force"), plan.get("extended_hours")],
                  [view.get("side"), view.get("qty"), view.get("time_in_force"), view.get("extended_hours")],
                  "plan.json bound by receipt plan_sha256")
    for c in refused:
        claimed = sorted(set(c["read_statuses"])) or [404]
        check(f"lookup_{c['suffix']}_http_status", claimed, [lookups[c["suffix"]]["http_status"]],
              "receipt " + "/".join(c["cases"]) + " client-id read after submit " + str(c["submit_statuses"]))
        check(f"no_listed_order_{c['suffix']}", False, c["suffix"] in prefix_orders, "receipt: submit refused")
    check("foreign_orders_in_run_window", 0, out["orders_listing"]["foreign_orders_in_run_window"],
          "single writer during the run (receipt posts_reserved are the run's only submits)")
    check("account_fill_activities_in_run_window", 0, out["account_fill_activities"]["in_run_window"],
          "receipt cleanup cash_delta_usd " + str(reconcile.get("cash_delta_usd")))
    check("open_orders_with_prefix_now", 0, out["open_orders_now"]["with_prefix"],
          "receipt cleanup broker_open_orders " + str(cleanup.get("broker_open_orders")))
    check("open_orders_now", reconcile.get("open_orders"),
          out["open_orders_now"]["count"], "receipt cleanup reconcile open_orders")
    check("positions_now", reconcile.get("positions"),
          out["positions_now"]["count"], "receipt cleanup reconcile positions")
    check("account_market_value_zero", [True, True],
          [out["account"]["long_market_value_zero"], out["account"]["short_market_value_zero"]],
          "receipt cleanup flat " + str(cleanup.get("flat")))
    if probe:
        check("cash_and_equity_equal_pre_run_probe", [True, True],
              [out["account"]["cash_equals_pre_run_probe"], out["account"]["equity_equals_pre_run_probe"]],
              "receipt cleanup cash_delta_usd " + str(reconcile.get("cash_delta_usd"))
              + "; baseline is the run stage's pre-run GET probe")
    if ledger is not None:
        crosscheck = {}
        for cid, c in claims.items():
            row = ledger["intents"].get(cid)
            recorded = bool(row and row[3])
            crosscheck[c["suffix"]] = {
                "in_ledger": row is not None, "ledger_status": row[1] if row else None,
                "ledger_filled_qty": num(row[2]) if row else None, "broker_id_recorded": recorded,
                "ledger_broker_id_equals_broker_order": (row[3] == lookup_ids.get(cid)) if recorded else None}
            check(f"ledger_{c['suffix']}_broker_id_recorded", (c["ledger"] or {}).get("broker_id_recorded"), recorded,
                  "receipt ledger broker_id_recorded")
            if c["accepted"]:
                check(f"ledger_{c['suffix']}_broker_id_equals_broker_order", True,
                      crosscheck[c["suffix"]]["ledger_broker_id_equals_broker_order"],
                      "private ledger intent broker_id vs client-id lookup")
                check(f"ledger_{c['suffix']}_status_and_fill_equal_broker",
                      [lookups[c["suffix"]].get("status"), lookups[c["suffix"]].get("filled_qty")],
                      [crosscheck[c["suffix"]]["ledger_status"], crosscheck[c["suffix"]]["ledger_filled_qty"]],
                      "private ledger intent vs broker")
            else:
                check(f"ledger_{c['suffix']}_status", (c["ledger"] or {}).get("status"),
                      crosscheck[c["suffix"]]["ledger_status"], "receipt ledger status")
        check("ledger_intents_equal_receipt_client_ids", sorted(c["suffix"] for c in claims.values()),
              sorted(str(k)[len(prefix):] for k in ledger["intents"] if str(k).startswith(prefix)),
              "private ledger intents")
        check("ledger_foreign_intents_executions_positions", [0, 0, 0],
              [ledger["foreign_intents"], ledger["executions_total"], ledger["positions_rows"]],
              "receipt: zero fills and flat")
        out["ledger_crosscheck"] = {"sha256": sha256_file(a.ledger), "opened": "read-only, immutable",
                                    "client_ids": crosscheck, "event_kind_counts": ledger["event_kind_counts"],
                                    "foreign_intents": ledger["foreign_intents"],
                                    "executions_total": ledger["executions_total"],
                                    "positions_rows": ledger["positions_rows"]}

    out["compat_observe_native_faults_20260924"] = {
        "orders_listed_since_start": out["orders_listing"]["orders_since_receipt_started_at"],
        "orders_with_prefix": len(prefix_orders),
        "by_suffix": {s: {"status": v["status"], "filled_qty": v["filled_qty"]} for s, v in prefix_orders.items()},
        **{f"lookup_{s}": ({"found": True, "status": v["status"], "filled_qty": v["filled_qty"]} if v["found"]
                           else {"found": False, "http_status": v["http_status"]}) for s, v in lookups.items()},
        "status_counts": out["prefix_status_counts"],
        "positions_now": out["positions_now"]["count"], "open_orders_now": out["open_orders_now"]["count"]}
    out["checks"] = checks
    out["mismatches"] = [c["check"] for c in checks if not c["match"]]
    out["all_match"] = not out["mismatches"]
    out["requests"] = client.log
    out["request_count"] = len(client.log)
    out["methods_used"] = sorted({entry["method"] for entry in client.log})
    out["observed_finished_at"] = iso_z(datetime.now(timezone.utc))
    out["privacy"] = ("No key value, account id, account fingerprint, balance, broker order id or host path is "
                      "printed; broker order ids appear only as sha256[:12].")
    print(json.dumps(out, indent=1))
    return 0 if out["all_match"] else 1


if __name__ == "__main__":
    sys.exit(main())
