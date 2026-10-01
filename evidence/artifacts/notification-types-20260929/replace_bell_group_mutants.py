#!/usr/bin/env python3
"""Negative controls for replace_bell_group_controls.py: each mutant is a copy of replace_bell_group.py with one guard removed (a literal replacement in a temporary checkout copy under a
private temporary directory; the checkout itself is never touched), and the controls are run against it. A mutant must make exactly the named cases fail (an exact set, not "some case"),
so a control that passes whatever the script does would show here. The unmutated script is run first and must pass all cases.
usage: python3 -B replace_bell_group_mutants.py <checkout>"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

CHECKOUT = Path(sys.argv[1]).resolve()
ART = "evidence/artifacts/notification-types-20260929"
CONTROLS = CHECKOUT / ART / "replace_bell_group_controls.py"
SCRIPT_TEXT = (CHECKOUT / ART / "replace_bell_group.py").read_text(encoding="utf-8")
FILES = ["adoption/templates/claude.settings.linux-wsl2.overlay.json", "tools/adoption/apply_claude_settings.py", f"{ART}/replace_bell_group.py", f"{ART}/concurrent_writer_harness.py"]

APPLY_OLD = 'acs.atomic_write(live_path, new_bytes.decode("utf-8"), mode)'
APPLY_FIXED_NAME = 'staging = live_path.parent / (live_path.name + ".new"); staging.write_bytes(new_bytes); os.chmod(staging, mode); os.replace(staging, live_path)'
MUTANTS = [
    ("the staging file has the fixed name again (a symlink at that name is followed)", APPLY_OLD, APPLY_FIXED_NAME, {"--apply does not follow a symlink at the old fixed staging name"}),
    ("the bell hook's extra keys are no longer checked", "if extra_keys:", "if False:",
     {"a bell hook with a key beyond type and command is refused", "a current matcher on a bell hook with an extra key is refused, not reported as nothing to do"}),
    ("the matcher is no longer compared with the overlay's", "if held_types is None or not held_types <= want_types:", "if False:",
     {"a matcher naming a type the overlay's does not is refused, not dropped, and the refusal names no matcher value", "an absent matcher is refused"}),
    ("'nothing to do' looks at the matcher only", "if len(holders) == 1 and holders[0] == overlay_group and acs.merge_settings(before, overlay) == before:",
     'if len(holders) == 1 and holders[0].get("matcher") == want_matcher:',
     {"an equal bell group is not 'nothing to do' while the overlay's own keys are missing", "a current matcher on a bell hook with an extra key is refused, not reported as nothing to do"}),
    ("'nothing to do' ignores whether the bell group equals the overlay's", "if len(holders) == 1 and holders[0] == overlay_group and acs.merge_settings(before, overlay) == before:",
     "if len(holders) == 1 and acs.merge_settings(before, overlay) == before:",
     {"an old matcher with the overlay's own keys already present is replaced, not 'nothing to do'", "a current matcher on a bell hook with an extra key is refused, not reported as nothing to do"}),
    ("an existing overlay key may be overwritten", "if overwritten:", "if False:", {"an existing different preferredNotifChannel is refused, not overwritten"}),
    ("no backup is taken", "backup = acs.write_backup(live_path)", "backup = live_path",
     {"--apply installs the merged copy after a backup equal to the original, keeps the mode, leaves no staging file", "--apply does not follow a symlink at the old fixed staging name",
      "a save that lands while the backup is taken is refused, the backup holds it and nothing is installed", "--apply keeps a file mode other than 0600 on the installed file and on its backup",
      'a save that lands after the backup was taken is refused, the backup equals the read and nothing is installed', 'a save at the rename itself is the documented residual, exit 0, with that save in neither the installed file nor the backup', 'an atomic save that replaces the file while the backup is being copied is refused, the backup equals the read and nothing is installed'}),
    ("the live file is not compared with the read before the backup", '        if live_path.read_bytes() != original:\n            refuse("the settings file changed since it was read (another writer saved it); nothing was written, run the tool again")\n', "        pass\n",
     {"a settings file saved by another writer after the read is refused, before any backup, and that save is kept"}),
    ("the live file is not compared with the read right before the replace", '        if live_path.read_bytes() != original:\n            refuse("the settings file changed after it was backed up; the backup holds the bytes that were read and nothing was installed, run the tool again")\n', "        pass\n",
     {'a save that lands after the backup was taken is refused, the backup equals the read and nothing is installed', 'an atomic save that replaces the file while the backup is being copied is refused, the backup equals the read and nothing is installed'}),
    ("the backup is not compared with the read", '        if backup.read_bytes() != original:\n            refuse("the settings file changed while it was backed up; the backup holds the newer content and nothing was installed, run the tool again")\n', "        pass\n",
     {"a save that lands while the backup is taken is refused, the backup holds it and nothing is installed"}),
    ("another hook in the bell group is no longer refused", "if len(acs.hook_list(holder)) != 1:", "if False:", {"another hook in the bell group is refused, not lost"}),
    ("keys beyond matcher and hooks on the bell group are no longer refused", "if extra_group_keys:", "if False:", {"a bell group with a key beyond matcher and hooks is refused, not silently replaced"}),
    ("the file mode is not kept", 'acs.atomic_write(live_path, new_bytes.decode("utf-8"), mode)', 'acs.atomic_write(live_path, new_bytes.decode("utf-8"), 0o600)',
     {"--apply keeps a file mode other than 0600 on the installed file and on its backup"}),
    ("two bell groups are no longer refused", "if len(holders) > 1:", "if False:", {"two bell groups are refused"}),
    ("a symlinked settings file is no longer refused up front", "if live_path.is_symlink():", "if False:", {"a symlinked settings file is refused, also with --apply, and the real file is untouched"}),
]


def failing_cases(checkout):
    result = subprocess.run([sys.executable, "-B", str(CONTROLS), str(checkout)], capture_output=True, text=True, timeout=600)
    return result.returncode, {m.group(1) for m in re.finditer(r"^WRONG {4}(.+?): exit ", result.stdout, re.M)}, result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


bad = 0
code, failed, summary = failing_cases(CHECKOUT)
ok = code == 0 and not failed
bad += 0 if ok else 1
print(("ok    " if ok else "WRONG ") + f"the unmutated script passes every case: exit {code}, {summary}")
for name, old, new, expected in MUTANTS:
    assert SCRIPT_TEXT.count(old) == 1, f"mutation site not found exactly once: {old[:60]}"
    with tempfile.TemporaryDirectory(prefix="rbm") as raw:
        copy = Path(raw)
        for relative in FILES:
            (copy / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CHECKOUT / relative, copy / relative)
        (copy / ART / "replace_bell_group.py").write_text(SCRIPT_TEXT.replace(old, new), encoding="utf-8")
        code, failed, summary = failing_cases(copy)
    ok = code != 0 and failed == expected
    bad += 0 if ok else 1
    print(("ok    " if ok else "WRONG ") + f"mutant, {name}: controls exit {code}, failing cases {len(failed)} (expected {len(expected)})" + ("" if ok else f" | unexpected {sorted(failed - expected)}, missed {sorted(expected - failed)}"))
print(f"{len(MUTANTS) + 1} runs, {bad} problems")
sys.exit(1 if bad else 0)
