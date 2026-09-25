"""run_discipline.amendment_format: the versioned line schema of the two append-only amendment files (review round
15, amendment-format item). FORMAT is repeated verbatim in the protocol, and tests/test_params.py asserts that the two
are equal, as for the parameters. data-pins.json named no line format; the parsers implied one that did not match the
base files (a fee line's 'rate' and 'max_per_trade' against the base rows' usd_per_million and max_usd_per_trade).

A calendar line removes one session of the pinned calendar; a fee line sets one rate over an inclusive date range on
the date basis of its table (cost_model.fees.charge_date). Every line cites a primary source on an official host.
"""
from __future__ import annotations

import math
import re
from datetime import date

SCHEMA_VERSION = 1
FEE_KINDS = ("sec_section31", "finra_taf_covered_equity")
CALENDAR_KINDS = ("remove_session",)
FEE_HOSTS = ("www.sec.gov", "www.federalregister.gov", "www.ecfr.gov", "www.finra.org")
CALENDAR_HOSTS = ("www.nyse.com", "ir.theice.com")

FORMAT = {
    "schema_version": SCHEMA_VERSION,
    "encoding": "UTF-8 JSON Lines: one JSON object per line, each line ending in a newline; the files are append-only "
                "(run_discipline.data_files), so a line is never edited, reordered or removed",
    "common_fields": {
        "schema_version": "the integer 1 (this format); a line with another version is refused",
        "kind": "the line kind, below",
        "source": "the primary source: an object with document (a non-empty string naming it), url (https on an "
                  "official host of the line's kind), retrieved_at (an ISO date) and quotes (a non-empty list of "
                  "non-empty verbatim passages that state the line's content)",
        "reason": "a non-empty string saying why the line is appended",
    },
    "calendar_line": {
        "file": "data/session-calendar-amendments.jsonl",
        "kind": "remove_session",
        "fields": {"session": "the ISO date of a session of the pinned calendar (data/session-calendar.json) that "
                              "the exchange will not open; removing a date that is not a pinned session is refused"},
        "official_hosts": list(CALENDAR_HOSTS),
    },
    "fee_lines": {
        "file": "data/fees-v3-amendments.jsonl",
        "sec_section31": {"fields": {"from": "ISO date, inclusive, on the SEC table's date basis (cost_model.fees)",
                                     "to": "ISO date, inclusive, or null for an open-ended rate",
                                     "usd_per_million": "a finite number >= 0: US dollars per million dollars of "
                                                        "covered sales, as data/fees-v3.json sec_section31.rows"}},
        "finra_taf_covered_equity": {"fields": {"from": "ISO date, inclusive, on the TAF table's date basis "
                                                        "(cost_model.fees)",
                                                "to": "ISO date, inclusive, or null for an open-ended rate",
                                                "usd_per_share": "a finite number >= 0: US dollars per share sold",
                                                "max_usd_per_trade": "a finite number >= 0: the per-trade cap, as "
                                                                     "data/fees-v3.json finra_taf_covered_equity.rows"}},
        "official_hosts": list(FEE_HOSTS),
    },
    "rules": [
        "Every listed field is required and no other field is allowed.",
        "Dates are inclusive; to null means open-ended; from <= to when to is a date.",
        "A calendar line's session and a fee line's from are on or after the freeze session; a line before it, or a "
        "line applied without a known freeze session, is refused.",
        "Precedence: a fee line supersedes, for the dates it covers, every earlier row of its kind, the base file's "
        "rows (their open-ended last row included) and every earlier line: the latest appended line that covers a "
        "date governs, and a base row governs a date no line covers. No line is edited; supersession is by "
        "precedence.",
        "A calendar line removes its session from the amended calendar; the freeze session and N0 keep the dates "
        "computed on the pinned, unamended calendar (chronology.holdout.window).",
        "Every line is logged in the access log under purpose 'amend' before its deadline: 09:30 ET of the session "
        "it removes, or the first holdout count or read that uses a date it covers (populations.session_calendar, "
        "cost_model.fees).",
    ],
}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _is_date(v) -> bool:
    if not isinstance(v, str) or not _DATE.fullmatch(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _is_rate(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def source_problems(src, hosts) -> list:
    if not isinstance(src, dict) or set(src) != {"document", "url", "retrieved_at", "quotes"}:
        return ["source must be an object with exactly document, url, retrieved_at and quotes"]
    out = []
    if not isinstance(src["document"], str) or not src["document"].strip():
        out.append("source.document must be a non-empty string")
    m = re.match(r"https://([^/]+)/", src["url"]) if isinstance(src["url"], str) else None
    if m is None or m.group(1) not in hosts:
        out.append(f"source.url must be https on one of {', '.join(hosts)}")
    if not _is_date(src["retrieved_at"]):
        out.append("source.retrieved_at must be an ISO date")
    q = src["quotes"]
    if not isinstance(q, list) or not q or not all(isinstance(x, str) and x.strip() for x in q):
        out.append("source.quotes must be a non-empty list of non-empty strings")
    return out


def _common(rec, kinds, hosts, extra: tuple) -> list:
    if not isinstance(rec, dict):
        return ["a line must be a JSON object"]
    want = {"schema_version", "kind", "source", "reason", *extra}
    out = []
    if rec.get("schema_version") != SCHEMA_VERSION or type(rec.get("schema_version")) is not int:
        out.append(f"schema_version must be {SCHEMA_VERSION}")
    if rec.get("kind") not in kinds:
        out.append(f"kind must be one of {', '.join(kinds)}")
    if set(rec) != want:
        missing, unknown = sorted(want - set(rec)), sorted(set(rec) - want)
        out.append(f"fields differ from the format (missing {missing}, unknown {unknown})")
    if not isinstance(rec.get("reason"), str) or not rec.get("reason", "").strip():
        out.append("reason must be a non-empty string")
    out.extend(source_problems(rec.get("source"), hosts))
    return out


def calendar_line_problems(rec) -> list:
    """Every way a calendar amendment line breaks FORMAT (empty when it conforms)."""
    out = _common(rec, CALENDAR_KINDS, CALENDAR_HOSTS, ("session",))
    if isinstance(rec, dict) and not _is_date(rec.get("session")):
        out.append("session must be an ISO date")
    return out


FEE_FIELDS = {"sec_section31": ("from", "to", "usd_per_million"),
              "finra_taf_covered_equity": ("from", "to", "usd_per_share", "max_usd_per_trade")}


def fee_line_problems(rec) -> list:
    """Every way a fee amendment line breaks FORMAT (empty when it conforms)."""
    kind = rec.get("kind") if isinstance(rec, dict) else None
    out = _common(rec, FEE_KINDS, FEE_HOSTS, FEE_FIELDS.get(kind, ("from", "to")))
    if not isinstance(rec, dict):
        return out
    if not _is_date(rec.get("from")):
        out.append("from must be an ISO date")
    if rec.get("to") is not None and not _is_date(rec.get("to")):
        out.append("to must be an ISO date or null")
    if _is_date(rec.get("from")) and _is_date(rec.get("to")) and rec["from"] > rec["to"]:
        out.append("from must be on or before to")
    for f in FEE_FIELDS.get(kind, ())[2:]:
        if not _is_rate(rec.get(f)):
            out.append(f"{f} must be a finite number >= 0")
    return out
