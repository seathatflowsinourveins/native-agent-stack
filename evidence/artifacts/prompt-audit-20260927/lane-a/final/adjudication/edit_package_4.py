"""One-off edit of package_lane_a.py: the exposure scan (exposure_scan_dir.py) found the host user name and the
session id's first block inside published regexes, and one installed Codex plugin's cache path in the self-test's
synthetic cases; replace them with placeholders."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "package_lane_a.py"
t = p.read_text()
a = '''    text = re.sub(r"-home-[A-Za-z0-9_]+-[A-Za-z0-9_-]*", "<project-dir>", text)'''
b = '''    text = re.sub(r"-home-[A-Za-z0-9_]+-[A-Za-z0-9_-]*", "<project-dir>", text)
    text = re.sub(r"\\b" + re.escape(S.parent.name[:8]) + r"[0-9a-f-]*", "<session-id>", text)
    text = text.replace(Path.home().name, "<user>")
    text = re.sub(r"plugins/cache/[\\w.@+-]+/[\\w.@+-]+/\\d[\\w.@+-]*/skills/[\\w.@+-]+",
                  "plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>", text)'''
assert t.count(a) == 1
t = t.replace(a, b)
t = t.replace('"edit_package_3.py", "antipattern-rows.md"):', '"edit_package_3.py", "edit_package_4.py", "antipattern-rows.md"):')
assert "edit_package_4.py" in t
p.write_text(t)
print("ok")
