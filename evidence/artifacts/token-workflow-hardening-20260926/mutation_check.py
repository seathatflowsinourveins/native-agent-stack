import shutil, subprocess, sys
from pathlib import Path
W, M, PY = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
MUTANTS = {
    "rtk-compaction-always-true": ('    return re.fullmatch("\\n".join(blocks) + "\\n", output) is not None', '    return True'),
    "rtk-ledger-filter-unchecked": ('saving["total_commands"] == 1 and saving["total_saved"] > 0', 'True'),
    "markitdown-literal-only": ('for candidate in (markdown, unescaped))', 'for candidate in (markdown,))'),
    "ast-grep-ranges-ignored": ('and ranges == AST_GREP_SHELL_CALL_RANGES and text_lines', 'and text_lines'),
    "repomix-bodies-unchecked": ('and all("def greeting(name)" in text and "return" not in text for text in structure.values())', ''),
    "toon-tabular-unchecked": ('tabular.rstrip("\\n") == TOON_TABULAR_RECORDS and ', ''),
}
for name, (old, new) in MUTANTS.items():
    root = M / name
    for part in ("scripts", "tests", "fixtures", "evidence/artifacts/native-token-ci-extension-20260926"):
        shutil.copytree(W / part, root / part, dirs_exist_ok=True)
    for single in ("manifests/stack.json", ".github/workflows/native-token-e2e.yml"):
        (root / single).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(W / single, root / single)
    harness = root / "scripts/native_token_ci.py"
    text = harness.read_text()
    assert text.count(old) == 1, (name, text.count(old))
    harness.write_text(text.replace(old, new))
    r = subprocess.run([PY, "-m", "unittest", "tests.test_native_token_ci"], cwd=root, capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(root)})
    failing = sorted({l.split(" ")[1] for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))})
    summary = [l for l in r.stderr.splitlines() if l.startswith(("FAILED", "OK"))]
    print(f"{name:30} rc={r.returncode} {summary} {failing}")
