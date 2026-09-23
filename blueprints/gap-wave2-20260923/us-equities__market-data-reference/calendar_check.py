"""Gaps 6/14: US venue calendars, ad-hoc closures, extended hours and NYSE corroboration.

Offline library arms (exchange_calendars, pandas_market_calendars) plus a parse of a
retained NYSE 'Holidays & Trading Hours' HTML fetch.  Usage: python calendar_check.py NYSE_HTML
"""
import html as H, json, re, sys
from datetime import date, datetime
import pandas as pd
import exchange_calendars as xc
import pandas_market_calendars as pmc

START, END, EXT_END = "2016-01-01", "2027-12-31", "2028-12-31"
out = {"versions": {"exchange_calendars": xc.__version__, "pandas_market_calendars": pmc.__version__, "pandas": pd.__version__},
       "range": [START, END], "future_extension_for_nyse_page": EXT_END}

def _ny(series):
    return (series.dt.tz_localize("UTC") if series.dt.tz is None else series).dt.tz_convert("America/New_York")

def xsessions(name, end=END):
    # Construct from an earlier bound so START is inside the realized range (attempt 1 hit DateOutOfBounds).
    cal = xc.get_calendar(name, start="2015-12-01", end=(pd.Timestamp(end) + pd.Timedelta(days=40)).date().isoformat())  # attempt 2 hit the same bound at end
    s = cal.sessions_in_range(START, end)
    # Fix round 1: derive "early" from every session close other than 16:00 ET, not only cal.early_closes.
    ny = _ny(cal.closes)
    early = {d.date().isoformat(): ny[d].strftime("%H:%M") for d in s if ny[d].strftime("%H:%M") != "16:00"}
    return cal, {d.date().isoformat() for d in s}, early

def psched(name, end=END, ext=False):
    cal = pmc.get_calendar(name)
    kw = {"start": "pre", "end": "post"} if ext else {}
    sch = cal.schedule(start_date=START, end_date=end, **kw)
    return cal, sch

def weekdays(end=END):
    return {d.date().isoformat() for d in pd.bdate_range(START, end)}

def pmc_early(sch):
    ny = sch["market_close"].dt.tz_convert("America/New_York")
    return {d.date().isoformat(): t.strftime("%H:%M") for d, t in ny.items() if t.strftime("%H:%M") != "16:00"}

def x_times(cal, sessions):
    o, c = _ny(cal.opens), _ny(cal.closes)
    return {d.date().isoformat(): (o[d].strftime("%H:%M"), c[d].strftime("%H:%M")) for d in cal.opens.index if d.date().isoformat() in sessions}

def p_times(sch):
    o = sch["market_open"].dt.tz_convert("America/New_York"); c = sch["market_close"].dt.tz_convert("America/New_York")
    return {d.date().isoformat(): (o[d].strftime("%H:%M"), c[d].strftime("%H:%M")) for d in sch.index}

def time_disagreements(a, b):
    """Fix round 1 (Codex review): compare opening AND closing times on common sessions."""
    return sorted([d, a[d], b[d]] for d in a.keys() & b.keys() if a[d] != b[d])

venues = {}
pairs = [("XNYS", "NYSE"), ("XNAS", "NASDAQ"), ("ARCX", "NYSE"), ("XASE", "NYSE"), ("XNYS", "BATS"), ("XNYS", "IEX")]
xcache, pcache = {}, {}
for x, p in pairs:
    if x not in xcache: xcache[x] = xsessions(x)
    if p not in pcache: pcache[p] = psched(p)
    _, xs, xe = xcache[x]
    _, ps = pcache[p]
    pset = {d.date().isoformat() for d in ps.index}
    pe = pmc_early(ps)
    venues[f"{x}~{p}"] = {"xcals_sessions": len(xs), "pmc_sessions": len(pset),
                          "only_xcals": sorted(xs - pset), "only_pmc": sorted(pset - xs),
                          "xcals_early_closes": len(xe), "pmc_early_closes": len(pe),
                          "early_close_disagreements": sorted(set(xe.items()) ^ set(pe.items())),
                          "open_close_time_disagreements": time_disagreements(x_times(xcache[x][0], xs), p_times(ps))}
out["venue_pairs"] = venues
out["xcals_calendar_objects"] = {k: type(v[0]).__name__ for k, v in xcache.items()}
out["pmc_calendar_objects"] = {k: type(v[0]).__name__ for k, v in pcache.items()}

# Ad-hoc closures with positive controls (adjacent session days that must be present).
adhoc = {"2018-12-05": "National Day of Mourning, George H. W. Bush", "2025-01-09": "National Day of Mourning, Jimmy Carter"}
controls = ["2018-12-04", "2018-12-06", "2025-01-08", "2025-01-10"]
out["adhoc_closures"] = {}
for d, why in adhoc.items():
    out["adhoc_closures"][d] = {"why": why, **{f"xcals_{x}_closed": d not in xcache[x][1] for x in xcache},
                                **{f"pmc_{p}_closed": d not in {i.date().isoformat() for i in pcache[p][1].index} for p in pcache}}
