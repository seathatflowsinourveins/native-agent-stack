"""Post-hoc diagnostic (not preregistered): token overlap of each BM25 miss."""
import json, re, sys
sys.path.insert(0, sys.argv[1])
import extra_arms as ea
data = json.load(open("r4/frozen_ohlcv.json"))
docs = {d["asset"] + " " + d["month"]: d["text"] for d in ea.month_docs(data)}
res = json.load(open("r4/haystack.json"))
tok = lambda s: re.findall(r"(?u)\b\w+\b", s.lower())
out = []
for q, top in res["misses"]:
    qt = set(tok(q))
    out.append({"query": q, "top1": top, "query_tokens_in_true_doc": sorted(qt & set(tok(docs[q]))), "query_tokens_in_top1_doc": sorted(qt & set(tok(docs[top]))), "top1_text": docs[top], "true_text": docs[q]})
print(json.dumps({"note": "Post-hoc, first 20 of 34 misses as reported by the arm; tokenizer regex is the haystack InMemory BM25 default (?u)\\b\\w+\\b from document_store.py line 67 (case-folding assumed)", "rows": out}, indent=1))
