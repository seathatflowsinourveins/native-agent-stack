#!/usr/bin/env python3
"""Write the prompts of the final review pass of the terminal lane (2026-09-30): the fifth repair round of the merged pull request #532, read by three lenses (F1 the settings-swap tool and the pty probes, F2 the
scripts, the scan and the tests, F3 claims, evidence and hygiene). The common preamble is re-used from build_review_prompts.py (its own source, not a copy), with the change described as the merged fifth round; the
packet is the round's changed files and the merged pull request's own evidence claims. One prompt per lens is written into each lane's prompts directory (both models read identical prompts).
usage: build_final_prompts.py <checkout at origin/main> <packets dir> <baseline commit> <merged pull request body file> <prompts dir> [<prompts dir> ...]"""
import re, subprocess, sys
from pathlib import Path

CHECKOUT, PACKETS, BASE, BODY = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4])
OUTS = [Path(a) for a in sys.argv[5:]]
for out in OUTS:
    out.mkdir(parents=True, exist_ok=True)
source = (Path(__file__).resolve().parent / "build_review_prompts.py").read_text(encoding="utf-8") if (Path(__file__).resolve().parent / "build_review_prompts.py").exists() else \
    (CHECKOUT / "evidence/artifacts/terminal-lane-cross-family-review-20260930/build_review_prompts.py").read_text(encoding="utf-8")
block = source[source.index('COMMON = f"""'):]
block = block[:block.index('"""\n\nUNITS')] + '"""\n'
namespace = {"CHECKOUT": CHECKOUT}
exec(block, namespace)
COMMON = namespace["COMMON"]
COMMON = COMMON.replace("(detached at a commit that contains the change)", "(detached at origin/main, which contains the merged change)")
inspect = re.search(r"Inspect the change with `git -C [^`]+` and `git -C [^`]+`\. Files are read as they are at CHECKOUT; `git log [^`]+` shows later edits by other changes, which are not under review\.", COMMON)
assert inspect, "the inspection sentence of the common preamble was not found"
COMMON = COMMON.replace(inspect.group(0),
    f"The change under review is the FIFTH REPAIR ROUND of pull request #532, merged as f03f41c7 (a squash of its whole branch); CHECKOUT is origin/main, which contains it and two later commits that are not part of it. "
    f"The state the earlier re-check saw is commit {BASE[:8]}, which is in the object store: `git -C {CHECKOUT} diff {BASE[:8]} HEAD -- <path of this lane>` shows the round-5 delta for a path (other paths differ because main moved). "
    f"The same delta, limited to this lane's paths, is in three patch files that you may read under ~/.local/state as the one exception to the rule below (read only these three): "
    f"{PACKETS}/round5-all.diff (everything), {PACKETS}/round5-F1.diff (the settings-swap tool and the pty probes) and {PACKETS}/round5-F2.diff (the scripts, the scan and the tests). Read them in windows with `sed -n 'A,Bp'`. "
    f"Files are read as they are at CHECKOUT. The two hot shared files `docs/harness-defaults.md` (only its last four table rows are this lane's) and `manifests/evidence.json` (registration entries and hashes) are part of the change but are not in the patches.")
COMMON += """

THE EARLIER REVIEWS. Two review rounds already happened on this lane. Round 1 (nine jobs) returned 46 findings; a re-check of its repairs (four jobs) returned 33 more; every one was graded by a verifier or checked against the code and repaired, and the results are in
evidence/artifacts/terminal-lane-cross-family-review-20260930/ (findings.json, recheck-findings.json, results.json, recheck-results.json, verification.json, recheck-verification.json). You are the reader of the round-5 repairs, which no reviewer has read yet, and the round-5 repairs
are where the earlier rounds found the most defects, so the tools, probes and controls most likely still hide some. The classes found so far (find more of them, and their instances in code the earlier rounds did not look at): a control or selftest that cannot fail (a stand-in that never
starts, a baseline that an earlier step already dirtied, an expected set that is met by accident); a guarantee stated in a docstring, README or decision record that no case exercises or that is false at one interleaving; a mechanism whose side effect on the processes it spawns was not checked
(a blocked signal mask survives `exec`); a claim of a native rerun that no recorded output backs; counts or names that disagree between files; a scan or comparison that returns 'identical' or 'found' when it saw nothing; private labels or paths republished. Findings the earlier
rounds answered: do not re-report an answered finding; report a repair that is wrong, incomplete, unsafe or that introduced a defect; two earlier findings were REFUTED by verifiers (identical command hooks run once; a terminal's permission notification is timed by inactivity, the fixed-delay timer being the Agent SDK path), do not reopen them without new evidence.
DOCUMENTED RESIDUALS (do not report as new; report only if a document or a control claims more than the residual allows): a settings save between the tool's last comparison and the rename is lost and is in neither file; the scan cannot resolve a minified name by scope (the three release binaries do not trigger it);
the colour counter treats an incomplete `38;2` group as unclassified where the terminal applies missing components as 0; the case that lands a signal in the first second of the probe's normal-exit cleanup is timing-dependent; no live Windows Terminal or interactive Claude Code session was run, so the bell and focus reports remain unobserved."""


