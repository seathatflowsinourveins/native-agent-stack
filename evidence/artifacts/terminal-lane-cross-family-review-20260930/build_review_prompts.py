#!/usr/bin/env python3
"""Write the cross-family review prompts and the strict output schema for the terminal-lane PRs (#484, #498, #510, #519) into <out>/prompts and <out>/schemas.
Each prompt = common preamble + one unit packet (merged commit, changed files, the PR's own evidence claims, a lens-specific task list). No model-family or reviewer names appear in
a prompt. usage: build_review_prompts.py <checkout> <pr-bodies-dir> <out-dir>"""
import json, re, subprocess, sys
from pathlib import Path

CHECKOUT, BODIES, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
(OUT / "prompts").mkdir(parents=True, exist_ok=True)
(OUT / "schemas").mkdir(parents=True, exist_ok=True)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "summary", "findings", "claims_checked", "commands_run"],
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "changes-needed"]},
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["severity", "file", "line", "claim", "evidence", "failure_scenario", "fix", "tested"],
            "properties": {"severity": {"type": "string", "enum": ["high", "medium", "low"]}, "file": {"type": "string"}, "line": {"type": "integer"},
                           "claim": {"type": "string"}, "evidence": {"type": "string"}, "failure_scenario": {"type": "string"}, "fix": {"type": "string"},
                           "tested": {"type": "boolean"}}}},
        "claims_checked": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["claim", "result", "source"],
            "properties": {"claim": {"type": "string"}, "result": {"type": "string", "enum": ["confirmed", "contradicted", "unverifiable"]}, "source": {"type": "string"}}}},
        "commands_run": {"type": "array", "items": {"type": "string"}},
    },
}
(OUT / "schemas" / "review.json").write_text(json.dumps(SCHEMA, indent=1) + "\n", encoding="utf-8")

COMMON = f"""ROLE. You are an independent reviewer of one change that is already merged into a portable engineering reference repository. The author's own checks and reviewers agreed with it; your value is what they missed. Be adversarial and evidence-driven, and finish with the JSON object the output schema requires.

CHECKOUT. The repository is checked out read-only at {CHECKOUT} (detached at a commit that contains the change). Never write inside it. Inspect the change with `git -C {CHECKOUT} show --stat <merged commit>` and `git -C {CHECKOUT} diff <merged commit>^ <merged commit> -- <path>`. Files are read as they are at CHECKOUT; `git log <merged commit>..HEAD -- <path>` shows later edits by other changes, which are not under review.

RUNNING THINGS. Your shell is read-only. To run tests or mutate anything, use the context-mode `ctx_execute` tool: make a private scratch copy (`D=$(mktemp -d /var/tmp/rv-XXXXXX); cp -r {CHECKOUT}/. "$D"/`), run `python3 -B ...` inside the copy (always -B), and delete the copy when done. Do not read or print anything under ~/.claude, ~/.codex, ~/.config, ~/.ssh, ~/.local/state or any credential store, and skip checks that need a real sign-in, a live interactive Windows Terminal or Claude Code session, or the user's live settings (for example `overlay_noop_check.py` reads the live user settings: skip it); mark a claim that depends on them `unverifiable` and say what evidence would settle it.

UPSTREAM SOURCES. Use web search, then fetch pages with `ctx_fetch_and_index` (the web `open` operation is not available on this route). Quote exactly and give the URL with the release tag or fetch date. Prefer primary sources: the vendor's documentation, the upstream repository source at a named tag, the tool's own `--help` or source. A statement that only a search snippet or a mirror supports is `unverifiable`.

WHAT COUNTS. A finding is a defect a maintainer would want fixed: wrong or unsafe behavior; a test or control that cannot fail (it passes for a wrong implementation); a claim in a document, decision record or receipt that the repository's own files or a primary source contradict; a number or hash that does not match its recorded output; a privacy or hygiene leak in files meant for publication (home paths, user names, host identifiers, credentials, session ids); a contradiction between two files of the change. Do NOT report: style or naming, hardening with no failing input, anything the change itself lists as a limitation or residual, or matters belonging to other changes. Confirm each finding by running something or quoting the exact lines before reporting it, and set `tested` true only when a command you ran showed it.

SEVERITY. high: wrong behavior, data loss, a security defect, or a false claim a reader would act on. medium: wrong edge behavior, a control that cannot fail, an overstated or unsupported claim. low: a minor inaccuracy or hygiene issue.

BUDGET. You have about 45 minutes. Do the highest-risk checks first and prefer running something over reading more. Return the JSON before the time is used up, even if some checks remain undone: list each undone check in `claims_checked` as unverifiable with the reason.

OUTPUT. Only the JSON object of the schema. `findings` most severe first; `line` is the line in the file at CHECKOUT (open the file and check it); `evidence` holds the command and an output excerpt or the verbatim quote; `failure_scenario` names inputs and the wrong outcome; `fix` is concrete. `claims_checked` lists every claim you tested with the result and its source. `commands_run` lists your commands with paths shortened. `verdict` is approve only when you found no medium or high finding."""

