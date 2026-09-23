"""Gaps 6/14 fix round 3: non-code corroboration of the ad-hoc closures and archived NYSE holiday tables.

Usage: python archive_calendar_check.py --press ICE_HTML [ICE_HTML ...] --nyse NYSE_HTML [NYSE_HTML ...]

Press arm: for each closure verb (close/closed/closes/closing), report the first 'Month D, YYYY' date that
follows it within 200 characters in the same sentence (review fix: only the first date per verb is taken, so a
list such as 'closed on A and B' reports A only; the retained pages name one closure date each). A plain proximity rule would wrongly report the Bush page's moment-of-silence
date (Monday, December 3, 2018), which sits next to 'close' in the headline; that date is the negative
control. Self-tests inject a closure sentence (must be reported) and an 'open' sentence (must not be).

Archive arm: parse the holiday <table> of archived nyse.com/markets/hours-calendars snapshots
("All NYSE markets observe U.S. holidays as listed below for ..."), plus the 1:00 p.m. early-close
footnotes, and compare every listed year in 2016-2027 with exchange_calendars XNYS and
pandas_market_calendars NYSE. Library-only ad-hoc closures (2018-12-05, 2025-01-09) are reported
separately because the tables list regular holidays only. Detection floor: >= 9 holidays per listed
year; a self-test injects an extra holiday row into the HTML table, re-parses the page and must see the
date reported as page-only (review fix: the first version inserted into the parsed set, bypassing the parser).
"""
import argparse, hashlib, html as H, json, re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import exchange_calendars as xc
import pandas_market_calendars as pmc

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
WD = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
FULL = re.compile(rf"(?:{WD},\s+)?({MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})")
MD = re.compile(rf"({MONTHS})\s+(\d{{1,2}})")
ADHOC = {"2018-12-05", "2025-01-09"}
LO, HI = 2016, 2027


def text_of(raw):
    t = re.sub(r"<script.*?</script[^>]*>|<style.*?</style[^>]*>", " ", raw, flags=re.S | re.I)
    t = H.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t).strip()


def iso(m, y=None):
    return datetime.strptime(f"{m.group(1)} {m.group(2)} {y or m.group(3)}", "%B %d %Y").date().isoformat()


def sentences(t):
    # Split on '. ' followed by an uppercase letter or quote; keeps 'a.m. (' and 'p.m. (' inside a sentence.
    return re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", t)


def closure_dates(t):
    found = {}
    for s in sentences(t):
        for v in re.finditer(r"\bclos(?:e|ed|es|ing)\b", s, flags=re.I):
            m = FULL.search(s, v.end())
            # Run-2 tightening: the date must start within 200 characters of the verb (a title "Close" otherwise
            # paired with a body date ~1,600 characters later in an unpunctuated navigation run).
            if m and m.start() - v.end() <= 200:
                found.setdefault(iso(m), s[max(0, v.start() - 160): m.end() + 40])
    return found


