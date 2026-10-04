#!/usr/bin/env python3
"""Does `install-hooks --apply` (2.4.1) keep unrelated content byte-for-byte when the file was
last written by another tool? Synthetic scratch files only; runs inside a private user+net
namespace when called with `inner`. Also checks the wave-1 precedent on ~/.codex/hooks.json
(value-free: booleans and counts only)."""
import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
VW = HOME / ".local/state/native-agent-stack/sota-refresh-20260925/wave2/ai-memory/verify"
V241 = HOME / ".local/share/codex-ecosystem/tools/ai-memory-2.4.1/ai-memory"
OLD, NEW = "tools/ai-memory-2.4.0/ai-memory", "tools/ai-memory-2.4.1/ai-memory"
FD = VW / "format-probe"


def env():
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(VW / "home"), "TMPDIR": str(VW / "tmp"),
            "AI_MEMORY_SERVER_URL": "http://127.0.0.1:9", "AI_MEMORY_BACKFILL_ON_START": "false"}


def path_only(a, b):
    al, bl = a.splitlines(), b.splitlines()
    ch = [(x, y) for x, y in zip(al, bl) if x != y]
    return len(al) == len(bl) and all(x.replace(OLD, NEW) == y for x, y in ch), len(ch), len(al), len(bl)


def inner():
    base = json.loads((VW / "hooks/claude-code-2.4.0.json").read_text())
    # Simulate another tool's edit: extra keys in unsorted order, non-ASCII text, Python json.dump styles.
    edited = {"zzLast": {"b": 1, "a": [1, 2, {"y": "ÿ", "x": None}]}, **base,
              "skillOverrides": {"tdd": "off", "codeql": "on"}, "permissions": {"deny": [], "allow": ["Bash(ls:*)"]},
              "note": "café – ü"}
    out = {}
    variants = {"py_indent2_ascii": json.dumps(edited, indent=2) + "\n",
                "py_indent2_utf8": json.dumps(edited, indent=2, ensure_ascii=False) + "\n",
                "py_indent4": json.dumps(edited, indent=4) + "\n",
                "py_compact": json.dumps(edited)}
    for name, text in variants.items():
        f = FD / f"{name}.json"
        f.write_text(text)
        r = subprocess.run([str(V241), "--data-dir", str(VW / "hooks/dd"), "install-hooks", "--apply", "--agent", "claude-code",
                            "--config-file", str(f), "--server-url", "http://127.0.0.1:49474", "--capture-mode",
                            "allowlist", "--no-capture-prompts"], env=env(), capture_output=True, text=True, timeout=120)
        after = f.read_text()
        ok, n, la, lb = path_only(text, after)
        out[name] = {"rc": r.returncode, "path_only": ok, "lines_changed": n, "lines_before": la, "lines_after": lb,
                     "semantic_equal_after_path_swap": json.loads(text.replace(OLD, NEW)) == json.loads(after)}
    return out


def main():
    if sys.argv[1:] == ["inner"]:
        print(json.dumps(inner()))
        return
    FD.mkdir(mode=0o700, exist_ok=True)
    (FD / "dd").mkdir(mode=0o700, exist_ok=True)
    r = subprocess.run(["unshare", "--user", "--map-root-user", "--net", "--", sys.executable, __file__, "inner"],
                       capture_output=True, text=True, timeout=300)
    res = {"synthetic": json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else r.stderr[-400:]}
    # Wave-1 precedent: the 16:44:20 install-hooks run on the real Codex file (2.3.2 -> 2.4.0).
    bak = (HOME / ".codex/hooks.json.bak-1790369060").read_text()
    cur = (HOME / ".codex/hooks.json").read_text()
    al, bl = bak.splitlines(), cur.splitlines()
    ch = [(x, y) for x, y in zip(al, bl) if x != y]
    res["wave1_codex_real_file"] = {
        "same_line_count": len(al) == len(bl), "lines_changed": len(ch),
        "path_only_2.3.2_to_2.4.0": len(al) == len(bl) and all(
            x.replace("tools/ai-memory-2.3.2/ai-memory", OLD) == y for x, y in ch),
        "bak_cmds_2.3.2": bak.count("tools/ai-memory-2.3.2/ai-memory"), "cur_cmds_2.4.0": cur.count(OLD)}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
