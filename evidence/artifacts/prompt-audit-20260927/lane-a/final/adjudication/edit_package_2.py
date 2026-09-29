"""One-off edit of package_lane_a.py: scripts build host paths from pieces (the session id, the project directory
name and the per-user temporary root), so replace those pieces too, not only whole paths."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "package_lane_a.py"
t = p.read_text()
a = '''               ("<tmp>", "<tmp>")], key=lambda p: -len(p[0]))'''
b = '''               ("<tmp>", "<tmp>"), (str(S.parent.parent), "<session-root>"),
               (S.parent.name, "<session-id>"), (S.parent.parent.name, "<project-dir>"),
               (str(S.parent.parent.parent), "<tmp-root>")], key=lambda p: -len(p[0]))'''
assert t.count(a) == 1
p.write_text(t.replace(a, b))
print("ok")
