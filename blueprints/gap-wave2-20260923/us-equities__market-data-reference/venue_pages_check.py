"""Gaps 6/14 fix round 2: per-venue published-calendar corroboration and library alias disclosure.

The library venue pairs in calendar_check.py all resolve to one NYSE rule set (aliases), so this
check compares the libraries with each venue operator's own published holiday page.
Usage: python venue_pages_check.py NASDAQTRADER_HTML CBOE_HOURS_HTML NYSE_HTML
"""
import html as H, json, re, sys
from datetime import date
import pandas as pd
import exchange_calendars as xc
import pandas_market_calendars as pmc

MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}


def text(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    t = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", re.sub(r"<(script|style).*?</\1>", "", s, flags=re.S))))
    return re.sub(r"(\|\s*)+", "| ", t)


def parse_nasdaqtrader(t):
    i = t.find("U.S. Equity and Options Markets Holiday Schedule")
    j = t.find("TradeDate", i)
    seg = t[i:j]
    rows = re.findall(r"(\w+) (\d+), (\d{4}) \| ([^|]+?) \| (Closed|\d+:\d\d [ap]\.m\.)", seg)
    hol, early = set(), {}
    for mo, d, y, name, status in rows:
        iso = date(int(y), MONTHS[mo], int(d)).isoformat()
        if status == "Closed":
            hol.add(iso)
        else:
            h, m = status.split()[0].split(":")
            early[iso] = f"{int(h) + (12 if 'p.m.' in status and int(h) != 12 else 0):02d}:{m}"
    return {"heading": seg[:60].strip(), "rows": [list(r) for r in rows], "holidays": hol, "early": early,
            "footnote": re.findall(r"\* (Nasdaq will continue[^|]+)", seg)[:1]}


def parse_cboe(t):
    m = re.search(r"(\d{4}) \| Equities Holiday Schedule \|", t)
    year = int(m.group(1))
    seg = t[m.end(): t.find("©", m.end())]
    rows = re.findall(r"\| ([A-Z][^|]+?) \| (\w+) (\d+) (?=\|)", seg)
    hol, early = set(), {}
    for name, mo, d in rows:
        if mo not in MONTHS:
            continue
        iso = date(year, MONTHS[mo], int(d)).isoformat()
        (early.__setitem__(iso, None) if "Early Close" in name else hol.add(iso))
    hours = {}
    heads = ["Cboe BYX and EDGA Equities Trading Hours", "Cboe BZX and EDGX Equities Trading Hours", "Equities Holiday Schedule"]
    for venue, nxt in zip(heads, heads[1:]):
        k = t.find(venue)
        hours[venue] = re.findall(r"(Early Trading Session|Pre-Market(?: Trading)? Session|Regular Trading Session|Post[- ]Market Session) \| ([^|]+?) \| ([^|]+?) \|", t[k:t.find(nxt, k)])
    return {"year": year, "rows": [list(r) for r in rows], "holidays": hol, "early": early, "hours": hours}


def lib_calendars(year):
    s, e = f"{year}-01-01", f"{year}-12-31"
    wd = {d.date().isoformat() for d in pd.bdate_range(s, e)}
    out = {}
    for name in ["XNAS", "XNYS"]:
        cal = xc.get_calendar(name, start=f"{year - 1}-12-01", end=f"{year + 1}-01-31")
        ses = cal.sessions_in_range(s, e)
        ny = cal.closes.dt.tz_localize("UTC").dt.tz_convert("America/New_York") if cal.closes.dt.tz is None else cal.closes.dt.tz_convert("America/New_York")
        out[f"xcals_{name}"] = (cal, {d.date().isoformat() for d in ses},
                                {d.date().isoformat(): ny[d].strftime("%H:%M") for d in ses if ny[d].strftime("%H:%M") != "16:00"})
    for name in ["NASDAQ", "BATS", "NYSE"]:
        cal = pmc.get_calendar(name)
        sch = cal.schedule(start_date=s, end_date=e)
        c = sch["market_close"].dt.tz_convert("America/New_York")
        out[f"pmc_{name}"] = (cal, {d.date().isoformat() for d in sch.index},
                              {d.date().isoformat(): t.strftime("%H:%M") for d, t in c.items() if t.strftime("%H:%M") != "16:00"})
    return wd, out


def compare(page_hol, page_early, wd, sessions, early, check_time):
    lib_hol = wd - sessions
    r = {"holidays_only_page": sorted(page_hol - lib_hol), "holidays_only_library": sorted(lib_hol - page_hol),
         "early_only_page": sorted(set(page_early) - set(early)), "early_only_library": sorted(set(early) - set(page_early))}
    r["early_time_mismatch"] = sorted([d, page_early[d], early[d]] for d in set(page_early) & set(early)
                                      if check_time and page_early[d] != early[d])
    r["agree"] = not any(r.values())
    return r


out = {"versions": {"exchange_calendars": xc.__version__, "pandas_market_calendars": pmc.__version__}}
# Alias disclosure: what each venue name actually resolves to in each library.
aliases = getattr(xc.calendar_utils, "_default_calendar_aliases", {})
out["library_aliases"] = {
    "xcals_alias_table": {k: v for k, v in aliases.items() if k in ("NYSE", "NASDAQ", "BATS", "XNAS", "ARCX", "XASE")},
    "xcals_resolved_class": {n: type(xc.get_calendar(n, start="2026-01-01", end="2026-12-31")).__name__ for n in ["XNYS", "XNAS", "ARCX", "XASE", "BATS"]},
    "pmc_resolved_class": {n: type(pmc.get_calendar(n)).__name__ for n in ["NYSE", "NASDAQ", "BATS", "IEX"]},
    "consequence": "XNAS, ARCX, XASE (xcals) and NASDAQ, BATS (pmc) are the NYSE rule set; library-vs-library agreement for those venues is one comparison repeated, not per-venue evidence."}

nq = parse_nasdaqtrader(text(sys.argv[1]))
cb = parse_cboe(text(sys.argv[2]))
nyse_t = text(sys.argv[3])
out["nyse_page_scope_statement"] = re.findall(r"All NYSE markets observe U\.S\. holidays as listed below for [^|]+", nyse_t)[:1]
out["nyse_page_extended_hours"] = {v: re.findall(r"Early Trading Session: ([^|]+?) \|", nyse_t[nyse_t.find(f"| {v} |", nyse_t.find("Trading Hours | NYSE |")):])[:1]
                                   for v in ["NYSE Arca Equities", "NYSE American", "NYSE National", "NYSE Texas"]}

nq_years = sorted({int(d[:4]) for d in nq["holidays"] | set(nq["early"])})
out["nasdaqtrader"] = {"heading": nq["heading"], "years": nq_years, "rows": nq["rows"], "footnote": nq["footnote"],
                       "n_holidays": len(nq["holidays"]), "early_closes": nq["early"]}
out["cboe"] = {"year": cb["year"], "rows": cb["rows"], "n_holidays": len(cb["holidays"]),
               "early_closes": sorted(cb["early"]), "early_close_time_published": False, "hours": cb["hours"]}
out["parser_detection_ok"] = len(nq["holidays"]) >= 9 and len(cb["holidays"]) >= 9

for yr in sorted(set(nq_years) | {cb["year"]}):
    wd, libs = lib_calendars(yr)
    res = {}
    for lib in ["xcals_XNAS", "pmc_NASDAQ", "xcals_XNYS", "pmc_NYSE"]:
        _, ses, early = libs[lib]
        res[f"nasdaqtrader_vs_{lib}"] = compare({d for d in nq["holidays"] if d.startswith(str(yr))},
                                                {d: v for d, v in nq["early"].items() if d.startswith(str(yr))}, wd, ses, early, True)
    if cb["year"] == yr:
        for lib in ["pmc_BATS", "xcals_XNYS"]:
            _, ses, early = libs[lib]
            res[f"cboe_vs_{lib}"] = compare(cb["holidays"], cb["early"], wd, ses, early, False)
    out[f"comparisons_{yr}"] = res
    # Self-test: an injected extra holiday and a shifted early-close time must be reported.
    _, ses, early = libs["xcals_XNAS"]
    inj = compare({d for d in nq["holidays"] if d.startswith(str(yr))} | {f"{yr}-03-10"},
                  {**{d: v for d, v in nq["early"].items() if d.startswith(str(yr))}, f"{yr}-11-27": "14:00"}, wd, ses, early, True)
    out[f"self_test_{yr}"] = {"injected": [f"{yr}-03-10 holiday", f"{yr}-11-27 14:00 close"], "result": inj,
                             "detected": f"{yr}-03-10" in inj["holidays_only_page"] and bool(inj["early_time_mismatch"])}
print(json.dumps(out, indent=1, sort_keys=True, default=sorted))
