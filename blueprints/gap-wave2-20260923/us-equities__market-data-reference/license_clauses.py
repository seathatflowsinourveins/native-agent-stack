"""Gap 7: extract storage/redistribution clauses from retained primary documents.

Usage: python license_clauses.py DOCS_DIR  (PDFs already converted to .txt with pypdf).
Every clause is located by an exact anchor phrase; a missing anchor is reported, not skipped.
"""
import hashlib, html, json, re, sys
from pathlib import Path

D = Path(sys.argv[1])
def norm_txt(p): return re.sub(r"\s+", " ", p.read_text(encoding="utf-8", errors="replace"))
def norm_html(p):
    t = re.sub(r"<(script|style).*?</\1>", "", p.read_text(encoding="utf-8", errors="replace"), flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
SOURCES = {
 "alpaca_customer_agreement": ("https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf", "AcctAppMarginAndCustAgmt", "pdf",
    ["I also agree to the terms of the NASDAQ OMX Global Subscriber Agreement", "30. Use of Market Data", "AlpacaDB, Inc. provides market data to non-professional", "I agree not to reproduce, distribute, sell or commercially exploit the market data", "V26.2026.07"]),
 "alpaca_terms_and_conditions": ("https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf", "TermsAndConditions", "pdf",
    ["Content is provided exclusively for personal and noncommercial access and use", "Alpaca offers a ‘Basic’ market data plan"]),
 "nyse_market_data_display_services_agreement": ("https://files.alpaca.markets/disclosures/library/NYSE+Market+Data+Display+Services+Agreement.pdf", "NYSE_Market_Data_Display_Services_Agreement", "pdf",
    ["5. PERMITTED USE", "NONPROFESSIONAL SUBSCRIBER DEFINITION"]),
 "nasdaq_global_subscriber_agreement": ("https://files.alpaca.markets/disclosures/library/NASDAQ+OMX+Global+Subscriber+Agreement.pdf", "NASDAQ_OMX_Global_Subscriber_Agreement", "pdf",
    ["Information is licensed only for personal use", "Subscriber shall take reasonable security precautions"]),
 "sec_privacy_website_dissemination": ("http://web.archive.org/web/20260919152816id_/https://www.sec.gov/about/privacy-information", "sec-privacy-information-wb20260919", "html",
    ["Information presented on sec.gov is considered public information", "Current guidelines limit users to a total of no more than 10 requests per second"]),
 "sec_accessing_edgar_data": ("http://web.archive.org/web/20260821173111id_/https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data", "sec-accessing-edgar-data-wb20260821", "html",
    ["Anyone can access and download this information for free", "Current max request rate: 10 requests/second", "Please declare your user agent in request headers"]),
}
out = {}
for key, (url, stem, kind, anchors) in SOURCES.items():
    raw = D / (stem + (".pdf" if kind == "pdf" else ".html"))
    text = norm_txt(D / (stem + ".txt")) if kind == "pdf" else norm_html(raw)
    rec = {"url": url, "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "raw_bytes": raw.stat().st_size, "clauses": {}}
    for a in anchors:
        i = text.find(a)
        rec["clauses"][a] = text[i:i + 520] if i >= 0 else None
    rec["storage_terms_found"] = sorted(set(m.lower() for m in re.findall(r"\b(store|stored|storage|retain|retention|archive|cache|mirroring)\b", text, flags=re.I)))
    out[key] = rec
missing = [f"{k}:{a}" for k, r in out.items() for a, v in r["clauses"].items() if v is None]
print(json.dumps({"sources": out, "missing_anchors": missing}, indent=1, ensure_ascii=False))
sys.exit(1 if missing else 0)