UNITS = {
    "u484": dict(pr=484, sha="cf2960a7", focus_A="""LENS: behaviour and tests. The change adds probe scripts and a host check under evidence/artifacts/terminal-experience-20260928/ and a receipt.
1. Run the artifact scripts' own self-tests and controls that need no live session (for example `alert_probe.py --selftest`, the fragment check's mutant runs, `validate_fragment.py` against its schema) in a scratch copy. Report any that fail or that only pass because of a fixture.
2. The BEL counter claims to model the pinned terminal's escape-sequence parser (bytes split across reads, BEL in the escape state, DCS/APC strings, CAN/SUB, OSC-terminating BEL). Compare it with the state machine of microsoft/terminal at tag v1.24.11911.0 (src/terminal/parser/stateMachine.cpp and the engine) and look for an input where the counter and the parser disagree.
3. The host check is said to fail the previous fragment and nine single-defect mutants, each for exactly one rule. Try to write a tenth defect that the check misses, or a mutant whose failing rule is not the one claimed.
4. Check that each number in the receipt matches the recorded outputs in the same directory, and that the saved hook command yields exactly one BEL byte.""",
                 focus_B="""LENS: claims and evidence. Verify the change's factual statements against primary sources, and its receipt against the recorded artifacts.
1. Windows Terminal: `suppressApplicationTitle`, `bellStyle`, `bellSound`, profile `environment` and fragment semantics in the official docs and settings schema; the source at tags v1.24.11911.0 and the newest release tag for the claims "no shipped release handles plain OSC 9 text, OSC 777 or OSC 99", "toasts are unreleased" and "BellStyle lacks `notification` on both release tags".
2. Codex: the `[tui] notifications` kinds against `type_name()` in codex-rs at rust-v0.157.1 and the config documentation.
3. Claude Code: the Notification hook types and timings in the hooks reference; whether the receipt and decision record quote the reference correctly.
4. Receipt hygiene: no home paths, user names, GUIDs of the user's own host state, session ids or credentials; every `native_proven` row names a command or artifact that really produces it; every limitation is stated where a reader needs it.""",
                 packet_note="The decision record is docs/decisions/2026-09-28-terminal-experience.md (first part); the receipt is evidence/receipts/terminal-experience-20260928.json."),
    "u498": dict(pr=498, sha="9ad7bebe", focus_A="""LENS: behaviour and tests. The change records a login-shell incident and adds probes and controls under its evidence artifacts.
1. Run the scripts that need no live session in a scratch copy (login_shell_check_controls.py without --real-host, login_path_digest.py against a throwaway home, scrub_placeholder_probe.py only if it isolates HOME and touches nothing else; landscape_refresh.py is network-only, run it only with its documented flags). Report failures, and any claim the script's output does not support.
2. Bash reads only the first of ~/.bash_profile, ~/.bash_login and ~/.profile for a login shell: build throwaway homes yourself (empty file, real hand-off file, missing files) and confirm the claimed behaviour with `bash -lc` under a scratch HOME, including the hand-off file idiom.
3. Look for a sequence of home states where the doctor-check logic described in the change (and any code in this repository that implements it) would pass or fail incorrectly.
4. The three anti-pattern rows added to the repository's harness-defaults document: check they are accurate, dated and not duplicated elsewhere.""",
                 focus_B="""LENS: claims and evidence. Verify against primary sources and the recorded artifacts.
1. bash(1) INVOCATION and the Bash Reference Manual for the login-shell startup order and the hand-off idiom; the header of /etc/skel/.profile.
2. The upstream statements about CLAUDE_CODE_SUBPROCESS_ENV_SCRUB placeholder files (the issues the change cites, by number) and what the Claude Code documentation says; whether "a maintainer acknowledged it" is what those pages actually show.
3. The landscape-refresh claims ("no new Windows Terminal release, both toast signals unchanged, Claude Code 2.1.284 still newest, Codex notification, palette and kind sources identical between the installed and newest stable tag, candidate pins unchanged") against the sources as of the change's date.
4. Receipt integrity: each number, hash and count against the recorded outputs; hygiene (home paths, user names, host identifiers, session ids); limitations stated where needed.""",
                 packet_note="The decision record is docs/decisions/2026-09-28-terminal-experience.md (update sections dated 2026-09-29); the receipt is evidence/receipts/login-shell-contract-20260929.json."),
    "u510": dict(pr=510, sha="fca73ded", focus_A="""LENS: behaviour and tests. The change carries terminal defaults in the repository: a settings overlay, a Codex template edit, a Windows Terminal profile fragment example, `scripts/adoption_status.py --login-shell`, tests and controls.
1. Run tests.test_windows_terminal_defaults, tests.test_adoption_status, tests.test_adoption_docs_consistency, tests.test_render_config and tests.test_apply_claude_settings in a scratch copy with `python3 -B -m unittest`. Report failures. Then look for tests that cannot fail: mutate the overlay, the fragment example or the login-shell model in the scratch copy and see whether a test notices.
2. `--login-shell` claims to equal real bash's login startup search in 512 of 512 state combinations. Run the bash-truth script if it is in the change, then hunt for a state it does not cover (symlinks to directories or to missing files, unreadable files, a file named with unusual characters, HOME unset or relative, dangling links, a directory in place of the file) and compare the model with real bash.
3. tools/adoption/apply_claude_settings.py merges the overlay: try merging twice, in either order, into hooks that already exist in other shapes (matcher absent, several groups, another hook in the same group) and report a lost or duplicated hook.
4. macOS/Python portability of the new code (the repository supports macOS with bash 3.2 and Python 3.9 in places): anything that would break there.""",
                 focus_B="""LENS: claims and evidence.
1. Verify against primary sources: Codex `--strict-config` behaviour and the `[tui] notifications` schema (codex-rs at rust-v0.157.1 and the documentation); Windows Terminal fragment-profile semantics, including "a fragment profile that declares no guid gets one derived from its name and source" (microsoft/terminal source at v1.24.11911.0), the profile `environment` key replacing `profiles.defaults.environment`, and `suppressApplicationTitle`; the bash login-shell order; the Claude Code settings reference statement that edits to `hooks` apply to a running session.
2. Receipt integrity: each count, hash and result in evidence/receipts/wsl-terminal-defaults-20260929.json and login-shell-contract-20260929.json against the recorded artifacts; claims that rest on the user's private host state must be marked as such and must not leak it.
3. The platform page and recipe: every command shown must work as written and every path must exist; the six repaired defects of the earlier change (listed in the change's description) must actually be fixed in the files.""",
                 packet_note="Docs: adoption/platforms/linux-wsl2.md (Windows Terminal section), recipes/claude-native-profile.md, docs/decisions/2026-09-28-terminal-experience.md; receipts: evidence/receipts/wsl-terminal-defaults-20260929.json and login-shell-contract-20260929.json."),
    "u519a1": dict(pr=519, sha="e45328d3", focus_A="""LENS: behaviour and tests, part 1 of 2 (notification-type scan, decision table, tests, overlay). Part 2 (the settings-swap tool and the probes) is reviewed separately.
1. Files: evidence/artifacts/notification-types-20260929/notification_types_scan.py and scan_reader_mutants.py, tests/test_windows_terminal_defaults.py, adoption/templates/claude.settings.linux-wsl2.overlay.json.
2. Run tests.test_windows_terminal_defaults and the scan against the installed client binary in a scratch copy (`python3 -B .../notification_types_scan.py <binary> <copy>`; the binary path is the resolved target of `command -v claude`, read-only). Check that the scan reads all matcher values whatever the minified spread name is, and that a reader which finds nothing exits nonzero.
3. `DECISIONS` claims to be the single table the scan and the tests share: try to make the overlay matcher, the table and a document copy of the matcher disagree in the scratch copy and see whether a test fails for each; report a disagreement that no test catches.
4. Look for a notification type name in the client binary (strings or minified code) that the scan cannot see because of how it matches, and for any way the regexes over the minified bundle could match the wrong array.""",
                 focus_B="""LENS: claims and evidence.
1. Claude Code hooks reference (Notification section) and the installed binary: the 17 types, the 12 documented ones, `terminalSequence` hook output, `preferredNotifChannel`; the presence rule for the PushNotification tool (the change reads `function V4r`, `var KWt=60000`, `CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK`, `config_off`, the server-side flag) against the installed binary (`grep -a`/`strings` on the read-only binary; quote bytes).
2. Agent teams documentation (code.claude.com/docs/en/agent-teams): display modes, `teammateMode`, the limitation about Windows Terminal, the three team hooks; tmux 3.4 manual (`bell-action`, `visual-bell`); microsoft/terminal `DispatchTypes.hpp` mode 1004 at v1.24.11911.0.
3. Receipt integrity: evidence/receipts/notification-types-20260929.json against evidence/artifacts/notification-types-20260929/recorded/*: every count, exit code, hash (sha256 of the recorded files and scripts), timing and arm result; statements in the decision record's last section and the recipe bullets that go beyond what the recorded outputs show.
4. Hygiene of the added files: home paths, user names, host identifiers, session ids.""",
                 packet_note="Decision record: docs/decisions/2026-09-28-terminal-experience.md (last section, 'Update 2026-09-29 (late)'); recipe: recipes/claude-native-profile.md (the Notification and agent-teams bullets); receipt: evidence/receipts/notification-types-20260929.json; recorded outputs: evidence/artifacts/notification-types-20260929/recorded/."),
    "u519a2": dict(pr=519, sha="e45328d3", focus_A="""LENS: behaviour and tests, part 2 of 2 (the settings-swap tool, its controls and mutants, the probes). Part 1 (scan, decision table, tests) is reviewed separately.
1. Files: evidence/artifacts/notification-types-20260929/replace_bell_group.py, replace_bell_group_controls.py, replace_bell_group_mutants.py, push_notification_probe.py, tmux_bell_probe.py, and tools/adoption/apply_claude_settings.py which the tool calls (write_backup, atomic_write, merge_settings, refuse_symlink).
2. In a scratch copy, run the controls (`python3 -B .../replace_bell_group_controls.py <copy>`) and the mutants script. Then attack the tool with a synthetic HOME: settings files of unusual shapes (hooks that are not objects, Notification that is not a list, non-UTF-8 bytes, a very large file, a bell group with extra keys, matcher variants such as leading/trailing pipes or regex metacharacters, duplicate types), a settings file that is a hard link or lives on a read-only directory, and a backup name that already exists. Report any input where it writes a wrong file, loses a user setting, leaves a staging file, exits 0 after a failed write, or prints a settings value.
3. Judge the mutants: does each mutant remove a guard whose absence a control really detects? Find a guard whose removal no case fails, or a control that would pass for a wrong tool.
4. The tool's `polaris` target writes through `wsl.exe -d Polaris --exec /bin/sh -c ...`. That distro no longer exists and cannot be run; read the shell snippet for quoting, umask, symlink and trap defects and reason from the POSIX shell specification.
5. The probes: read push_notification_probe.py and tmux_bell_probe.py for logic defects (timing gates, the BEL counter, cleanup on failure, leaked payload files). They need a live client and tmux: run only what needs neither.""",
                    focus_B=None, packet_note="The decision record's last section and the receipt describe the tool's guarantees; test the guarantees they state."),
    "u519b": dict(pr=519, sha="e45328d3", focus_A=None, focus_B="""LENS: claims and evidence (all of the change).
1. Claude Code: the presence rule for the PushNotification tool and the statements built on it. Read the installed binary (resolved target of `command -v claude`, read-only; `grep -a -o` with a bounded window) for `function V4r`, `KWt`, `CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK`, the "Not sent" texts, `config_off`, and the emit sites of each notification type; compare with what the recipe, the decision record's last section, the platform page and the receipt say (for example 'a tab last reported focused counts as present however long the user is away').
2. Documentation: hooks reference (Notification), settings reference (`teammateMode`, hooks hot-reload), agent teams (display modes and limitations). Quote the lines the change relies on and say whether it reads them correctly.
3. Windows Terminal: DECSET 1004 in microsoft/terminal at v1.24.11911.0; whether the claim 'bell rings when the tab or window was last reported unfocused' is supported or only inferred.
4. tmux 3.4: the manual's `bell-action`, `visual-bell`, `monitor-bell` defaults.
5. Receipt integrity: every value in evidence/receipts/notification-types-20260929.json (counts, exit codes, hashes, timings, arm results, 'first attempts kept') against evidence/artifacts/notification-types-20260929/recorded/*; sha256 of the listed scripts and recorded files; claims in the pull request's own evidence table (below).
6. Overclaims: sentences in the decision record's last section, the recipe and the platform page that say more than the recorded evidence shows, or that omit a condition the evidence reveals.""",
                  packet_note="Decision record: docs/decisions/2026-09-28-terminal-experience.md (last section); recipe: recipes/claude-native-profile.md; platform page: adoption/platforms/linux-wsl2.md (Windows Terminal section)."),
}


