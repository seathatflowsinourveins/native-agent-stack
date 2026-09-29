#!/usr/bin/env python3
"""Reproduce, in an isolated HOME, what CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 leaves behind on Linux with bubblewrap installed, and
whether a real ~/.bash_profile that hands off to ~/.profile survives it. The real HOME is never touched: every arm runs the
installed native binary with `env -i`, a throwaway HOME inside a private temporary directory, a dummy non-credential API value
(the run stops at the API-key check after the files are written, so no model call is made) and no settings, hooks or telemetry.
The client also touches one absolute path outside any home, /tmp/inline-comments-buffer.jsonl (its startup code opens a fixed list of paths
in append mode, which creates a missing file and never truncates an existing one), and keeps per-directory state under /tmp/claude-<uid>/.
The script removes the shared file only if it was absent before the run and the run created it, removes only the /tmp/claude-<uid> entries
that appeared during an arm and carry that arm's own directory name, and checks the isolation claim itself: the presence of the placeholder
names in the real home is recorded before and after and must be unchanged. In the stock-home arm it also runs the installed `claude doctor`
(which warns about stale sandbox mask files since 2.1.257) and records whether that warning names the scrub-created file.

usage: python3 scrub_placeholder_probe.py [--keep]      prints one JSON summary of counts, names and booleans; no paths, no output text
Arms: A control without the variable; B the variable with a stock Ubuntu-shaped HOME (~/.profile only); C the variable with a real
~/.bash_profile that sources ~/.profile.
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

CLAUDE = Path.home() / ".local/bin/claude"        # symlink to the native binary; the ecosystem launcher is not involved
DUMMY = "dummy-value-not-a-credential"
HAND_OFF = '# hand off to ~/.profile so a generated file can never hide it\nif [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi\n'


def listing(root):
    """Relative name -> (type, size) for every entry under root, without following links."""
    found = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            found[rel] = ("link", 0)
        elif path.is_dir():
            found[rel] = ("dir", 0)
        else:
            found[rel] = ("file", path.stat().st_size)
    return found


SHARED = Path("/tmp/inline-comments-buffer.jsonl")   # the client hard-codes /tmp, whatever TMPDIR says


def empty_dirs(root, created):
    """Created directories that hold no entry after the run."""
    return sorted(k for k, v in created.items() if v[0] == "dir" and not any(other.startswith(k + "/") for other in listing(root)))


REAL_HOME_NAMES = [".bash_aliases", ".bash_login", ".bunfig.toml", ".gitmodules", ".netrc", ".npmrc", ".yarnrc", ".yarnrc.yml", ".pip",
                   ".config/pip", ".config/git", ".config/glab-cli", ".config/anthropic", ".claude/seed-admin"]
STATE_ROOT = Path("/tmp") / f"claude-{os.getuid()}"


def real_home_presence():
    return {name: (Path.home() / name).exists() for name in REAL_HOME_NAMES}


def state_entries():
    return set(os.listdir(STATE_ROOT)) if STATE_ROOT.is_dir() else set()


def remove_client_state(before, home):
    """Remove the /tmp/claude-<uid> entries that appeared since `before` and carry this arm's own directory name (letters and digits only)."""
    key = re.sub(r"[^A-Za-z0-9]", "-", home.name)
    removed = []
    for name in sorted(state_entries() - before):
        target = STATE_ROOT / name
        if key in name and target.is_dir() and not target.is_symlink() and target.parent == STATE_ROOT:
            shutil.rmtree(target, ignore_errors=True)
            removed.append(not target.exists())
    return removed


