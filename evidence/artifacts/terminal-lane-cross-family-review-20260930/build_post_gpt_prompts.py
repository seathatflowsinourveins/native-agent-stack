#!/usr/bin/env python3
"""Write the prompts of the GPT read of the post-merge repair round of the terminal lane (2026-10-01): pull request #563, merged as c99a482e (a squash of its branch; parent dca821cc), read by three lenses (P1 the two pty probes
and the mutant runner, P2 the tmux probes, the three new scripts and the recorded outputs, P3 claims, evidence and hygiene). Derived from build_final_prompts.py (the final read's builder, same directory): the common preamble is
re-used from build_review_prompts.py (its own source, not a copy), the change is described as the merged post-merge round, and the packet is the round's changed files and the merged pull request's own evidence claims. One
prompt per lens is written into each lane's prompts directory (both models read identical prompts).
usage: build_post_gpt_prompts.py <checkout at origin/main> <packets dir> <baseline commit> <merged commit> <merged pull request body file> <prompts dir> [<prompts dir> ...]"""
import re, subprocess, sys
from pathlib import Path

CHECKOUT, PACKETS, BASE, MERGED, BODY = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], sys.argv[4], Path(sys.argv[5])
OUTS = [Path(a) for a in sys.argv[6:]]
for out in OUTS:
    out.mkdir(parents=True, exist_ok=True)
source = (CHECKOUT / "evidence/artifacts/terminal-lane-cross-family-review-20260930/build_review_prompts.py").read_text(encoding="utf-8")
block = source[source.index('COMMON = f"""'):]
block = block[:block.index('"""\n\nUNITS')] + '"""\n'
namespace = {"CHECKOUT": CHECKOUT}
exec(block, namespace)
COMMON = namespace["COMMON"]
COMMON = COMMON.replace("(detached at a commit that contains the change)", "(detached at origin/main, which contains the merged change)")
inspect = re.search(r"Inspect the change with `git -C [^`]+` and `git -C [^`]+`\. Files are read as they are at CHECKOUT; `git log [^`]+` shows later edits by other changes, which are not under review\.", COMMON)
assert inspect, "the inspection sentence of the common preamble was not found"
COMMON = COMMON.replace(inspect.group(0),
    f"The change under review is the POST-MERGE REPAIR ROUND of pull request #563, merged as {MERGED[:8]} (a squash of its whole branch; its parent is {BASE[:8]}); CHECKOUT is origin/main, which contains it and later commits that are not part of it. "
    f"`git -C {CHECKOUT} diff {BASE[:8]} {MERGED[:8]} -- <path>` shows the round's delta for a path. "
    f"The same delta, limited to this lane's paths, is in three patch files that you may read under ~/.local/state as the one exception to the rule below (read only these three): "
    f"{PACKETS}/post-all.diff (everything), {PACKETS}/post-P1.diff (the pty probes and the mutant runner) and {PACKETS}/post-P2.diff (the tmux probes, the new scripts and the recorded outputs). Read them in windows with `sed -n 'A,Bp'`. "
    f"Files are read as they are at CHECKOUT. The two hot shared files `docs/harness-defaults.md` (three new rows and one edited row of its anti-pattern table are this lane's) and `manifests/evidence.json` (registration entries and hashes) are part of the change but are not in the patches.")
COMMON += """

THE EARLIER REVIEWS. Four review rounds already happened on this lane. Round 1 (nine jobs) returned 46 findings; a re-check of its repairs (four jobs) returned 33; a final read (six jobs, two models, three lenses) returned 37; and after the merge of those repairs one read-only Claude Opus agent (no shell) read the
signal handling and shutdown code only and returned 11 (three medium). Every finding was graded by a verifier or checked against the code and repaired, and the records are in evidence/artifacts/terminal-lane-cross-family-review-20260930/ (findings.json, recheck-findings.json, final-findings.json, post-merge-read.json, with the
raw results and verifications beside them). You are the first reader of the post-merge round's repairs: roughly 450 new or changed lines of probe, runner and control code and three new scripts, which is where the earlier rounds found most of their defects, so those most likely still hide some. The classes found so far (find more of them, and
their instances in code the earlier rounds did not look at): a control or selftest that cannot fail (a stand-in that never starts, a baseline that an earlier step already dirtied, an expected set that is met by accident); a guard whose removal no case or mutant notices (the spawn guard, the clause of an identity check that only another
process could trip); a coverage claim stated by intent instead of by a count ('every line'); a guarantee stated in a docstring, README or decision record that no case exercises or that is false at one interleaving; a mechanism whose side effect on the processes it spawns was not checked (a blocked signal mask survives `exec`); an exit
status standing in for the signal that caused it; a claim of a native rerun that no recorded output backs; counts or names that disagree between files; a scan or comparison that returns 'identical' or 'found' when it saw nothing; private labels or paths republished. Findings the earlier rounds answered: do not re-report an answered
finding; report a repair that is wrong, incomplete, unsafe or that introduced a defect; two earlier findings were REFUTED by verifiers (identical command hooks run once; a terminal's permission notification is timed by inactivity, the fixed-delay timer being the Agent SDK path), do not reopen them without new evidence.
DOCUMENTED RESIDUALS (do not report as new; report only if a document or a control claims more than the residual allows): a settings save between the settings-swap tool's last comparison and the rename is lost and is in neither file; the scan cannot resolve a minified name by scope or see a later `.push`; the login-shell scripts' nonce
and answer lines are not authenticated against a startup file that replays the `-c` string; the lines after the prompt is typed are not swept (the sweep's dry run stops at the trust dialog; the sweep's detail states how many lines it swept of how many have code); signals pending together run their handlers in ascending number, so 'the first
signal wins' holds one dispatch apart; a kill by pid after the tmux identity check has a gap that pidfd_open would close; SIGHUP is covered in process only; the tmux probes install no signal handler; the selftests exit 0 when end-to-end cases are skipped; a run killed from outside can leave `sleep 3137<digits>` stand-ins and `/tmp/sweep-*`
scratch directories; no live Windows Terminal or interactive Claude Code session was run, so the bell and focus reports remain unobserved; Claude Code 2.1.283 was pruned from the host during the round, so its scan record is retained from the earlier record pass."""