def press_arm(paths):
    out = {"self_test": {}}
    inj = closure_dates("Intro text. The exchange will be closed on Friday, March 13, 2037. "
                        "The exchange will be open on Friday, March 20, 2037. End.")
    out["self_test"] = {"injected_closure_reported": "2037-03-13" in inj, "injected_open_not_reported": "2037-03-20" not in inj}
    out["pages"] = {}
    for p in paths:
        raw = Path(p).read_text(encoding="utf-8", errors="replace")
        found = closure_dates(text_of(raw))
        out["pages"][Path(p).name] = {"sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                                      "closure_dates": sorted(found), "evidence": {d: found[d] for d in sorted(found)}}
    allc = set().union(*[set(v["closure_dates"]) for v in out["pages"].values()]) if paths else set()
    out["adhoc_corroborated"] = {d: d in allc for d in sorted(ADHOC)}
    out["negative_controls"] = {"2018-12-03 (moment of silence, not a closure) not reported": "2018-12-03" not in allc,
                                "2024-12-29 (date of death, not a closure) not reported": "2024-12-29" not in allc}
    return out


def cells(row):
    return [text_of(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.S | re.I)]


def parse_cell(c, y):
    if not MD.search(c):
        return None
    obs = re.search(rf"\(Observed\s+(?:{WD},\s+)?(({MONTHS})\s+(\d{{1,2}}))\)", c, flags=re.I)
    m = MD.search(obs.group(1)) if obs else MD.search(c)
    return datetime.strptime(f"{m.group(1)} {m.group(2)} {y}", "%B %d %Y").date().isoformat()


def parse_nyse(raw):
    tables = [t for t in re.findall(r"<table.*?</table>", raw, flags=re.S | re.I) if "Good Friday" in t]
    if not tables:
        return None
    # Run-1 defect fix: the 2018 snapshot puts its year header in a bare <thead> (no <tr>), so match both.
    rows = re.findall(r"<thead.*?</thead>|<tr.*?</tr>", tables[0], flags=re.S | re.I)
    years, hol = None, {}
    for r in rows:
        cs = cells(r)
        ys = [int(c) for c in cs if re.fullmatch(r"\d{4}", c)]
        if ys and years is None:
            years = ys
            continue
        if years and len(cs) >= len(years) + 1:
            for y, c in zip(years, cs[-len(years):]):
                d = parse_cell(c, y)
                if d:
                    hol.setdefault(y, set()).add(d)
    t = text_of(raw)
    early = set()
    for m in re.finditer(r"close early at 1:00 p\.m\.(.*?)(?:\.\s+(?=[A-Z])|$)", t):
        for d in FULL.finditer(m.group(1)):
            early.add(iso(d))
    head = re.search(r"All NYSE markets observe U\.S\. holidays as listed below for ([^.]*)\.", t)
    return {"years": years, "holidays": {y: sorted(v) for y, v in hol.items()}, "early_1pm": sorted(early),
            "scope_statement": head.group(0) if head else None}


def library(years):
    lo, hi = f"{min(years)}-01-01", f"{max(years)}-12-31"
    cal = xc.get_calendar("XNYS", start=f"{min(years) - 1}-12-01", end=f"{max(years) + 1}-01-31")
    xs = {d.date().isoformat() for d in cal.sessions_in_range(lo, hi)}
    xclose = cal.closes.dt.tz_localize("UTC") if cal.closes.dt.tz is None else cal.closes
    xny = xclose.dt.tz_convert("America/New_York")
    xearly = {d.date().isoformat() for d in cal.sessions_in_range(lo, hi) if xny[d].strftime("%H:%M") == "13:00"}
    sch = pmc.get_calendar("NYSE").schedule(start_date=lo, end_date=hi)
    ps = {d.date().isoformat() for d in sch.index}
    pny = sch["market_close"].dt.tz_convert("America/New_York")
    pearly = {d.date().isoformat() for d, v in pny.items() if v.strftime("%H:%M") == "13:00"}
    wk = {d.date().isoformat() for d in pd.bdate_range(lo, hi)}
    return {"xcals": (wk - xs, xearly), "pmc": (wk - ps, pearly)}


def compare(parsed):
    ys = [y for y in (parsed["years"] or []) if LO <= y <= HI]
    if not ys:
        return {}
    lib = library(ys)
    res = {}
    for y in ys:
        page = set(parsed["holidays"].get(y, []))
        pe = {d for d in parsed["early_1pm"] if d.startswith(str(y))}
        row = {"page_holiday_count": len(page), "detection_floor_met": len(page) >= 9}
        for k, (lh, le) in lib.items():
            lh = {d for d in lh if d.startswith(str(y))}
            le = {d for d in le if d.startswith(str(y))}
            row[k] = {"holidays_only_page": sorted(page - lh), "holidays_only_library": sorted(lh - page - ADHOC),
                      "library_adhoc_closures": sorted((lh - page) & ADHOC),
                      "early_only_page": sorted(pe - le), "early_only_library": sorted(le - pe)}
            row[k]["match"] = not any(row[k][x] for x in ("holidays_only_page", "holidays_only_library", "early_only_page", "early_only_library"))
        res[str(y)] = row
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--press", nargs="*", default=[])
    ap.add_argument("--nyse", nargs="*", default=[])
    a = ap.parse_args()
    out = {"versions": {"exchange_calendars": xc.__version__, "pandas_market_calendars": pmc.__version__},
           "range": [LO, HI], "press": press_arm(a.press), "nyse_archive": {}}
    for p in a.nyse:
        raw = Path(p).read_text(encoding="utf-8", errors="replace")
        parsed = parse_nyse(raw)
        entry = {"sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()}
        if parsed is None:
            entry["parsed"] = False
        else:
            entry.update(parsed=True, scope_statement=parsed["scope_statement"], listed_years=parsed["years"],
                         early_1pm=parsed["early_1pm"], comparison=compare(parsed))
            ys = [y for y in (parsed["years"] or []) if LO <= y <= HI]
            if ys:
                fake = date(ys[0], 3, 8)
                while fake.weekday() > 4:
                    fake = date(ys[0], 3, fake.day + 1)
                # Inject a table row (one cell per listed year; only the first in-range year carries a date),
                # re-parse the modified HTML and compare: exercises parser and comparison together.
                tcells = "".join(f"<td>{fake.strftime('%A')}, March {fake.day}</td>" if y == ys[0] else "<td>\u2014</td>" for y in parsed["years"])
                tbl = [t for t in re.findall(r"<table.*?</table>", raw, flags=re.S | re.I) if "Good Friday" in t][0]
                mod = raw.replace(tbl, tbl[: tbl.lower().rindex("</table>")] + f"<tr><td>Injected Day</td>{tcells}</tr></table>", 1)
                inj = compare(parse_nyse(mod))[str(ys[0])]
                entry["self_test_injected_holiday_cell"] = {"date": fake.isoformat(), "reported_page_only": all(fake.isoformat() in inj[k]["holidays_only_page"] for k in ("xcals", "pmc"))}
        out["nyse_archive"][Path(p).name] = entry
    cov = {}
    for name, e in out["nyse_archive"].items():
        for y, row in (e.get("comparison") or {}).items():
            cov.setdefault(y, []).append({"snapshot": name, "match_both": row["xcals"]["match"] and row["pmc"]["match"]})
    out["per_year"] = {y: cov[y] for y in sorted(cov)}
    # Derived view (not preregistered): the most recent snapshot listing each year, i.e. the latest published
    # schedule retained for it; snapshot file names carry the Wayback timestamp, so name order is time order.
    out["per_year_latest_snapshot"] = {y: max(cov[y], key=lambda r: r["snapshot"]) for y in sorted(cov)}
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
