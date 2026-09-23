"""Gap 1: publish only the corporate-action schema fragments of the Alpaca docs page.

The full page embeds public site keys and example tokens that secret scanners flag, so it is
kept in the cache ($HOME/.cache/gap-wave2-20260923/market-data-reference/docs/ca-docs.html);
this excerpt records the exact JSON fragments used, plus the page sha256.
Usage: python3 docs_excerpt.py DOCS_HTML > raw/1-alpaca-corporateactions-docs.excerpt.json
"""
import hashlib, json, re, sys
s = open(sys.argv[1], encoding="utf-8").read()
dec = json.JSONDecoder()
def frag(marker):
    i = s.find(marker)
    key = marker.split(":{", 1)[0]
    obj, end = dec.raw_decode(s[i + len(key) + 1:])
    return obj
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
out = {"url": "https://docs.alpaca.markets/us/reference/corporateactions-1",
       "page_sha256": hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest(),
       "components.schemas.cash_dividend": frag('"cash_dividend":{"description":"Cash dividend."'),
       "components.schemas.currency": frag('"currency":{"description":"The ISO 4217'),
       "sse_example.CashDividend": frag('"CashDividend":{"description":"Example SSE payload')}
print(UUID.sub("<uuid-redacted>", json.dumps(out, indent=1, sort_keys=True)))