def git(*args):
    return subprocess.run(["git", "-C", str(CHECKOUT), *args], capture_output=True, text=True, check=True).stdout


LANE_PATHS = ["evidence/artifacts/terminal-experience-20260928", "evidence/artifacts/notification-types-20260929", "evidence/artifacts/login-shell-contract-20260929", "evidence/artifacts/wsl-terminal-defaults-20260929",
              "evidence/artifacts/terminal-lane-cross-family-review-20260930", "docs/decisions/2026-09-28-terminal-experience.md", "recipes/claude-native-profile.md", "adoption/platforms/linux-wsl2.md",
              "tests/test_windows_terminal_defaults.py", "tests/test_adoption_status.py", "evidence/receipts/cross-family-review-terminal-lane-20260930.json", "evidence/receipts/terminal-experience-20260928.json",
              "evidence/receipts/login-shell-contract-20260929.json", "evidence/receipts/wsl-terminal-defaults-20260929.json", "evidence/receipts/notification-types-20260929.json"]
files = git("diff", "--name-status", BASE, MERGED, "--", *LANE_PATHS, "docs/harness-defaults.md").strip().splitlines()
body = BODY.read_text(encoding="utf-8")
match = re.search(r"^###? Evidence-class table.*?$\n(.*?)(?=^###? |\Z)", body, re.S | re.M)
rows = [line for line in (match.group(1) if match else "").splitlines() if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| Claim")]
claims = []
for number, row in enumerate(rows, 1):
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    text = f"{number}. {cells[0][:900]}  [class: {cells[1][:60] if len(cells) > 1 else ''}; recorded in: {cells[2][:240] if len(cells) > 2 else ''}]"
    claims.append(re.sub(r"`?gpt-6[\w.-]*`?", "the review model", text))
packet = "\n".join([f"UNIT: the post-merge repair round of pull request #563, merged commit {MERGED[:8]}, baseline {BASE[:8]}, CHECKOUT {git('rev-parse', '--short=8', 'HEAD').strip()}",
                    f"Files changed since the baseline, lane paths only ({len(files)}):", *[f"  {line}" for line in files], "",
                    "The merged pull request's own evidence claims (each is a claim to test, not a fact):", *claims])

LENSES = {
    "P1": """LENS P1: behaviour of the two pty probes and the mutant runner (signals, typing, the sweep, the mutants). Patch: post-P1.diff.
1. Files: evidence/artifacts/terminal-experience-20260928/{alert_probe.py, pty_probe_mutants.py} and evidence/artifacts/notification-types-20260929/push_notification_probe.py. The new or changed pieces: `end_by_latched_signal` and the `__main__` block, `type_prompt`, the SIG_IGN rule in `with_private_dir`, `sweep_trial` and `sweep_case`
   (the `started` fact, `before_spawn`, `code_lines`, the renamed case), the timeout handling of `sweep_trial`, `status_case` and the runner, `typing_case`, `ignored_case`, and in the runner `CASES`, `IGNORED`, `TYPING`, `WITHOUT_STATUS`, the eleven `MUTANTS` and their expected sets.
2. Run, in a scratch copy through ctx_execute: each probe's `--selftest` (about two minutes each; the end-to-end cases start stand-in `sleep 3137<digits>` clients under a private TMPDIR: make sure none is left behind and kill only by exact PID). `pty_probe_mutants.py <copy> alert` takes about 45 minutes: do not run it in full; instead reproduce single mutants by hand
   (copy the probe, apply ONE replacement of `MUTANTS`, run the named cases through the runner's `DRIVER`) for at least four mutants of your choice, and say whether the failing set equals the expected set.
3. Ending by the signal (the main task). Read `end_by_latched_signal` and the `__main__` block against what they claim. Try to break them: the latched signal is blocked or pending at the time of `os.kill`; stdout is a closed or full pipe or a closed pty; SIGHUP arrives while the output is being flushed; a second signal arrives between `signal.signal(number, SIG_DFL)` and `os.kill`;
   the process is a child of a shell loop (use `bash -c 'for i in 1 2 3; do python3 -B alert_probe.py ...; done'` with the stand-in arena of `signal_case`) and Ctrl-C is sent to the group; a KeyboardInterrupt or an exception inside `main()`; `SIGTERM` to a probe that already finished its cleanup. Does every path either end BY the signal or exit with a status that is documented? Which path falls through to `sys.exit(status)` silently, and is that stated?
   Note that the sweep's driver calls `probe.main()` itself and never runs the `__main__` block: which cases do exercise it, and which statement of the README or the decision record about the exit depends on a case that does not?
4. The sweep: does `started` (a stand-in pidfile exists) really mean 'a client was started'? Can a trial pass vacuously (the spawn guard not in the dry run's lines, a stand-in that is slow, a pidfile left by an earlier trial, trials sharing serial numbers)? Is `before_spawn` the right set (execution order of the dry run versus the signal landing at that line)? Are the nested functions of `measure` (`pump`, `observer`, `work`, `log_lines`) inside or outside the swept lines and the count?
   Are the numbers it prints ('N lines swept of the M lines with code') computed the way the READMEs describe, on Python 3.13 and on the oldest Python the repository's tests support?
5. Typing and SIG_IGN: attack `type_prompt` (a signal between the last keystroke and the Enter, a write that raises, a stand-in that closes the pty) and the SIG_IGN rule (SIGINT ignored by the parent, SIGHUP ignored, SIGTERM ignored; a handler restored in the wrong order; `previous` empty). Is `typing_case` or `ignored_case` able to fail for a wrong implementation, or is it met by accident?
6. Mutants: for each of the four new mutants and the changed expectation of the raising-handler mutant, is the expected failing set caused by the removed guard or incidental? Find a guard of the new code whose removal leaves every case passing (candidates: the flushes, `if number is None: return`, the early return after `type_prompt`, the `started` check, the timeout branches, `code_lines`).
7. The two probes against each other: the derived probe (`push_notification_probe.py`) must carry every repair of its origin. Report any difference between the two that the documents do not call intended.
8. Report only what you ran or quoted.""",
    "P2": """LENS P2: the tmux probes, the three new scripts and the recorded outputs. Patch: post-P2.diff.
1. Files: evidence/artifacts/notification-types-20260929/tmux_bell_probe.py and evidence/artifacts/terminal-lane-cross-family-review-20260930/{tmux_sync_probe.py, shell_loop_control.py, signal_order_probe.py, tmux_identity_mutant.py, post-merge-read.json}, the new or changed files of recorded/ (environment.txt, notification_types_scan_2.1.286.json, shell_loop_control.txt,
   signal_order_probe.txt, tmux_identity_mutant_bell.txt, tmux_identity_mutant_sync.txt, exit_codes.txt, color_capture.txt, scrub_placeholder_probe.txt, the two selftests), the retained notification_types_scan_2.1.283.json, and tests/test_windows_terminal_defaults.py as context.
2. Run in a scratch copy: both tmux probes' `--selftest` (private sockets: check that no tmux process and nothing in /tmp/tmux-<uid>/ or /tmp/tb*, /tmp/tw* is left afterwards), `shell_loop_control.py`, `signal_order_probe.py`, `tmux_identity_mutant.py <copy> bell` and `... sync`, and the five test modules named in the repository's CI.
3. The tmux identity check (the main task). `server_identity` accepts a pid when `comm` starts with `tmux` and the private socket path occurs in the command line: is that an exact comparison of argv elements or a substring test, and what does that allow (another server started with a longer or similar socket path, an argument that merely contains the path, a wrapper script)? Build a concrete case and run it.
   `server_alive` now excludes state Z: check the state field parsing (a process name containing a space or a parenthesis), and that `stop_server` still ends when the server is a zombie of an unreaped parent. Is the third control (the pid of another private server) able to fail for a wrong implementation other than the deleted clause (the mutant)? What does the control leave behind when the measurement raises something other than ServerNotStopped?
   The `os._exit(127)` child: can the `finally` run in the child before `os.execv` raises, and what else could the child execute (flush of inherited stdio buffers, atexit handlers)?
4. The three scripts against their own claims: `shell_loop_control.py` (does it measure what the documents say: only bash was run, the documents speak of 'a parent shell'; is the 0.5 s timing safe on a loaded host; does the second loop's `sleep(5)` matter), `signal_order_probe.py` (CPython's own `PyErr_CheckSignals` source decides the handler order: fetch Modules/signalmodule.c of the CPython tag that matches the host's Python and quote the loop; also state what signal(7) says about the kernel's delivery order) and `tmux_identity_mutant.py` (a copy under /var/tmp, the exact clause it removes, the verdict it prints).
5. Recorded outputs against the commands that produced them and the files that cite them: `exit_codes.txt` (35 lines; which command is missing or duplicated; the two mutant runs were moved into recorded/ afterwards), `environment.txt`, the scans of 2.1.284, 2.1.285 and 2.1.286 (17 types each, the same list?), the retained 2.1.283 scan (its binary is gone: is every statement about it scoped), the colour capture (the arithmetic of 'without COLORTERM 31 foreground and 4 background 256-colour sequences; with it 33 foreground and 6 background truecolor ones') and the scrub probe. Compute the sha256 values the receipt lists and compare.
6. Report only what you ran or quoted.""",
    "P3": """LENS P3: claims, evidence and hygiene (every document, record and receipt of the round).
1. Files: docs/decisions/2026-09-28-terminal-experience.md (the subsection 'The post-merge read of the final repairs', the three decision rows it added or edited, both evidence tables, the limits), the three artifact READMEs that changed (terminal-experience-20260928, notification-types-20260929, terminal-lane-cross-family-review-20260930), evidence/receipts/cross-family-review-terminal-lane-20260930.json (rebuilt) and
   evidence/receipts/terminal-experience-20260928.json (corrected), docs/harness-defaults.md (the last three rows of the anti-pattern table and the edited signal-handling row), post-merge-read.json, and recorded/*.
2. Numbers. Build a table of every count, hash, duration, token figure and name that appears in more than one place (tests run, controls, mutants and mutant runs, cases and in-process tests per probe, the swept-line counts, commands, findings by severity and disposition, tokens, minutes, files touched) and check each occurrence against the recorded output or record file it comes from. Report a disagreement or an unsupported figure.
   Pay attention to wording that mixes 'mutants' and 'mutant runs', 'cases' and 'tests', 'eleven per probe' and '22'.
3. Hashes and the repository's own check. Compute the sha256 of every file listed in the receipt's provenance (scripts, record files, recorded outputs) at CHECKOUT and compare; run `python3 -B scripts/validate.py` in a scratch copy and report what it prints; check that manifests/evidence.json carries the receipt's claim and limitations text unchanged.
4. Each sentence of the new subsection, the rows and the README text against the recorded evidence and the primary sources it leans on: Cracauer's 'Proper handling of SIGINT/SIGQUIT' (cons.org/cracauer/sigint.html), the Python `signal` documentation, CPython's pending-signal dispatch, signal(7), the tmux and /proc facts. Quote the source and give the URL with the tag or the fetch date. In particular: is the claim that 'a shell cannot tell an exit 130 from a death by SIGINT' stated for bash only or for every shell, and what was measured?
5. Overclaims and omissions: sentences that say more than the recorded outputs show, that omit a condition the evidence reveals, or that a later change made stale (search for leftovers: 'at every line of the resource lifecycle', 'six in-process latch tests', '14 mutants', 'seven mutants', 'exit status 128 + the signal' stated as current, 'matches the counts of 2026-09-28', '242 unit tests', two shutdown-failure controls where three are meant, a README row that
   disagrees with its script's docstring, a receipt limitation that contradicts the decision record). Check that the claims of the pull request's evidence table (in the packet) are each backed by a recorded file.
6. post-merge-read.json is a hand-written record: compare each finding's 'verification' and 'disposition' with the recorded outputs and the code; report a statement of a measurement that was not recorded.
7. Hygiene of every added or changed file: home paths (only /home/example is allowed), user names, host identifiers beyond the repository's host_scope convention, session ids, credentials, GUIDs of the user's own state, private per-project profile labels, and screen contents in recorded outputs. Report counts and file names, never the sensitive string itself.
8. Report only what you ran or quoted.""",
}
sizes = {}
for name, lens in LENSES.items():
    prompt = "\n\n".join([COMMON, packet, lens])
    for out in OUTS:
        (out / f"{name}.txt").write_text(prompt + "\n", encoding="utf-8")
    sizes[name] = len(prompt.encode("utf-8"))
print(sizes, "| largest", max(sizes.values()), "bytes (limit 120000) | files in the packet:", len(files), "| claims:", len(claims))
