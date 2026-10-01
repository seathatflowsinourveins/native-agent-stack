"""Acceptance assertions for a markitdown qualification run.

Usage: python3 check_outputs.py DIR
DIR holds greeting.md, 8k.md and disc.md written with `markitdown INPUT -o OUTPUT`.
Exit 0 only when every check passes.
"""
import hashlib
import re
import sys

d = sys.argv[1]


def read(name):
    return open(f"{d}/{name}", encoding="utf-8").read()


def sha(name):
    return hashlib.sha256(open(f"{d}/{name}", "rb").read()).hexdigest()


g, k, m = read("greeting.md"), read("8k.md"), read("disc.md")
rows = [line for line in k.splitlines() if line.startswith("|")]
checks = {
    # recipe fixture (recipes/README.md): expected heading present
    "greeting_heading": "# Local browser command check" in g.splitlines(),
    # real SEC 8-K HTML (host receipt nativestack-5975wx-20260925--markitdown--use--20260925)
    "8k_phrases": "FORM 8-K" in k and "PREMIER FINANCIAL BANCORP" in k,
    "8k_table_rows_29": len(rows) == 29,
    "8k_lines_120": len(k.splitlines()) == 120,
    "8k_chars_5535": len(k) == 5535,
    "8k_no_raw_tags": not re.findall(r"<[a-zA-Z][^>]*>", k),
    # byte identity with the accepted 0.1.7 -o outputs (valid while the transitive set is unchanged)
    "greeting_sha256": sha("greeting.md") == "6196d91e3223d43a9fc4e99cd3c9e9b94fee57b0a91ae70b2030607b277681a2",
    "8k_sha256": sha("8k.md") == "b434cd315ba0da36730ad1fc4c035692d3570ccd444e122d179da75d2e554977",
    # 0.1.8 behavior discriminators taken from upstream v0.1.8 tests / code
    "v018_underline": "First<u>word</u>Last" in m,
    "v018_encoded_slash": "[example](https://example.com/items/a%2Fb)" in m,
    "v018_strike": "~~gone~~" in m,
    "v018_data_src": "![A photo](https://example.com/photo.jpg)" in m,
}
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} {name}")
raise SystemExit(0 if all(checks.values()) else 1)
