"""One-off edit of package_lane_a.py: truncated labels in self-test records cut host paths mid-name, so after the
whole-path replacements also replace any remaining project-directory fragment, per-user temporary root or UUID."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "package_lane_a.py"
t = p.read_text()
a = '''    return re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)'''
b = '''    text = re.sub(r"-home-[A-Za-z0-9_]+-[A-Za-z0-9_-]*", "<project-dir>", text)
    text = re.sub(r"/tmp/claude-\\d+", "<tmp-root>", text)
    text = re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "<uuid>", text, flags=re.I)
    return re.sub(r"/home/[A-Za-z0-9_.-]+", "~", text)'''
assert t.count(a) == 1
t = t.replace(a, b)
t = t.replace('"edit_package_1.py", "edit_package_2.py", "antipattern-rows.md"):',
              '"edit_package_1.py", "edit_package_2.py", "edit_package_3.py", "antipattern-rows.md"):')
assert "edit_package_3.py" in t
p.write_text(t)
print("ok")
