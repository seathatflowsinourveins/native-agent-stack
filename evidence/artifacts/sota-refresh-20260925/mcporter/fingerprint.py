#!/usr/bin/env python3
"""Read-only production fingerprint for the mcporter qualification (no content of credential stores is read).

Usage: fingerprint.py LABEL   -> writes fp/LABEL.json next to this script and prints a short summary.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

HOME = os.path.expanduser("~")
HERE = pathlib.Path(__file__).resolve().parent
E = f"{HOME}/.local/share/codex-ecosystem"
QDRANT = "http://127.0.0.1:26333"


def get(url):
    with urllib.request.urlopen(url, timeout=15) as r:  # GET only
        return json.loads(r.read())


def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout


def sha(s):
    return hashlib.sha256(s.encode() if isinstance(s, str) else s).hexdigest()


def stat_entry(p):
    try:
        st = os.lstat(p)
        return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "mode": oct(st.st_mode & 0o7777)}
    except FileNotFoundError:
        return None


def listing(root, maxdepth=3):
    out = {}
    rootp = pathlib.Path(root)
    if not rootp.exists():
        return None
    for dirpath, dirnames, filenames in os.walk(root):
        depth = pathlib.Path(dirpath).relative_to(rootp).parts
        if len(depth) >= maxdepth:
            dirnames[:] = []
        for n in dirnames + filenames:
            p = os.path.join(dirpath, n)
            out[os.path.relpath(p, root)] = stat_entry(p)  # metadata only, never contents
    return out


fp = {"label": sys.argv[1], "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

# Qdrant (production port): read-only GETs
cols = {}
for c in get(f"{QDRANT}/collections")["result"]["collections"]:
    info = get(f"{QDRANT}/collections/{c['name']}")["result"]
    cols[c["name"]] = {
        "status": info.get("status"),
        "points_count": info.get("points_count"),
        "payload_schema": sorted((info.get("payload_schema") or {}).keys()),
        "config_sha256": sha(json.dumps(info.get("config"), sort_keys=True)),
    }
fp["qdrant"] = cols
# Server-wide REST request counters (read-only telemetry GET): write endpoints must be explained if they move
tel = get(f"{QDRANT}/telemetry?details_level=1")["result"]["requests"]["rest"]["responses"]
fp["qdrant_rest_counts"] = {ep: sum(v.get("count", 0) for v in codes.values()) for ep, codes in tel.items()}
WRITE_EPS = ("PUT /collections/{collection_name}/points", "POST /collections/{collection_name}/points/delete",
             "PUT /collections/{collection_name}", "DELETE /collections/{collection_name}",
             "PUT /collections/{collection_name}/index", "POST /collections/{collection_name}/snapshots",
             "DELETE /collections/{collection_name}/snapshots/{snapshot_name}")
fp["qdrant_write_endpoint_counts"] = {ep: fp["qdrant_rest_counts"].get(ep, 0) for ep in WRITE_EPS}

# Shared per-user mcporter daemon namespace: names/sizes/mtimes only (credentials.json and user.key are never opened)
fp["mcporter_home_listing"] = listing(f"{HOME}/.mcporter")
fp["bin_mcporter_link"] = os.readlink(f"{E}/bin/mcporter")
fp["tools_mcporter_prefixes"] = sorted(p.name for p in pathlib.Path(f"{E}/tools").glob("mcporter-*"))
fp["installed_versions_mcporter"] = sh(f"grep -A1 -- '-- mcporter --' {E}/installed-versions.txt | tail -1")[1].strip()
fp["mcporter_config_sha256"] = sha(pathlib.Path(f"{E}/config/mcporter.json").read_bytes())

# git checkouts: HEAD + porcelain status hash without taking optional locks (no index refresh writes)
for key, path in (("live_clone", f"{HOME}/code/native-agent-stack-live"), ("main_checkout", f"{HOME}/code/native-agent-stack")):
    head = sh(f"git -C {path} rev-parse HEAD")[1].strip()
    st = sh(f"git -C {path} --no-optional-locks status --porcelain --untracked-files=all")[1]
    fp[key] = {"head": head, "status_porcelain_sha256": sha(st), "status_lines": len(st.splitlines())}

# Files a context-mode start.mjs self-heal could write (we never launch start.mjs; recorded to prove it)
for key, p in (("claude_installed_plugins_json", f"{HOME}/.claude/plugins/installed_plugins.json"),
               ("codex_context_mode_plugin_stats_json", f"{HOME}/.codex/plugins/cache/context-mode/context-mode/1.0.169/stats.json")):
    e = stat_entry(p)
    fp[key] = dict(e, sha256=sha(pathlib.Path(p).read_bytes())) if e else None
fp["codex_context_mode_plugin_dir_listing_sha256"] = sha(json.dumps(listing(f"{HOME}/.codex/plugins/cache/context-mode/context-mode/1.0.169", 1), sort_keys=True))

# user services (names + states) and unix-socket listeners that look like mcporter daemons
rc, out = sh("systemctl --user list-units --type=service --all --no-legend --plain --no-pager")
units = sorted(" ".join(l.split()[:4]) for l in out.splitlines() if l.strip())
fp["user_services"] = {"count": len(units), "sha256": sha("\n".join(units)),
                       "running": sorted(l.split()[0] for l in units if " running" in l)}
rc, out = sh("ss -xlpn")
fp["mcporter_socket_listeners"] = sorted(l.split()[4].replace(HOME, "~") for l in out.splitlines()
                                         if "user.sock" in l and ".mcporter" in l or "mcporter/x/dd" in l or "mcporter/y/dd" in l)

outp = HERE / "fp" / f"{sys.argv[1]}.json"
outp.parent.mkdir(exist_ok=True)
outp.write_text(json.dumps(fp, indent=1, sort_keys=True).replace(HOME, "~") + "\n")
print(json.dumps({"label": fp["label"], "at_utc": fp["at_utc"],
                  "qdrant_points": {k: v["points_count"] for k, v in cols.items()},
                  "qdrant_write_counts": fp["qdrant_write_endpoint_counts"],
                  "bin_link": fp["bin_mcporter_link"].replace(HOME, "~"), "prefixes": fp["tools_mcporter_prefixes"],
                  "mcporter_home_entries": sorted((fp["mcporter_home_listing"] or {}).keys()),
                  "sockets": fp["mcporter_socket_listeners"], "running_services": len(fp["user_services"]["running"]),
                  "live_head": fp["live_clone"]["head"][:12], "main_head": fp["main_checkout"]["head"][:12]}, indent=None))
