"""Gaps 1/12: does Alpaca's corporate-action cash dividend carry a currency field?

Arms: (a) public REST contract embedded in docs.alpaca.markets (fetched HTML),
(b) installed alpaca-py CashDividend model fields, (c) key names (never values) of the
retained 2026-09-20 private actions bodies. Positive control: the key scanner is run on
the docs' own SSE example, which does carry `currency`.
Usage: python ca_currency_probe.py DOCS_HTML PRIVATE_RUN_DIR
"""
import json, sys, hashlib
from pathlib import Path

def keys(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield p + "/" + k
            yield from keys(v, p + "/" + k)
    elif isinstance(o, list):
        for v in o:
            yield from keys(v, p + "/[]")

html, run = Path(sys.argv[1]), Path(sys.argv[2])
s = html.read_text(encoding="utf-8", errors="replace")
dec = json.JSONDecoder()
def schema_after(marker):
    i = s.find(marker)
    return dec.raw_decode(s[i + len(marker.split(":{", 1)[0]) + 1:])[0] if i >= 0 else None
cash = schema_after('"cash_dividend":{"description":"Cash dividend."')
cur = schema_after('"currency":{"description":"The ISO 4217')
sse = schema_after('"CashDividend":{"description":"Example SSE payload')
out = {"docs_html_sha256": hashlib.sha256(html.read_bytes()).hexdigest(),
       "rest_cash_dividend": {"properties": sorted(cash["properties"]), "required": cash.get("required"),
                              "currency_is_property": "currency" in cash["properties"],
                              "currency_is_required": "currency" in (cash.get("required") or [])},
       "currency_schema": cur,
       "positive_control_sse_example_has_currency_key": any(k.endswith("/currency") for k in keys(sse["value"]))}
try:
    from alpaca.data.models.corporate_actions import CashDividend
    import importlib.metadata as m
    out["alpaca_py"] = {"version": m.version("alpaca-py"), "CashDividend_fields": list(CashDividend.model_fields),
                        "currency_field": "currency" in CashDividend.model_fields}
except ImportError:
    out["alpaca_py"] = None
out["retained_capture"] = {}
for f in sorted(run.glob("actions-*.json")):
    if f.name.endswith(".meta.json"):
        continue
    ks = sorted(set(keys(json.loads(f.read_bytes()))))
    out["retained_capture"][f.name] = {"body_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                       "currency_key_present": any(k.endswith("/currency") for k in ks), "key_paths": ks}
print(json.dumps(out, indent=1, sort_keys=True))