# one prompt per (job name, lens key): PR #519 is split into three jobs that share one packet
LENSES = {"u484": [("u484-A", "focus_A"), ("u484-B", "focus_B")], "u498": [("u498-A", "focus_A"), ("u498-B", "focus_B")],
          "u510": [("u510-A", "focus_A"), ("u510-B", "focus_B")], "u519a1": [("u519-A1", "focus_A")], "u519a2": [("u519-A2", "focus_A")],
          "u519b": [("u519-B", "focus_B")]}
UNITS["u519a1"]["focus_B"] = None  # the claims lens of #519 is the u519b job


def git(*args):
    return subprocess.run(["git", "-C", str(CHECKOUT), *args], capture_output=True, text=True, check=True).stdout


def claims(pr):
    body = (BODIES / f"pr-{pr}.body.md").read_text(encoding="utf-8")
    match = re.search(r"^###? Evidence-class table.*?$\n(.*?)(?=^###? |\Z)", body, re.S | re.M)
    rows = [line for line in (match.group(1) if match else "").splitlines() if line.startswith("|") and not line.startswith("| ---") and not line.startswith("| Claim")]
    out = []
    for number, row in enumerate(rows, 1):
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        out.append(f"{number}. {cells[0][:700]}  [class: {cells[1][:60] if len(cells) > 1 else ''}; recorded in: {cells[2][:200] if len(cells) > 2 else ''}]")
    return out


sizes = {}
for unit, spec in UNITS.items():
    sha = git("rev-parse", spec["sha"]).strip()
    subject = git("log", "-1", "--format=%s", sha).strip()
    files = git("diff", "--name-status", f"{sha}^", sha).strip().splitlines()
    packet = [f"UNIT: PR #{spec['pr']}, merged commit {sha[:12]} (parent {sha[:8]}^)", f"Title: {subject}", f"Changed files ({len(files)}):", *[f"  {line}" for line in files],
              spec["packet_note"], "", "The change's own evidence claims (each is a claim to test, not a fact):", *claims(spec["pr"])]
    for name, key in LENSES[unit]:
        assert spec.get(key), (unit, key)
        prompt = "\n\n".join([COMMON, "\n".join(packet), spec[key]])
        path = OUT / "prompts" / f"{name}.txt"
        path.write_text(prompt + "\n", encoding="utf-8")
        sizes[name] = len(prompt.encode("utf-8"))
print(json.dumps(sizes, indent=1))
print("largest:", max(sizes.values()), "bytes (limit 120000)")