out["positive_controls_present"] = {c: all(c in xcache[x][1] for x in xcache) and all(c in {i.date().isoformat() for i in pcache[p][1].index} for p in pcache) for c in controls}

# Extended hours: pmc pre/post boundaries; exchange_calendars has no extended-session model.
ext = {}
for p in ["NYSE", "NASDAQ"]:
    cal, sch = psched(p, ext=True)
    cols = [c for c in ["pre", "market_open", "market_close", "post"] if c in sch.columns]
    ny = sch[cols].apply(lambda s: s.dt.tz_convert("America/New_York").dt.strftime("%H:%M"))
    combos = ny.value_counts().to_dict()
    ext[p] = {"columns": cols, "sessions": len(sch),
              "boundary_combinations_ET": {"|".join(k): v for k, v in combos.items()},
              "early_close_day_sample": ny.loc[ny["market_close"] != "16:00"].head(3).reset_index(drop=True).to_dict("records")}
out["pmc_extended_hours"] = ext
out["xcals_has_extended_hours_attrs"] = {a: hasattr(xcache["XNYS"][0], a) for a in ["pre_opens", "post_closes", "break_starts"]}

# NYSE published page (retained HTML) -> holidays 2026-2028 and early closes.
s = open(sys.argv[1], encoding="utf-8").read()
t = H.unescape(re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", re.sub(r"<script.*?</script[^>]*>", "", s, flags=re.S | re.I))))
hdr = re.search(r"\|Holiday\|(\d{4})\|(\d{4})\|(\d{4})\|", t)
years = [int(y) for y in hdr.groups()]
body = t[hdr.end(): t.find("|Trading Hours|NYSE|")]
names = ["New Year’s Day", "Martin Luther King, Jr. Day", "Washington's Birthday", "Good Friday", "Memorial Day",
         "Juneteenth National Independence Day", "Independence Day", "Labor Day", "Thanksgiving Day", "Christmas Day"]
cells = body.split("|")
MONTHS = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
nyse_holidays, rows = set(), {}
i = 0
while i < len(cells):
    if cells[i] in names:
        row = cells[i + 1: i + 4]; rows[cells[i]] = row
        for y, c in zip(years, row):
            m = re.match(r"\w+day, (\w+) (\d+)", c)
            if m: nyse_holidays.add(date(y, MONTHS[m.group(1)], int(m.group(2))).isoformat())
        i += 4
    else:
        i += 1
foot = " ".join(c for c in cells if "close early" in c)
nyse_early = {date(int(y), MONTHS[mo], int(d)).isoformat() for mo, d, y in re.findall(r"\w+day, (\w+) (\d+), (\d{4})", foot)}
out["nyse_page"] = {"years": years, "table_rows": rows, "holidays": sorted(nyse_holidays), "early_closes_1pm": sorted(nyse_early),
                    "arca_hours_text": re.findall(r"NYSE Arca Equities\|Pre-Opening Session: [^|]+\|[^|]+\|(Early Trading Session: [^|]+)\|", t)[:1]
                                        + re.findall(r"(Late Trading Session: [^|]+)", t[t.find("NYSE Arca Equities|Pre-Opening"):])[:1]}
_, xs28, xe28 = xsessions("XNYS", end=EXT_END)
_, ps28 = psched("NYSE", end=EXT_END)
p28 = {d.date().isoformat() for d in ps28.index}
wd = {d for d in weekdays(EXT_END) if d >= f"{years[0]}-01-01"}
for label, sess, early in [("xcals_XNYS", xs28, xe28), ("pmc_NYSE", p28, pmc_early(ps28))]:
    lib_hol = {d for d in wd if d not in sess}
    # Fix round 1 (Codex review): every library close other than 16:00 counts, and page dates must close at 13:00.
    lib_early = {d: tm for d, tm in early.items() if d >= f"{years[0]}-01-01"}
    out["nyse_page"][f"vs_{label}"] = {"holidays_only_page": sorted(nyse_holidays - lib_hol), "holidays_only_library": sorted(lib_hol - nyse_holidays),
                                       "early_only_page": sorted(nyse_early - set(lib_early)),
                                       "early_only_library": sorted([d, tm] for d, tm in lib_early.items() if d not in nyse_early),
                                       "early_time_not_1300": sorted([d, tm] for d, tm in lib_early.items() if d in nyse_early and tm != "13:00")}
# Self-test (fix round 1): injected disagreements must be reported by the same functions.
a = {"2020-01-02": ("09:30", "16:00"), "2020-01-03": ("09:30", "16:00")}
b = {"2020-01-02": ("10:00", "16:00"), "2020-01-03": ("09:30", "14:00")}
out["self_test_injected_time_disagreements"] = time_disagreements(a, b)
out["self_test_detected"] = len(out["self_test_injected_time_disagreements"]) == 2
print(json.dumps(out, indent=1, sort_keys=True, default=str))
