"""One-off edit before dispatch: refuse a `..` segment right after an allowed Codex-home directory, too."""
from pathlib import Path

p = Path(__file__).resolve().parent / "void_patterns_final.py"
t = p.read_text()
a = r"""(?![^\s'\"]*/\.\.)))","""
b = r"""(?!(?:[^\s'\"]*/)?\.\.)))","""
assert t.count(a) == 1
p.write_text(t.replace(a, b))
print("ok")
