#!/usr/bin/env python3
"""Write the prompts of the bounded re-check of the repair pull request (2026-09-30): the common preamble of build_review_prompts.py (re-used from its source, with the change described as an open
repair of an earlier review), one packet (the pull request's head, its changed files, its own evidence claims), and one task per lens. The schema is the one build_review_prompts.py wrote.
usage: build_recheck_prompts.py <checkout at the pull request head> <pull request body file> <out dir> <pull request number> <base>"""
import re, subprocess, sys
from pathlib import Path

CHECKOUT, BODY, OUT, NUMBER, BASE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
(OUT / "prompts").mkdir(parents=True, exist_ok=True)
source = (Path(__file__).resolve().parent / "build_review_prompts.py").read_text(encoding="utf-8")
block = source[source.index('COMMON = f"""'):]
block = block[:block.index('"""\n\nUNITS')] + '"""\n'
namespace = {"CHECKOUT": CHECKOUT}
exec(block, namespace)
COMMON = namespace["COMMON"].replace("one change that is already merged into a portable engineering reference repository. The author's own checks and reviewers agreed with it; your value is what they missed.",
                                     "one open pull request against a portable engineering reference repository. It repairs the findings of an earlier cross-family review of four merged pull requests; the author's own checks and an independent verifier agreed with it, and your value is what they missed.")
COMMON = COMMON.replace("(detached at a commit that contains the change)", "(detached at the pull request's head)")
inspect = re.search(r"Inspect the change with `git -C [^`]+` and `git -C [^`]+`\. Files are read as they are at CHECKOUT; `git log [^`]+` shows later edits by other changes, which are not under review\.", COMMON)
assert inspect, "the inspection sentence of the common preamble was not found"
COMMON = COMMON.replace(inspect.group(0), f"Inspect the change with `git -C {CHECKOUT} diff --stat {BASE} HEAD` and `git -C {CHECKOUT} diff {BASE} HEAD -- <path>`. Files are read as they are at CHECKOUT; everything that differs from {BASE[:12]} is under review.")
COMMON += ("\n\nTHE EARLIER REVIEW. Every finding of the earlier review, with how it was checked and where its repair is, is in evidence/artifacts/terminal-lane-cross-family-review-20260930/findings.json (and results.json, "
           "verification.json). Do not re-report a finding the repair answers; report a repair that is wrong, incomplete, or unsafe, a control or mutant that would pass for a wrong implementation, a claim in the new text "
           "that the recorded outputs (evidence/artifacts/terminal-lane-cross-family-review-20260930/recorded/) or a primary source contradict, and new defects the repairs introduced. Two earlier findings were REFUTED by "
           "verifiers; do not reopen them without new evidence.")


def git(*args):
    return subprocess.run(["git", "-C", str(CHECKOUT), *args], capture_output=True, text=True, check=True).stdout


