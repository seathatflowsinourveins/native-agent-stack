#!/usr/bin/env python3
"""Ground truth for --login-shell: run the real bash -l over every combination of startup-file states and compare (a FIFO, which blocks bash, has its own case).

Each file set to `content` exports MARK=<its name>; the observed MARK is therefore the file bash actually read. The static model
predicts it: the first existing file when that file has content, else nothing (an empty or unusable file ends the search).
The MARK is empty for most combinations (344 of 512: an empty, unusable or unreadable first file), so it cannot show which file the model called `first_read`: since 2026-09-30 (a cross-family review) the
sweep also requires first_read to be the first startup file that exists and is not a dangling link, and the script exits 1 on any mismatch or when the negative control never disagrees with bash.
usage: python3 -B login_shell_bash_truth.py <worktree>
"""
import itertools, os, shutil, subprocess, sys, tempfile
from pathlib import Path

worktree = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(worktree))
from scripts.adoption_status import LOGIN_SHELL_FILES, login_shell

STATES = ("absent", "empty", "content", "directory", "dangling", "linked", "devnull", "unreadable")
bash = shutil.which("bash")
print("bash:", subprocess.run([bash, "--version"], capture_output=True, text=True).stdout.splitlines()[0][:60])
mismatch, checked, control_disagreements = [], 0, 0
for combo in itertools.product(STATES, repeat=3):
    work = Path(tempfile.mkdtemp(prefix="login-truth-"))
    try:
        for (key, name), state in zip(LOGIN_SHELL_FILES.items(), combo):
            target = work / name
            if state == "empty":
                target.write_bytes(b"")
            elif state == "content":
                target.write_text(f"MARK={key}; export MARK\n")
            elif state == "directory":
                target.mkdir()
            elif state == "dangling":
                target.symlink_to(work / "nowhere")
            elif state == "devnull":
                target.symlink_to("/dev/null")
            elif state == "unreadable":
                target.write_text(f"MARK={key}; export MARK\n")
                target.chmod(0)
            elif state == "linked":
                real = work / f"real-{key}"
                real.write_text(f"MARK={key}; export MARK\n")
                target.symlink_to(real)
        got = login_shell({"HOME": str(work)})
        wrong_first = next((k for k, s in got.items() if k in LOGIN_SHELL_FILES and s not in ("absent", "empty")), None)
        wrong_expected = wrong_first if wrong_first is not None and got[wrong_first] == "content" else ""
        run = subprocess.run([bash, "-l", "-c", 'printf %s "$MARK"'], env={"HOME": str(work)}, capture_output=True, text=True, timeout=30)
        first = got["first_read"]
        truth_first = next((k for k, s in zip(LOGIN_SHELL_FILES, combo) if s not in ("absent", "dangling")), None)
        if first != truth_first:
            mismatch.append((combo, "first_read", first, truth_first))
        expected = first if first is not None and got[first] == "content" else ""
        if run.stdout != expected:
            mismatch.append((combo, got, run.stdout, run.stderr.strip()[:80]))
        # profile_read: true means ~/.profile is what ran; false means it did not run (and does not exist or was hidden)
        if got["profile_read"] is True and run.stdout not in ("profile", ""):
            mismatch.append((combo, "profile_read true but", run.stdout))
        if got["profile_read"] is False and run.stdout == "profile" and got["profile"] != "absent":
            mismatch.append((combo, "profile_read false but profile ran", run.stdout))
        checked += 1
        if run.stdout != wrong_expected:
            control_disagreements += 1
    finally:
        for child in work.iterdir():
            if child.is_file() and not child.is_symlink():
                child.chmod(0o600)
        shutil.rmtree(work, ignore_errors=True)
# a FIFO cannot join the sweep (bash blocks at open); one case shows the block, and that the model still calls it unusable and unread
work = Path(tempfile.mkdtemp(prefix="login-truth-fifo-"))
try:
    os.mkfifo(work / ".bash_profile")
    (work / ".profile").write_text("MARK=profile; export MARK\n")
    fifo_model = login_shell({"HOME": str(work)})
    try:
        subprocess.run([bash, "-l", "-c", 'printf %s "$MARK"'], env={"HOME": str(work)}, capture_output=True, text=True, timeout=3)
        fifo_blocked = False
    except subprocess.TimeoutExpired:
        fifo_blocked = True
finally:
    shutil.rmtree(work, ignore_errors=True)
print("FIFO .bash_profile: bash blocked:", fifo_blocked, "| model:", fifo_model["bash_profile"], fifo_model["first_read"], fifo_model["profile_read"])
# stat errors that are neither ENOENT nor a readable file: a symlink loop (ELOOP), HOME being a regular file (ENOTDIR) and a HOME the user cannot
# search (EACCES). Each must end the search in bash (nothing read, MARK empty) and be called unusable by the model.
other_errors = {}
work = Path(tempfile.mkdtemp(prefix="login-truth-errors-"))
try:
    (work / "loop").mkdir()
    (work / "loop" / ".bash_profile").symlink_to(".bash_profile")
    (work / "loop" / ".profile").write_text("MARK=profile; export MARK\n")
    (work / "file").write_text("x\n")
    closed = work / "closed"
    closed.mkdir()
    (closed / ".profile").write_text("MARK=profile; export MARK\n")
    closed.chmod(0)
    for label, home in (("symlink loop (ELOOP)", work / "loop"), ("HOME is a regular file (ENOTDIR)", work / "file"), ("HOME not searchable (EACCES)", closed)):
        model = login_shell({"HOME": str(home)})
        seen = subprocess.run([bash, "-l", "-c", 'printf %s "$MARK"'], env={"HOME": str(home)}, capture_output=True, text=True, timeout=30).stdout
        other_errors[label] = (model["bash_profile"], model["profile_read"], seen)
    closed.chmod(0o700)
finally:
    shutil.rmtree(work, ignore_errors=True)
for label, (state, profile_read, seen) in other_errors.items():
    print(f"{label}: model {state}/{profile_read} | bash read nothing: {seen == ''}")
    if (state, profile_read, seen) != ("unusable", False, ""):
        mismatch.append((label, state, profile_read, seen))
if not fifo_blocked or (fifo_model["bash_profile"], fifo_model["first_read"], fifo_model["profile_read"]) != ("unusable", "bash_profile", False):
    mismatch.append(("fifo", fifo_model, fifo_blocked))
print("combinations checked:", checked, "| mismatches:", len(mismatch),
      "| negative control (empty file treated as absent) disagrees with real bash in", control_disagreements, "combinations")
for item in mismatch[:8]:
    print("  ", item)
sys.exit(1 if mismatch or control_disagreements == 0 else 0)
