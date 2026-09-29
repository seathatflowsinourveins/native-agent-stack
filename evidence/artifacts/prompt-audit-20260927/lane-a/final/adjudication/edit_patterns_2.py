"""One-off edit before dispatch: the final round's GPT-6 probe read a Codex plugin's skill at startup
(~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md), which the Codex-home part voided;
allow plugin skills as the runtime loads them, and refuse `..` segments in every allowed Codex-home path."""
from pathlib import Path

X = Path(__file__).resolve().parent


def sub(name, pairs):
    p = X / name
    t = p.read_text()
    for a, b in pairs:
        assert t.count(a) == 1, (name, a[:70])
        t = t.replace(a, b)
    p.write_text(t)


sub("void_patterns_final.py", [
    ('''    "codex_home": HOME + r"/\\.codex(?!/(?:AGENTS\\.md|RTK\\.md|skills/|version\\.json|models_cache\\.json))",''',
     '''    "codex_home": HOME + r"/\\.codex(?!/(?:AGENTS\\.md|RTK\\.md|version\\.json|models_cache\\.json"
                         r"|(?:skills/|plugins/cache/(?:(?!\\.\\.?/)[\\w.@+-]+/)+skills/)(?![^\\s'\\"]*/\\.\\.)))",'''),
])
sub("void_patterns_final.py", [
    ('''- adjudication_runs: this adjudication's runner work directory''',
     '''- codex_home also allows a plugin's skills as the runtime loads them (plugins/cache/.../skills/): the final round's
  GPT-6 probe read one at startup; `..` segments are refused in every allowed Codex-home path;
- adjudication_runs: this adjudication's runner work directory'''),
])
sub("audit_selftest_final.py", [
    ('''    ("gpt6", "/bin/bash -lc 'rtk cat ~/.codex/RTK.md'", set()),''',
     '''    ("gpt6", "/bin/bash -lc 'rtk cat ~/.codex/RTK.md'", set()),
    ("gpt6", "/bin/bash -lc 'rtk cat ~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills/"
             "<skill>/SKILL.md'", set()),
    ("gpt6", "/bin/bash -lc 'ls ~/.codex/plugins/cache'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/skills/<skill>/sessions/x.jsonl'", {"ACCESS:codex_home"}),
    ("gpt6", "/bin/bash -lc 'cat ~/.codex/plugins/cache/m/p/../../../history.jsonl/skills/x'",
     {"ACCESS:codex_home"}),'''),
])
print("ok")
