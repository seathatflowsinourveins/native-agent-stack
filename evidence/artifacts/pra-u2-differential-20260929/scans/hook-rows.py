"""Count-only scan of hook attachment rows (item 1): events, name shapes, content shapes, stdout claims. No ids, names of tools
beyond the event prefix, text or paths are printed."""
import json
import os
import sys
from collections import Counter, defaultdict

c = defaultdict(Counter)
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            try:
                fh = open(os.path.join(dirpath, name), "rb")
            except OSError:
                continue
            success = {}
            with fh:
                for raw in fh:
                    if b'"hook_' not in raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue
                    a = row.get("attachment") if isinstance(row, dict) else None
                    if not isinstance(a, dict) or not isinstance(a.get("type"), str) or not a["type"].startswith("hook_"):
                        continue
                    t = a["type"]
                    hn = a.get("hookName") if isinstance(a.get("hookName"), str) else None
                    he = a.get("hookEvent") if isinstance(a.get("hookEvent"), str) else None
                    prefix = hn.split(":", 1)[0] if hn else "(none)"
                    c["types"][t] += 1
                    c["event_vs_name_prefix"][t + " hookEvent=" + (he or "(absent)") + " nameprefix=" + prefix + " colon=" + str(bool(hn and ":" in hn))] += 1
                    if hn and len(hn) > 80:
                        c["long_names"][t + " " + prefix + " mcp=" + str(":mcp__" in hn)] += 1
                    if t == "hook_additional_context":
                        ct = a.get("content")
                        shape = "list%d" % len(ct) if isinstance(ct, list) else type(ct).__name__
                        c["additional_context_content"][(he or prefix) + " " + shape] += 1
                        if isinstance(ct, list):
                            c["additional_context_item_types"][",".join(sorted({type(x).__name__ for x in ct}))] += 1
                        tid = a.get("toolUseID")
                        c["additional_context_pairs_success"][(he or prefix) + " pair=" + str((tid, hn) in success)] += 1
                    elif t == "hook_success":
                        so = a.get("stdout")
                        kind = "absent"
                        if isinstance(so, str):
                            if not so.strip():
                                kind = "empty"
                            else:
                                try:
                                    j = json.loads(so)
                                    hso = j.get("hookSpecificOutput") if isinstance(j, dict) else None
                                    kind = "json_with_additionalContext" if isinstance(hso, dict) and hso.get("additionalContext") else "json_other"
                                except ValueError:
                                    kind = "plain"
                        c["success_stdout"][(he or prefix) + " " + kind] += 1
                        success[(a.get("toolUseID"), hn)] = True
                        c["success_has_hookEvent"][str(he is not None)] += 1
                    else:
                        c["other_hook_types_by_event"][t + " " + (he or prefix)] += 1
print(json.dumps({k: dict(v) for k, v in c.items()}, indent=1, sort_keys=True))
