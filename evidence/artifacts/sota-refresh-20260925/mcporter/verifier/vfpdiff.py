#!/usr/bin/env python3
"""Diff two verifier fingerprints (fp/A.json + fp/A.ext.json vs fp/B...). Read-only; prints only counters, hashes and flags."""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
a_label, b_label = sys.argv[1], sys.argv[2]


def load(label, root=HERE):
    base = json.loads((root / "fp" / f"{label}.json").read_text())
    ext_p = root / "fp" / f"{label}.ext.json"
    ext = json.loads(ext_p.read_text()) if ext_p.exists() else None
    return base, ext


root_a = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else HERE
a, ae = load(a_label, root_a)
b, be = load(b_label)
print("window", a["at_utc"], "->", b["at_utc"])
keys = sorted(dict.fromkeys(list(a["qdrant_rest_counts"]) + list(b["qdrant_rest_counts"])))
for k in keys:
    x, y = a["qdrant_rest_counts"].get(k, 0), b["qdrant_rest_counts"].get(k, 0)
    if x != y:
        print("   rest", k, x, "->", y, "(write-class)" if k in a["qdrant_write_endpoint_counts"] else "")
for c in sorted(dict.fromkeys(list(a["qdrant"]) + list(b["qdrant"]))):
    pa, pb = (a["qdrant"].get(c) or {}).get("points_count"), (b["qdrant"].get(c) or {}).get("points_count")
    if pa != pb:
        print("   points", c, pa, "->", pb)
for k in ("bin_mcporter_link", "installed_versions_mcporter", "mcporter_config_sha256", "mcporter_home_listing", "live_clone",
          "main_checkout", "claude_installed_plugins_json", "codex_context_mode_plugin_stats_json",
          "codex_context_mode_plugin_dir_listing_sha256", "user_services", "mcporter_socket_listeners", "tools_mcporter_prefixes"):
    same = a.get(k) == b.get(k)
    print(k, "unchanged" if same else "CHANGED " + json.dumps(a.get(k))[:220] + " -> " + json.dumps(b.get(k))[:220])
if ae and be:
    for k in ("bin_table_sha256", "bin_entries", "bin_max_lstat_mtime_utc", "bin_mcporter", "systemd_user_dir_max_mtime_utc"):
        print("ext", k, "unchanged" if ae.get(k) == be.get(k) else "CHANGED " + json.dumps(ae.get(k)) + " -> " + json.dumps(be.get(k)))
    for p in be["hook_config_mtimes_utc"]:
        x, y = ae["hook_config_mtimes_utc"].get(p), be["hook_config_mtimes_utc"].get(p)
        print("mtime", p, "unchanged" if x == y else f"CHANGED {x} -> {y}")
    for u, v in be["service_start"].items():
        w = ae["service_start"].get(u, {})
        same = all(w.get(f) == v.get(f) for f in ("ActiveEnterTimestamp", "MainPID", "NRestarts"))
        if not same:
            print("service CHANGED", u, {f: [w.get(f), v.get(f)] for f in ("ActiveEnterTimestamp", "MainPID", "NRestarts")})
    print("services with identical ActiveEnterTimestamp/MainPID/NRestarts:",
          sum(all(ae["service_start"].get(u, {}).get(f) == v.get(f) for f in ("ActiveEnterTimestamp", "MainPID", "NRestarts"))
              for u, v in be["service_start"].items()), "of", len(be["service_start"]))
