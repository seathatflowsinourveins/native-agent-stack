"""One-off edit of package_lane_a.py's clean(): home directories become ~ before the user name is replaced (so
/home/<name>/ reads as ~/), and installed plugin and skill names in Codex and agent skill paths become placeholders
also when a script splits such a path across two string literals (host client configuration stays out)."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "package_lane_a.py"
t = p.read_text()
start = t.index("def clean(text):")
end = t.index("\n\n\ndef write(")
new = '''def clean(text):
    for old, new in SUBS:
        text = text.replace(old, new)
    text = re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)
    text = re.sub(r"-home-[A-Za-z0-9_]+-[A-Za-z0-9_-]*", "<project-dir>", text)
    text = re.sub(r"\\b" + re.escape(S.parent.name[:8]) + r"[0-9a-f-]*", "<session-id>", text)
    text = text.replace(Path.home().name, "<user>")
    text = re.sub(r"plugins/cache/[\\w.@+-]+/[\\w.@+-]+/\\d[\\w.@+-]*/skills/[\\w.@+-]+",
                  "plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>", text)
    for old, new in (("<marketplace>", "<marketplace>"), ("<plugin>/<version>", "<plugin>/<version>"),
                     ("<skill>", "<skill>")):
        text = text.replace(old, new)
    text = re.sub(r"(\\.agents/skills/|\\.codex/skills/)[\\w.-]+", r"\\1<skill>", text)
    text = re.sub(r"/tmp/claude-\\d+", "<tmp-root>", text)
    return re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "<uuid>", text, flags=re.I)'''
t = t[:start] + new + t[end:]
t = t.replace('"edit_package_4.py", "antipattern-rows.md"):', '"edit_package_4.py", "edit_package_5.py", "antipattern-rows.md"):')
assert "edit_package_5.py" in t
p.write_text(t)
print("ok")