head = git("rev-parse", "HEAD").strip()
files = git("diff", "--name-status", f"{BASE}", "HEAD").strip().splitlines()
body = BODY.read_text(encoding="utf-8")
match = re.search(r"^###? Evidence-class table.*?$\n(.*?)(?=^###? |\Z)", body, re.S | re.M)
rows = [line for line in (match.group(1) if match else "").splitlines() if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| Claim")]
claims = []
for number, row in enumerate(rows, 1):
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    text = f"{number}. {cells[0][:600]}  [class: {cells[1][:60] if len(cells) > 1 else ''}; recorded in: {cells[2][:200] if len(cells) > 2 else ''}]"
    text = re.sub(r"`?gpt-6[\w.-]*`?", "the review model", text)   # the reviewer is not told which model wrote the earlier review
    claims.append(text)
packet = "\n".join([f"UNIT: pull request #{NUMBER}, head {head[:12]}, base {BASE[:12]}", f"Changed files ({len(files)}):", *[f"  {line}" for line in files], "",
                    "The pull request's own evidence claims (each is a claim to test, not a fact):", *claims])

LENSES = {
    "R1": """LENS: behaviour and tests, part 1 of 3 (the settings-swap tool and the pty and tmux probes).
1. Files: evidence/artifacts/notification-types-20260929/replace_bell_group.py, replace_bell_group_controls.py, replace_bell_group_mutants.py, concurrent_writer_harness.py, tmux_bell_probe.py, push_notification_probe.py, and
   evidence/artifacts/terminal-experience-20260928/alert_probe.py.
2. Run the controls and the mutants in a scratch copy. Attack the tool with synthetic homes: the lost-update comparisons (is there a window between the second comparison and the replace that a control should still
   cover, or that the text overclaims?), file modes and ownership, a backup that already exists, a settings file that is a hard link, a directory that cannot be written, a settings file whose hooks are not objects,
   concurrent runs of the tool itself. Judge each mutant: does the failing set it names really depend on the removed guard, and would a wrong implementation pass every control?
3. The probes: the signal handlers (SIGTERM and SIGHUP become SystemExit for the duration; can this hide an exception, leave the child group running, or run cleanup twice?), the end-to-end SIGTERM case (can it pass by
   accident? does its process scan match only its own stand-in?), the UTF-8 decoding in BelCounter (incremental decoder state across reads, replacement characters, a split multi-byte sequence, C1 code points from an
   invalid sequence), the exit statuses (2, 1, 0) and what a caller that only checks the exit status learns.
4. Report only what you ran or quoted.""",
    "R2": """LENS: behaviour and tests, part 2 of 3 (the scan, the tests, the login-shell, defaults and landscape scripts, the practice repository's checks).
1. Files: evidence/artifacts/notification-types-20260929/notification_types_scan.py and scan_reader_mutants.py; tests/test_windows_terminal_defaults.py and tests/test_adoption_status.py (the new reader, documentation and
   oracle tests); evidence/artifacts/login-shell-contract-20260929/*.py; evidence/artifacts/wsl-terminal-defaults-20260929/*.py; evidence/artifacts/terminal-experience-20260928/color_capture.py; evidence/artifacts/terminal-lane-cross-family-review-20260930/tmux_sync_probe.py.
   The practice repository (outside this checkout, no remote) is not available to you: skip it.
2. Run the affected test modules (`python3 -B -m unittest tests.test_adoption_status tests.test_windows_terminal_defaults tests.test_adoption_docs_consistency tests.test_render_config tests.test_apply_claude_settings`) and every
   script's --selftest or controls in a scratch copy. Mutate: does each new test or selftest fail for a wrong implementation? Try inputs the authors did not: a minified bundle in which the catalog's spread identifier is
   assigned twice in different scopes or spread from a nested expression, a SGR sequence with empty parameters or 38;2 split across sub-parameters, a login shell whose startup file prints something before the probe,
   a home with both ~/.bash_profile and an unreadable ~/.bash_login, landscape definitions in a different order, a Codex banner in a language or format the regex does not expect.
3. Look for any script whose exit status still cannot tell a measurement from a non-measurement.
4. Report only what you ran or quoted.""",
    "R3": """LENS: claims and evidence (all of the change: documents, decision record, receipts, the new artifact directory).
1. The new decision record section (docs/decisions/2026-09-28-terminal-experience.md, last section), the corrected text in the recipe, the platform page and harness-defaults, and the correction limitation added to four receipts:
   every sentence against the recorded outputs and the primary sources it cites (Windows Terminal at v1.24.11911.0, tmux 3.4 and 3.6, the hooks reference, the installed Claude Code binary read-only via grep -a with bounded windows, bash(1)).
2. The new receipt evidence/receipts/cross-family-review-terminal-lane-20260930.json: every number and hash against evidence/artifacts/terminal-lane-cross-family-review-20260930/{results,verification,findings}.json, prompts_sha256.txt and recorded/*
   (sha256 of the listed scripts and files); the counts in the decision record, the pull request description and the README against the files. findings.json: for a sample of at least ten rows, check the claimed disposition against the tree
   (is the repair really where the row says, and does it do what the row says?).
3. Hygiene of the added files: home paths (only /home/example is allowed), user names, host identifiers beyond the repository's host_scope convention, session ids, credentials; whether any recorded output includes screen contents.
4. Overclaims: statements that say more than the evidence shows, or omit a condition the evidence reveals; the limitations of the new receipt against what was and was not run.
5. Report only what you ran or quoted.""",
    "U1": """LENS: adversarial second opinion on the whole change, highest-risk items first (you may split the work yourself).
Rank the repairs by the harm a wrong repair would do: (1) replace_bell_group.py, which writes the user's Claude settings file; (2) the checks whose exit status other tooling trusts (login-shell check and the practice repository's doctor, codex_tui_strict_check.py,
overlay_noop_check.py, the pty probes); (3) the documents a reader would act on (platform page step 5 about profiles.defaults, the recipe's login-shell probe, the presence-rule text). Try to make each repair fail: run it, mutate it in a scratch copy,
read the upstream source it cites. Also check that the findings marked refuted, removed or kept in findings.json are right to be, by reading the verifier's evidence and the code.
Report only what you ran or quoted.""",
}
sizes = {}
for name, lens in LENSES.items():
    prompt = "\n\n".join([COMMON, packet, lens])
    (OUT / "prompts" / f"{name}.txt").write_text(prompt + "\n", encoding="utf-8")
    sizes[name] = len(prompt.encode("utf-8"))
print(sizes, "| largest", max(sizes.values()), "bytes (limit 120000)")