def git(*args):
    return subprocess.run(["git", "-C", str(CHECKOUT), *args], capture_output=True, text=True, check=True).stdout


LANE_PATHS = ["evidence/artifacts/terminal-experience-20260928", "evidence/artifacts/notification-types-20260929", "evidence/artifacts/login-shell-contract-20260929", "evidence/artifacts/wsl-terminal-defaults-20260929",
              "evidence/artifacts/terminal-lane-cross-family-review-20260930", "docs/decisions/2026-09-28-terminal-experience.md", "recipes/claude-native-profile.md", "adoption/platforms/linux-wsl2.md",
              "tests/test_windows_terminal_defaults.py", "tests/test_adoption_status.py", "evidence/receipts/cross-family-review-terminal-lane-20260930.json", "evidence/receipts/terminal-experience-20260928.json",
              "evidence/receipts/login-shell-contract-20260929.json", "evidence/receipts/wsl-terminal-defaults-20260929.json", "evidence/receipts/notification-types-20260929.json"]
files = git("diff", "--name-status", BASE, "HEAD", "--", *LANE_PATHS).strip().splitlines()
body = BODY.read_text(encoding="utf-8")
match = re.search(r"^###? Evidence-class table.*?$\n(.*?)(?=^###? |\Z)", body, re.S | re.M)
rows = [line for line in (match.group(1) if match else "").splitlines() if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| Claim")]
claims = []
for number, row in enumerate(rows, 1):
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    text = f"{number}. {cells[0][:800]}  [class: {cells[1][:60] if len(cells) > 1 else ''}; recorded in: {cells[2][:220] if len(cells) > 2 else ''}]"
    claims.append(re.sub(r"`?gpt-6[\w.-]*`?", "the review model", text))
packet = "\n".join([f"UNIT: the fifth repair round of pull request #532, merged commit f03f41c7, baseline {BASE[:8]}, CHECKOUT {git('rev-parse', '--short=8', 'HEAD').strip()}",
                    f"Files changed since the baseline, lane paths only ({len(files)}):", *[f"  {line}" for line in files], "",
                    "The merged pull request's own evidence claims (each is a claim to test, not a fact):", *claims])

LENSES = {
    "F1": """LENS F1: behaviour of the settings-swap tool and the two pty probes (signals, concurrency, cleanup). Patch: round5-F1.diff.
1. Files: evidence/artifacts/notification-types-20260929/{replace_bell_group.py, replace_bell_group_controls.py, replace_bell_group_mutants.py, concurrent_writer_harness.py, push_notification_probe.py}, evidence/artifacts/terminal-experience-20260928/{alert_probe.py, pty_probe_mutants.py}, and
   tools/adoption/apply_claude_settings.py (called by the tool; unchanged in this round).
2. Run, in a scratch copy through ctx_execute: the controls and the mutants of the settings-swap tool; each probe's `--selftest` (about two minutes each; the end-to-end cases start stand-in `sleep 3137<digits>` clients under a private TMPDIR: make sure none is left behind, and kill only by exact PID); and `pty_probe_mutants.py <copy> alert`
   (about five minutes; sample the push variant instead of running it in full if time is short). Also run the controls under `umask 077` and with a read-only HOME subdirectory.
3. Signals, the main task. List every point at which SIGTERM, SIGHUP or SIGINT can arrive in `main()`, `with_private_dir()` and `measure()` of both probes (before the handlers exist; between mkdtemp and the handlers; before and inside the spawn flag's window; between the spawn and `os.close(slave)`; in the observation loop; in `deferred_signals()`;
   during rmtree; after the handlers are restored; during the final `print`), say for each what can leak (the client's process group, the pty master, the payload directory, the terminal's state, a zombie), and try to build at least three concrete interleavings that break a statement of the docstrings, the README or the decision record ("the first signal wins", "the cleanups run with the signals deferred", "the client
   is created under a spawn flag", "a signal during the spawn waits until the client is recorded"). Drive them the way the earlier reviewers did (`sys.settrace`, an `os.kill` from a patched function or a helper thread). Consider what happens to a signal that arrives while the flag is set and a second one that arrives after it (which is remembered?), to SIGHUP from a closing terminal, and to a `SystemExit` raised inside a `finally`.
   Also check the two probes against each other: the derived probe must carry every repair of its origin (exit statuses, cleanup, counters).
4. The settings-swap tool: the final comparison and the harness modes (after-merge, at-backup, during-backup, after-backup, at-replace): does each case fail for the interleaving it names and only for it (mutate the tool to check)? Attack the tool with synthetic homes: hard-linked settings file, a file owned by another user or with unusual mode/ACL, a full or read-only directory, a settings file of several MB, non-UTF-8 bytes, hooks that are not objects, a Notification that is not a list, duplicate bell groups in unusual shapes, a settings file that is replaced by a symlink between the read and the write. State what each does and whether it can lose the user's settings.
5. Mutants: for each of the 15 (tool) and 6+6 (probe) mutants, is the expected failing set caused by the removed guard, or is it incidental? Find a guard whose removal leaves every case passing, or a case that would pass for a wrong implementation.
6. Portability: Python 3.9 (macOS CI) to 3.13; note only what can break where the code is meant to run (the probes are Linux-only by design: `/proc`, pty).
7. Report only what you ran or quoted.""",
    "F2": """LENS F2: behaviour of the scan, the tests, the login-shell scripts, the landscape comparison, the colour counter and the tmux probes. Patch: round5-F2.diff.
1. Files: evidence/artifacts/notification-types-20260929/{notification_types_scan.py, scan_reader_mutants.py, tmux_bell_probe.py}; tests/test_windows_terminal_defaults.py (ScanReaderTests, MATCHER_QUOTE, quoted_matchers, the documentation and oracle tests); evidence/artifacts/login-shell-contract-20260929/{login_path_digest.py, scrub_placeholder_probe.py, login_shell_check_controls.py, landscape_refresh.py};
   evidence/artifacts/terminal-experience-20260928/color_capture.py; evidence/artifacts/terminal-lane-cross-family-review-20260930/tmux_sync_probe.py; and the wsl-terminal-defaults-20260929 scripts as context.
2. Run in a scratch copy: `python3 -B -m unittest tests.test_adoption_status tests.test_windows_terminal_defaults tests.test_adoption_docs_consistency tests.test_render_config tests.test_apply_claude_settings`, every script's --selftest or controls, `scan_reader_mutants.py` against the three installed release binaries (the resolved targets under the client's versions directory; read-only), the tmux probes
   if tmux is installed (they use private sockets: check that nothing is left in /tmp/tmux-<uid>/ afterwards), and `login_shell_check_controls.py` without --real-host.
3. Mutate to look for cases that cannot fail: the documentation test (`quoted_matchers`, `MATCHER_QUOTE`): try an operative matcher phrased in a way that neither the phrase rule nor the pipe-list rule sees, a matcher in a table cell, a matcher split over a line break, one with a different separator; the scan (a property assignment, a `let`, whitespace, two catalogs in one binary, a spread of a call result); the login-shell check (a symlink to an executable, a directory named like the command, a
   relative PATH entry, a command found only through a shell function, `hash -p` with a valid path); the digest and the scrub probe's nonce framing (a PATH holding a newline or a `%`, a startup file that closes stdout, calls `exec`, prints binary, sets `set -e`); the scrub probe's selftest (does a state function that skips a name really make the control fail; is the exact-set rule met by accident).
4. `landscape_refresh.py`: fetch codex-rs/config/src/types.rs at rust-v0.157.1 and rust-v0.159.2 (use `ctx_fetch_and_index`) and run `definitions()` on both; then mutate them as an upstream change plausibly would (a changed `Notifications` default, another `impl` block, a new field of `Tui` about notifications, a renamed `terminal_title`, an attribute wrapped over several lines, reordered fields) and report an upstream-plausible change that the comparison calls identical.
5. `color_capture.py`: compare `sgr_counts` with the pinned Windows Terminal parser (microsoft/terminal v1.24.11911.0, src/terminal/adapter/adaptDispatchGraphics.cpp and the VT parameter parsing) on tricky input (empty parameters, `38;2;;;`, `38:2:...` with and without a colour-space field, a colon group inside a semicolon sequence, `4:3`, over-long or non-numeric parameters) and say where the counter's classification disagrees with the terminal's.
6. tmux probes: private socket length limit, an inherited TMUX or TMUX_TMPDIR, cleanup on a failure before the `try`, a server that survives `kill-server`.
7. Report only what you ran or quoted.""",
    "F3": """LENS F3: claims, evidence and hygiene (every document, record and receipt of the round).
1. Files: docs/decisions/2026-09-28-terminal-experience.md (the whole 'Update 2026-09-30' section, including the subsection 'The bounded re-check of the repairs' and both evidence tables), the five artifact READMEs of the lane, the receipts (new: evidence/receipts/cross-family-review-terminal-lane-20260930.json; corrected: terminal-experience-20260928, login-shell-contract-20260929, wsl-terminal-defaults-20260929, notification-types-20260929),
   docs/harness-defaults.md (the last four rows of the anti-pattern table), recipes/claude-native-profile.md, adoption/platforms/linux-wsl2.md, the record files findings.json, recheck-findings.json, results.json, recheck-results.json, verification.json, recheck-verification.json, prompts_sha256.txt, recheck_prompts_sha256.txt, and recorded/*.
2. Numbers. Build a table of every count, hash, duration, token figure and name that appears in more than one place (tests run, controls, mutants, passes, commands, findings by severity and disposition, verdicts, tokens and cache share, minutes, pool points, PATH entries, real-home names, files touched) and check each occurrence against the recorded output or record file it comes from. Report a disagreement or an unsupported figure.
3. Hashes. Compute the sha256 of every file listed in the new receipt's provenance (scripts, record files, recorded outputs) at CHECKOUT and compare; check that manifests/evidence.json carries the receipts' claim and limitations text unchanged and the registered hashes of the lane's files match the tree (`python3 -B scripts/validate.py` in a scratch copy is the repository's own check: run it; report what it prints).
4. Each sentence of the round-5 subsection and of the corrected receipts against the recorded evidence and the primary sources it leans on: signal(7) and the Python `signal` documentation (a blocked mask survives execve), bash's `type -P`/`hash` behaviour, the pinned Windows Terminal parser, Codex `types.rs` at rust-v0.157.1 and rust-v0.159.2, tmux 3.4. Quote the source and give the URL with the tag or the fetch date. Also check that a statement of a native rerun names a recorded output that shows it.
5. Overclaims and omissions: sentences that say more than the recorded outputs show, that omit a condition the evidence reveals, or that a later change made stale (search for leftovers: 'polaris' as a target, 'handler-less', 24 or 26 controls, 14 or 16 mutant runs, 'nine' where ten or eleven homes are meant, 'seven mutants', a README row that disagrees with its script's docstring).
6. Hygiene of every added or changed file: home paths (only /home/example is allowed), user names, host identifiers beyond the repository's host_scope convention, session ids, credentials, GUIDs of the user's own state, private per-project profile labels of the retired second distro, and screen contents in recorded outputs. Report counts and file names, never the sensitive string itself.
7. Report only what you ran or quoted.""",
}
sizes = {}
for name, lens in LENSES.items():
    prompt = "\n\n".join([COMMON, packet, lens])
    for out in OUTS:
        (out / f"{name}.txt").write_text(prompt + "\n", encoding="utf-8")
    sizes[name] = len(prompt.encode("utf-8"))
print(sizes, "| largest", max(sizes.values()), "bytes (limit 120000) | files in the packet:", len(files), "| claims:", len(claims))
