"""Fix round 3 review fix: show the injected-cell self-test fails when the table parser is broken.
Usage: python selftest_mutation.py NYSE_SNAPSHOT_HTML"""
import re, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_calendar_check as a  # noqa: E402

raw = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")


def run():
    parsed = a.parse_nyse(raw)
    ys = [y for y in parsed["years"] if a.LO <= y <= a.HI]
    fake = date(ys[0], 3, 8)
    while fake.weekday() > 4:
        fake = date(ys[0], 3, fake.day + 1)
    tc = "".join(f"<td>{fake.strftime('%A')}, March {fake.day}</td>" if y == ys[0] else "<td>-</td>" for y in parsed["years"])
    tbl = [t for t in re.findall(r"<table.*?</table>", raw, flags=re.S | re.I) if "Good Friday" in t][0]
    mod = raw.replace(tbl, tbl[: tbl.lower().rindex("</table>")] + f"<tr><td>Injected Day</td>{tc}</tr></table>", 1)
    inj = a.compare(a.parse_nyse(mod))[str(ys[0])]
    return all(fake.isoformat() in inj[k]["holidays_only_page"] for k in ("xcals", "pmc"))


print("unmutated parser: injected cell reported =", run())
a.parse_cell = lambda c, y: None
print("mutant parse_cell returning None: injected cell reported =", run())