def native_doctor(home, env):
    run = subprocess.run([str(CLAUDE.resolve()), "doctor"], cwd=home / "proj", env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    plain = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", (run.stdout + run.stderr).decode("utf-8", "replace"))
    found = re.search(r"(\d+) warnings? found", plain)
    return {"exit": run.returncode, "warnings_found": int(found.group(1)) if found else None, "mentions_bash_profile": "bash_profile" in plain,
            "mentions_mask_stale_or_placeholder": bool(re.search(r"mask|stale|placeholder", plain, re.I))}


def login_path(home):
    run = subprocess.run(["/usr/bin/env", "-i", f"HOME={home}", "PATH=/usr/bin:/bin", "/bin/bash", "-lc", 'printf "%s" "$PATH"'],
                         capture_output=True, text=True, timeout=30)
    return run.stdout


def arm(label, scrub, real_bash_profile, base, doctor=False):
    state_before = state_entries()
    home = Path(tempfile.mkdtemp(prefix=f"arm-{label}-", dir=base))
    (home / "proj").mkdir()
    (home / ".local/bin").mkdir(parents=True)
    (home / ".profile").write_text('export PATH="$HOME/.local/bin:$PATH"\n')
    if real_bash_profile:
        (home / ".bash_profile").write_text(HAND_OFF)
    before = listing(home)
    before_bash_profile = hashlib.sha256((home / ".bash_profile").read_bytes()).hexdigest() if real_bash_profile else None
    path_before = login_path(home)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": DUMMY, "DISABLE_AUTOUPDATER": "1",
           "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1"}
    if scrub:
        env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"
    run = subprocess.run([str(CLAUDE.resolve()), "-p", "hi", "--max-turns", "1"], cwd=home / "proj", env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, timeout=120)
    after = listing(home)
    doctor_result = native_doctor(home, env) if doctor else None
    created = {k: v for k, v in after.items() if k not in before}
    zero_files = sorted(k for k, v in created.items() if v == ("file", 0))
    result = {
        "arm": label, "scrub_variable": scrub, "real_bash_profile_present_before": real_bash_profile, "client_exit": run.returncode,
        "entries_created": len(created), "empty_files_created": len(zero_files),
        "directories_created": sum(1 for v in created.values() if v[0] == "dir"),
        "empty_directories_created": len(empty_dirs(home, created)),
        "created_in_home_top_level": sorted(k for k in created if "/" not in k),
        "created_in_working_dir": sorted(k.split("/", 1)[1] for k in created if k.startswith("proj/"))[:30],
        "bash_profile_exists_after": (home / ".bash_profile").exists(),
        "bash_profile_empty_after": (home / ".bash_profile").exists() and (home / ".bash_profile").stat().st_size == 0,
        "real_bash_profile_untouched": (hashlib.sha256((home / ".bash_profile").read_bytes()).hexdigest() == before_bash_profile) if real_bash_profile and (home / ".bash_profile").exists() else None,
        "login_path_had_local_bin_before": str(home / ".local/bin") in path_before.split(":"),
        "login_path_has_local_bin_after": str(home / ".local/bin") in login_path(home).split(":"),
    }
    if doctor_result is not None:
        result["native_doctor"] = doctor_result
    result["client_state_entries_removed"] = len(remove_client_state(state_before, home))
    return home, result


def main():
    keep = "--keep" in sys.argv
    base = Path(tempfile.mkdtemp(prefix="scrub-probe-"))
    results = []
    shared_before = SHARED.exists()
    presence_before = real_home_presence()
    try:
        for label, scrub, real in (("A_control_no_scrub", False, False), ("B_scrub_stock_home", True, False), ("C_scrub_real_bash_profile", True, True)):
            _, res = arm(label, scrub, real, base, doctor=(label == "B_scrub_stock_home"))
            results.append(res)
    finally:
        if not keep:
            shutil.rmtree(base, ignore_errors=True)
    created_shared = (not shared_before) and SHARED.exists()
    if created_shared and SHARED.is_file() and SHARED.stat().st_size == 0 and not SHARED.is_symlink():
        SHARED.unlink()
    summary = {"claude": subprocess.run([str(CLAUDE.resolve()), "--version"], capture_output=True, text=True).stdout.strip(),
               "bubblewrap": shutil.which("bwrap") is not None, "bubblewrap_version": subprocess.run(["bwrap", "--version"], capture_output=True, text=True).stdout.strip(),
               "arms": results, "scratch_removed": not base.exists(), "real_home_placeholder_names_unchanged": real_home_presence() == presence_before,
               "shared_temp_file": {"name": SHARED.name, "present_before_run": shared_before, "created_by_run": created_shared,
                                    "removed_by_script": created_shared and not SHARED.exists(), "present_after_script": SHARED.exists()}}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
