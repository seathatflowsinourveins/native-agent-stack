"""One-off edit of package_lane_a.py: publish the README, the verification script, the exposure scan and the token
counts at the lane-a root and in final/adjudication/."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "package_lane_a.py"
t = p.read_text()
a = '''    copy(AD / f, f"{FA}/{f}")
print(len(written)'''
b = '''    copy(AD / f, f"{FA}/{f}")
for f in ("token-counts-base.txt", "token-counts-after.txt"):
    copy(AD / f, f"{FA}/{f}")
copy(AD / "README.lane-a.md", "README.md")
copy(AD / "verify_lane_a.py", "verify_lane_a.py")
copy(W3 / "exposure_scan_dir.py", "exposure_scan_dir.py")
print(len(written)'''
assert t.count(a) == 1
t = t.replace(a, b)
t = t.replace('"edit_package_5.py", "antipattern-rows.md"):', '"edit_package_5.py", "edit_package_6.py", "antipattern-rows.md"):')
assert "edit_package_6.py" in t
p.write_text(t)
print("ok")
