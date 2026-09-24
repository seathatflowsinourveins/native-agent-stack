#!/usr/bin/env python3
"""Copy cited raw outputs into the evidence tree: replace the home path with $HOME, redact UUIDs, hash both forms."""
import hashlib, json, os, re, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
home = os.path.expanduser("~")
UUID = re.compile(rb"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
# Privacy sweep 2026-09-23 (PR #132 review): RFC 1918 addresses -> <lan-ip> (not package versions such as ==10.4.0.35).
LAN = re.compile(rb"(?<![\w.])(?<!==)(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?!\.?[\w])")
groups = {
    "purge": ["run-purge/results.json", "logs/purge.stdout", "logs/ljungbox.json", "run-purge-r2/results.json", "logs/purge-r2.stdout"],
    "libs": ["libs/" + n for n in sorted(os.listdir(src / "libs"))],
    "fcmp": ["logs/fcmp-attempt1.stderr", "logs/fcmp-attempt1.stdout", "run-fcmp-A/results.json", "run-fcmp-A/forecasts.json", "logs/fcmp-A.stdout", "logs/fcmp-A.stderr",
             "run-fcmp-B/results.json", "run-fcmp-B/forecasts.json", "logs/fcmp-B.stdout", "logs/fcmp-B.stderr",
             "run-fcmp-merged/results.json", "run-fcmp-merged/forecasts.json", "logs/fcmp-merge.stdout", "run-fcmp-merged-r2/results.json", "logs/fcmp-merge-r2.stdout"],
    "nautilus-round1": ["run-nautilus-round1/" + n for n in sorted(os.listdir(src / "run-nautilus-round1")) if n != "development-RAW.reports.json"] + ["logs/nautilus-round1.stdout"],
    "nautilus": ["run-nautilus/" + n for n in sorted(os.listdir(src / "run-nautilus"))] + ["logs/nautilus.stdout", "logs/nautilus.stderr"],
    "c13": ["run-c13/" + n for n in sorted(os.listdir(src / "run-c13"))] + ["logs/c13.stdout"],
    "r4": ["r4/" + n for n in sorted(os.listdir(src / "r4")) if n != "dump_bin.py" and not (src / "r4" / n).is_dir()]
          + ["logs/r4-export.json"] + ["logs/" + n for n in sorted(os.listdir(src / "logs")) if n.startswith("install-r4-")],
    "r5": ["r5/" + n for n in sorted(os.listdir(src / "r5")) if n != "dump_bin.py" and not (src / "r5" / n).is_dir()],
    "install": ["logs/install.log", "logs/install-al.log", "logs/install-extra.log", "requirements.in", "requirements-alphalens.in", "requirements-extra.in"],
}
manifest = []
for group, files in groups.items():
    for rel in files:
        raw = (src / rel).read_bytes()
        text = raw.replace(home.encode(), b"$HOME")
        text, uuids = UUID.subn(b"<uuid-redacted>", text)
        text, lans = LAN.subn(b"<lan-ip>", text)
        name = rel.replace("/", "__")
        if re.fullmatch(r"requirements[^/]*\.(?:txt|in)", name):
            # A captured probe requirements file is evidence, not a manifest of anything the catalog
            # installs: the non-manifest suffix keeps dependency scanners from treating it as one.
            name += ".captured"
        if name.endswith(".json"):
            # Not-JSON captures (empty, or stdout mixed with warnings) are retained as .json.txt, so
            # evidence discovery, which parses every hash-listed .json, can read the tree.
            try:
                json.loads(text)
            except ValueError:
                name += ".txt"
        out = dst / "raw" / group / name
        out.parent.mkdir(parents=True, exist_ok=True)
        data = text
        out.write_bytes(data)
        manifest.append({"source": "$CACHE/" + rel, "path": str(out.relative_to(dst)), "original_sha256": hashlib.sha256(raw).hexdigest(),
                         "home_replaced": home.encode() in raw, "uuids_redacted": uuids,
                         "committed_sha256": hashlib.sha256(data).hexdigest(), "bytes": len(raw)})
        if lans:
            manifest[-1]["lan_ips_redacted"] = lans
(dst / "raw" / "MANIFEST.json").write_text(json.dumps({"cache_root": "$CACHE = $HOME/.cache/gap-wave2-20260923/research-factors-ml",
    "note": "original_sha256 hashes the file as produced on the host (script-printed hashes refer to it); committed_sha256 hashes the committed file after replacing the home path with $HOME and UUIDs (engine event/order identities, codex session ids) with <uuid-redacted>. The Nautilus development reports of round 1 RAW are not retained (not cited).",
    "files": manifest}, indent=1) + "\n")
print(len(manifest), sum(m["home_replaced"] for m in manifest), sum(m["uuids_redacted"] for m in manifest))
