"""Mutation check of the hash-list rule review: each mutant of tools/adoption/codex_hook_trust.py must fail at least one test of
tests/test_codex_hook_trust.py. Run from the repository root; it works on a temporary copy, the checkout is not touched.

The tests were written after the code, so this is the check that they are not vacuous: a mutant that survives names an untested decision. A mutant of
the ASCII decode in is_allow_only is not listed: both regular expressions admit only printable ASCII, so it is equivalent.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
LISTING = ('    try:\n        entries = os.scandir(directory)\n    except FileNotFoundError:\n        return []\n    found = []\n    with entries:\n'
           '        for entry in entries:\n            regular = stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode)\n'
           '            if regular and Path(entry.name).suffix == ".rules":\n                found.append(directory / entry.name)\n    return sorted(found)')
GRAMMAR = ('    return all(line == "" or (ALLOW_LINE.fullmatch(line) and REWRITE_WORD not in line) or COMMENT_LINE.fullmatch(line) for line in text.split("\\n"))')
MUTANTS = {
    # listing (705e finding 1, 705f P1-5)
    "a FileNotFoundError on an entry or the iteration reads as no rules": (
        LISTING,
        '    found = []\n    try:\n        with os.scandir(directory) as entries:\n            for entry in entries:\n'
        '                regular = stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode)\n                if regular and Path(entry.name).suffix == ".rules":\n'
        '                    found.append(directory / entry.name)\n    except FileNotFoundError:\n        return []\n    return sorted(found)'),
    "an open error reads as no rules": ("    except FileNotFoundError:\n        return []", "    except OSError:\n        return []"),
    "the extension is looked at before the file type (an error on another entry is not seen)": (
        '            regular = stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode)\n            if regular and Path(entry.name).suffix == ".rules":',
        '            if Path(entry.name).suffix == ".rules" and stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode):'),
    "a symlink is followed": ("entry.stat(follow_symlinks=False).st_mode", "entry.stat().st_mode"),
    "anything but a directory is loaded (a named pipe is opened)": ("regular = stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode)",
                                                                   "regular = not stat.S_ISDIR(entry.stat(follow_symlinks=False).st_mode)"),
    "any name that ends in rules is loaded": ('Path(entry.name).suffix == ".rules"', 'entry.name.endswith("rules")'),
    "the listing is not sorted": ("    return sorted(found)", "    return found"),
    # the allow-only grammar
    "a prompt rule is allow-only": ("""decision="allow"\\)')""", """decision="(?:allow|prompt)"\\)')"""),
    "a token may hold a quote": ("""TOKEN = r'"[ !#-\\[\\]-~]+"'""", """TOKEN = r'"[ -\\[\\]-~]+"'"""),
    "a token may hold a backslash": ("""TOKEN = r'"[ !#-\\[\\]-~]+"'""", """TOKEN = r'"[ !#-~]+"'"""),
    "a comment may hold a backslash": ('COMMENT_LINE = re.compile(r"#[ -\\[\\]-~]*")', 'COMMENT_LINE = re.compile(r"#[ -~]*")'),
    "a comment may hold a tab or a CR": ('COMMENT_LINE = re.compile(r"#[ -\\[\\]-~]*")', 'COMMENT_LINE = re.compile(r"#[^\\n\\\\]*")'),
    "a line may be followed by more": (GRAMMAR, GRAMMAR.replace("ALLOW_LINE.fullmatch(line)", "ALLOW_LINE.match(line)")),
    "one allow line is enough": (GRAMMAR, GRAMMAR.replace("return all(", "return any(")),
    "an empty line is not allowed": (GRAMMAR, GRAMMAR.replace('line == "" or ', "")),
    "an allow rule that names rtk is allow-only (it matches the rewritten command and not the original)": (GRAMMAR, GRAMMAR.replace(" and REWRITE_WORD not in line", "")),
    "only an allow rule that starts with rtk is refused": (GRAMMAR, GRAMMAR.replace("REWRITE_WORD not in line", """not line.startswith('prefix_rule(pattern=["rtk"')""")),
    "any token that contains the letters rtk is refused": ("""REWRITE_WORD = '"rtk"'""", """REWRITE_WORD = 'rtk'"""),
    "any line is a comment": (GRAMMAR, GRAMMAR.replace("COMMENT_LINE.fullmatch(line)", "True")),
    "a space-separated token list is not required": (
        'ALLOW_LINE = re.compile(rf\'prefix_rule\\(pattern=\\[{TOKEN}(?:, {TOKEN})*\\], decision="allow"\\)\')',
        'ALLOW_LINE = re.compile(rf\'prefix_rule\\(pattern=\\[{TOKEN}(?:,\\s*{TOKEN})*\\], decision="allow"\\)\')'),
    "a pattern may be empty": (
        'ALLOW_LINE = re.compile(rf\'prefix_rule\\(pattern=\\[{TOKEN}(?:, {TOKEN})*\\], decision="allow"\\)\')',
        'ALLOW_LINE = re.compile(rf\'prefix_rule\\(pattern=\\[(?:{TOKEN}(?:, {TOKEN})*)?\\], decision="allow"\\)\')'),
    # the reviewed list
    "a hash with trailing characters is a hash": ('re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])', 're.match(r"[0-9a-f]{64}", entry["sha256"])'),
    "an uppercase hash is a hash": ('re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])', 're.fullmatch(r"[0-9a-fA-F]{64}", entry["sha256"])'),
    "an entry with another version output is well formed": ('.startswith("rtk ")', '.startswith("")'),
    "a malformed list is read as empty": ("        raise ReviewError(f\"cannot read {REVIEWED_FILE.name}: {error}\") from error", "        return {}"),
    "a broken list does not block": ("        review.problems.append(str(error))\n        reviewed = {}", "        reviewed = {}"),
    "the list is read although there is no rule file": ("    if not review.files:\n        return review\n    try:\n        reviewed = load_reviewed()",
                                                       "    try:\n        reviewed = load_reviewed()"),
    # the decision per file
    "a file is reviewed whatever its hash": ("        if digest in reviewed:", "        if True:"),
    "a file is allow-only whatever its bytes": ("        elif is_allow_only(data):", "        elif True:"),
    "an unreadable file does not block": ('            review.problems.append(f"cannot read {path.name}: {error}")', "            pass"),
    "rtk is asked for allow-only files as well": ("    if applied:\n        try:", "    if True:\n        try:"),
    "a failed rtk step does not block": ("            review.problems.append(str(error))\n    return review", "            pass\n    return review"),
    "a file that is not accepted is not an exposure": ("            review.exposed.append(f\"{path.name} (sha256", "            review.allow_only.append(f\"{path.name} (sha256"),
    # what a reviewed file depends on
    "the version gate is dropped": ("if done.returncode != 0 or reported not in reviewed:", "if False:"),
    "the version command's exit status is ignored": ("if done.returncode != 0 or reported not in reviewed:", "if reported not in reviewed:"),
    "an unreadable rtk config is accepted (exit status)": ('if done.returncode != 0 or not first.startswith("Config: "):', 'if not first.startswith("Config: "):'),
    "an unreadable rtk config is accepted (no Config line)": ('if done.returncode != 0 or not first.startswith("Config: "):', "if done.returncode != 0:"),
    "configured transparent prefixes are ignored": ('if not re.search(r"^transparent_prefixes = \\[\\]$", body, re.M):', "if False:"),
    "the transparent_prefixes line is matched only at the start of the output": ('r"^transparent_prefixes = \\[\\]$", body, re.M)', 'r"^transparent_prefixes = \\[\\]$", body)'),
    "trusted TOML filters are ignored": ('    if done.returncode != 0 or (done.stdout or "").strip() != NO_TRUSTED_FILTERS:', "    if False:"),
    "the trust list's exit status is ignored": ('    if done.returncode != 0 or (done.stdout or "").strip() != NO_TRUSTED_FILTERS:', '    if (done.stdout or "").strip() != NO_TRUSTED_FILTERS:'),
    "the trust list is matched loosely (the phrase anywhere in the output)": (
        '    if done.returncode != 0 or (done.stdout or "").strip() != NO_TRUSTED_FILTERS:', '    if done.returncode != 0 or NO_TRUSTED_FILTERS not in (done.stdout or ""):'),
    "the trust override variable is ignored": ("    if TRUST_ENV in os.environ:", "    if False:"),
    "only the value 1 of the trust override variable counts": ("    if TRUST_ENV in os.environ:", '    if os.environ.get(TRUST_ENV) == "1":'),
    "user-global TOML filters are ignored": ("    if filters.exists():", "    if False:"),
    "the schema line is a filter": ("if line and not SCHEMA_LINE.fullmatch(line)]", "if line]"),
    "comments are filters": ('(re.sub(r"#.*$", "", row).strip() for row in text.splitlines())', "(row.strip() for row in text.splitlines())"),
    "an unreadable filters file is accepted": ('        except (OSError, ValueError) as error:\n            raise ReviewError(f"cannot read rtk\'s {filters.name} ({error})") from error',
                                               '        except (OSError, ValueError) as error:\n            text = ""'),
    "a filters file that is not UTF-8 raises instead of failing closed": ("        except (OSError, ValueError) as error:\n            raise ReviewError(f\"cannot read rtk's",
                                                                           "        except OSError as error:\n            raise ReviewError(f\"cannot read rtk's"),
    "no rtk executable is accepted": ('        raise ReviewError("no rtk executable on PATH (or --rtk): a reviewed rule file applies to one rtk version")', "        return []"),
    "rtk is not looked up on the PATH": ('    rtk = rtk or shutil.which("rtk")', "    rtk = rtk"),
    "an rtk that cannot be run is accepted": ("        raise ReviewError(f\"cannot run {command[0]}: {error}\") from error", "        return subprocess.CompletedProcess(command, 0, '', '')"),
    "a non-text rtk output raises instead of failing closed": ("except (OSError, ValueError, subprocess.SubprocessError) as error:  # ValueError: output that is not text",
                                                              "except (OSError, subprocess.SubprocessError) as error:"),
    "rtk runs with telemetry on": ('"RTK_TELEMETRY_DISABLED": "1"', '"RTK_TELEMETRY_DISABLED": "0"'),
    "rtk may wait for a terminal": ("stdin=subprocess.DEVNULL, capture_output=True", "capture_output=True"),
    "rtk may run without a time limit": ("timeout=30, check=False", "timeout=None, check=False"),
    # the flow
    "--apply does not refuse on an exposure": ("    if args.apply and blocked:", "    if False:"),
    "the flag does not accept an exposure": ("    blocked = review.blocked and not args.allow_exec_rules", "    blocked = review.blocked"),
    "the flag accepts nothing": ("    blocked = review.blocked and not args.allow_exec_rules", "    blocked = False"),
    "--check ignores an exposure": ('                if blocked:\n                    print("not accepted:', '                if False:\n                    print("not accepted:'),
    "--check says 6 before 5": ("                if todo:\n                    print(\"not trusted: \"", "                if todo and not blocked:\n                    print(\"not trusted: \""),
    "the --rtk flag is not passed to the review": ("    review = review_rules(home, args.rtk)", "    review = review_rules(home, None)"),
    "a dry run does not say the apply would refuse": ('                if blocked:\n                    print("note: --apply would refuse', '                if False:\n                    print("note: --apply would refuse'),
}

with tempfile.TemporaryDirectory(prefix="mutants-") as scratch:
    base = Path(scratch) / "base"
    (base / "tools").mkdir(parents=True)
    shutil.copytree(root / "tools" / "adoption", base / "tools" / "adoption")
    (base / "tests").mkdir()
    shutil.copy(root / "tests" / "test_codex_hook_trust.py", base / "tests")
    (base / "scripts").symlink_to(root / "scripts")
    e2e = Path("evidence/artifacts/token-stack-fresh-session-e2e-20261004")
    (base / e2e).parent.mkdir(parents=True)
    shutil.copytree(root / e2e, base / e2e)
    plan_config = Path("evidence/artifacts/new-wsl-install-plan-20261002/config")
    if (root / plan_config).is_dir():
        (base / plan_config).parent.mkdir(parents=True)
        shutil.copytree(root / plan_config, base / plan_config)
    (base / "adoption").mkdir()
    shutil.copy(root / "adoption" / "pins-linux-x86_64.json", base / "adoption")
    for entry in json.loads((root / "tools" / "adoption" / "exec_rules_reviewed.json").read_text(encoding="utf-8"))["entries"]:
        for cited in entry["evidence"]:  # the tests check that every cited file exists
            (base / cited).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(root / cited, base / cited)
    tool = base / "tools" / "adoption" / "codex_hook_trust.py"
    original = tool.read_text(encoding="utf-8")

    def run_tests():
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "tests.test_codex_hook_trust"], cwd=base, capture_output=True, text=True)
        tail = done.stderr.strip().splitlines()[-1] if done.stderr.strip() else done.stdout[-80:]
        return done.returncode, tail

    base_code, base_tail = run_tests()
    print("baseline:", base_code, base_tail)
    if base_code:
        print(subprocess.run([sys.executable, "-B", "-m", "unittest", "tests.test_codex_hook_trust"], cwd=base, capture_output=True, text=True).stderr[-1500:])
        sys.exit("the baseline must pass")
    survivors = []
    for name, (old, new) in MUTANTS.items():
        if original.count(old) != 1:
            print(f"!! cannot apply: {name} ({original.count(old)} matches)")
            survivors.append(name)
            continue
        tool.write_text(original.replace(old, new), encoding="utf-8")
        code, tail = run_tests()
        print(f"{'killed' if code else 'SURVIVED'}: {name}: {tail}")
        if not code:
            survivors.append(name)
    tool.write_text(original, encoding="utf-8")
    print(f"{len(MUTANTS)} mutants, survivors: {survivors}")
    sys.exit(1 if survivors else 0)
