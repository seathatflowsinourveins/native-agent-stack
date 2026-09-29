"""Count-only scan of an evidence directory in the working tree before its first push: exposure_scan.py's patterns
(client configuration text, home paths, secret-shaped strings) plus the settings-file names of make_x9_round3.py.
Prints counts and file names, never the matched text; exits 1 when any file carries configuration text, a home path,
a secret-shaped string or a Claude subagent id (added 2026-09-28 after a review found three in the lane-A package).

usage: exposure_scan_dir.py DIR
"""
import re
import sys
from pathlib import Path

CONFIG = re.compile(
    r"enabledPlugins|statusLine|status-?line (?:command|is wired|wiring)|installed_plugins|known_marketplaces"
    r"|plugins/cache|[a-z0-9-]+@[a-z0-9-]+\"?\s*:\s*true"
)
SETTINGS = re.compile(r"settings(?:\.local)?\.json|installed_plugins\.json|\.claude\.json|\.mcp\.json", re.I)
HOME = re.compile(r"/home/|/Users/|<user>")
SECRETISH = re.compile(r"\b(?:sk-[A-Za-z0-9]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-)"
                       r"|Bearer [A-Za-z0-9._-]{16,}")
AGENT_ID = re.compile(r"\ba[0-9a-f]{16}\b")
root = Path(sys.argv[1])
bad, settings_names = {}, {}
for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue
    t = p.read_text(errors="replace")
    rel = str(p.relative_to(root))
    n = {k: len(rx.findall(t)) for k, rx in (("config", CONFIG), ("home", HOME), ("secretish", SECRETISH),
                                              ("agent_id", AGENT_ID))}
    if any(n.values()):
        bad[rel] = n
    s = len(SETTINGS.findall(t))
    if s:
        settings_names[rel] = s
print("files with configuration text, home paths, secret-shaped strings or subagent ids:", bad or "none")
print("files naming a settings file (names only, counted):", settings_names or "none")
sys.exit(1 if bad else 0)
