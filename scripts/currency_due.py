#!/usr/bin/env python3
"""Write a one-line currency notice for the next session when a pin, receipt or layer is due.

The daily user timer adoption/templates/systemd/stack-currency.timer runs this. It runs this checkout's own
read-only checks as subprocesses, with the arguments their weekly workflows use, and aggregates four counts:

- pins_behind: components whose platform pin's version probe did not observe the pinned version
  (scripts/adoption_status.py --pinned-versions --json, the "mismatched" ids of each selected profile, each id
  once); with --network also the runtime-worker skill pins that tools/adoption/runtime_skill_freshness.py reports
  as drifted from upstream HEAD (skill-drift, repository-drift, removed-at-head) or as not matching their recorded
  tree (invalid-pin, a fetched answer), and a drifted skills CLI pin;
- stale_receipts: the component x platform buckets scripts/receipt_staleness.py --json flags ("flagged");
- due_layers: the layers scripts/saturation_ledger.py --report --json marks due (not a saturation candidate) whose
  last completed sweep is at least --sweep-cadence-days old, or that have none or an undatable one. The default,
  30, follows recipes/saturation-sweep.md ("Sweep only the due layers, at most monthly"); 0 counts every layer
  the report marks due;
- reopen_triggers: the layers with a current reopen trigger in that report (the recipe's "or sooner when a reopen
  trigger fires").

When any count is nonzero it writes ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/currency-due.json
atomically (a temporary file in the same directory, fsync, mode 0600, os.replace):

  {"generated_at": "YYYY-MM-DDTHH:MM:SSZ", "root": "the inspected checkout", "due": {the four counts},
   "summary_line": "at most 160 characters, ending with the command below or with `cat <this file>`",
   "details_command": "the command below", "details": [...]}

and otherwise removes that file, unless the run could not see everything it was asked to check. A skill check
(--network) that answered incompletely, meaning an error in its report, a skill left unfetched or in a state this
script does not know, or a skills CLI release that was not fetched, is unknown, and unknown is not "nothing due"
(the check's own report says "Incomplete fetches remain unknown"). Such a run writes the file when the counts it
did reach are nonzero, with the gap in the coverage entry of the details, and otherwise leaves the state
directory as it was: no removal and no new file, exit 0.

The command that ends summary_line is "python3 <checkout>/scripts/currency_due.py --dry-run", the inspected checkout's
own copy of this script by its absolute path, written as ~/... under the home directory (so the command works from any
working directory, stays short and names the checkout it inspected), plus the options that change what a run reports, --network and a non-default --sweep-cadence-days, so
that running it prints the details of the notice. A checkout without the script is named by --root instead. When the
absolute command would leave the counts no room in the line, the line ends with "cat <due-file>" instead, a short
command that prints this document, whose details_command field carries the full command and whose root field names
the checkout; when the resolved path is too long for that and the state directory came from XDG_STATE_HOME, the
symbolic `cat "$XDG_STATE_HOME"/native-agent-stack/currency-due.json` is used (the hook that prints the line resolves
the same variable); an explicit --state-dir too long for any runnable form is refused before the checks run. Every
emitted line ends with a runnable command, never a cwd-relative one, and never exceeds 160 characters. A SessionStart hook, a separate change, prints summary_line in whatever project the session
starts in when the file exists and nothing when it does not (docs/decisions/2026-09-30-session-currency-notice.md).

  python3 scripts/currency_due.py                    # write or remove the due-file; one line for the journal
  python3 scripts/currency_due.py --dry-run          # the report as text; writes and removes nothing
  python3 scripts/currency_due.py --dry-run --json   # the due-file document; writes and removes nothing
  python3 scripts/currency_due.py --network          # also compare runtime-worker skill pins through gh api

No network call unless --network is given. It exits 0 whether or not anything is due, and 2 on an internal error:
a check that fails, times out or prints something other than its JSON report (a field of the wrong type included),
an unreadable saturation ledger or a failed write. An error leaves the state directory as it was.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_NAME = "native-agent-stack"
DUE_FILE = "currency-due.json"
DUE_KEYS = ("pins_behind", "stale_receipts", "due_layers", "reopen_triggers")
LABELS = {"pins_behind": ("pin behind", "pins behind"),
          "stale_receipts": ("stale receipt", "stale receipts"),
          "due_layers": ("layer due", "layers due"),
          "reopen_triggers": ("layer with reopen triggers", "layers with reopen triggers")}
SUMMARY_LIMIT = 160
# The smallest count text is "1 pin behind"; a command that leaves the counts less room than that gives way to
# "cat <due-file>" (the document carries the command in full), and that to the symbolic XDG form when the state
# directory came from XDG_STATE_HOME. The last pointer is used even when it leaves the counts less room.
MIN_COUNTS_ROOM = len("1 pin behind")
XDG_POINTER = f'cat "$XDG_STATE_HOME"/{STATE_NAME}/{DUE_FILE}'
DETAILS_SCRIPT = "scripts/currency_due.py"
DETAILS_COMMAND = f"python3 {DETAILS_SCRIPT} --dry-run"
# recipes/saturation-sweep.md: "Sweep only the due layers, at most monthly"; 30 days is also
# scripts/receipt_staleness.py's DEFAULT_MAX_AGE_DAYS.
DEFAULT_SWEEP_CADENCE_DAYS = 30
# The notice repeats a non-default --sweep-cadence-days in its command; the bound (a hundred years) keeps that short.
MAX_SWEEP_CADENCE_DAYS = 36500
# tools/adoption/runtime_skill_freshness.py compare_skill() (:77-81) gives each skill one state. main() (:152) counts
# the first three as drift. "invalid-pin" is a fetched answer: the manifest's tree is not the tree at the pinned ref.
# "unfetched" is no answer, and so is a state that is none of these, which a newer check may add.
SKILL_DRIFT_STATES = ("skill-drift", "repository-drift", "removed-at-head")
SKILL_INVALID_STATE = "invalid-pin"
SKILL_CURRENT_STATE = "current"
ERROR_SAMPLES = 5  # of the skill check's own error strings that the details keep (value-free by design, :46-47)
ISO_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")  # host_receipts.ISO_UTC_PATTERN
LEDGER = "catalogs/saturation/ledger.json"  # scripts/saturation_ledger.py LEDGER
SKILLS_MANIFEST = "blueprints/runtime-workers/skills/manifest.json"  # runtime_skill_freshness.py DEFAULT_MANIFEST

# (script, exit codes that still carry its JSON report, timeout in seconds). adoption_status.py exits 2 whenever
# prerequisites are missing and bounds each version probe at 30 s; runtime_skill_freshness.py exits 1 whenever its
# report is not ok (errors, or a skill whose manifest tree does not match its pin, :115; drift alone exits 0), and
# its gh api calls time out at 60 s each.
RECEIPTS = ("scripts/receipt_staleness.py", frozenset({0}), 120)
LAYERS = ("scripts/saturation_ledger.py", frozenset({0}), 120)
PINS = ("scripts/adoption_status.py", frozenset({0, 2}), 600)
SKILLS = ("tools/adoption/runtime_skill_freshness.py", frozenset({0, 1}), 900)


class CheckError(Exception):
    """A check failed or printed something other than its report; nothing is written or removed."""


def default_state_dir(environ=os.environ) -> Path:
    """$XDG_STATE_HOME/native-agent-stack, or ~/.local/state/native-agent-stack when XDG_STATE_HOME is unset, empty or
    relative (the XDG Base Directory specification treats a relative value as invalid)."""
    configured = environ.get("XDG_STATE_HOME") or ""
    if os.path.isabs(configured):
        return Path(configured) / STATE_NAME
    home = environ.get("HOME") or str(Path.home())
    return Path(home) / ".local/state" / STATE_NAME


def run_check(root: Path, check: tuple, arguments: list[str]) -> str:
    """Run one check of ``root`` with this interpreter; return its stdout when it exits with an accepted code."""
    script, accepted, timeout = check
    name = Path(script).name
    try:
        result = subprocess.run([sys.executable, str(root / script), *arguments], cwd=root, capture_output=True,
                                text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False)
    except subprocess.TimeoutExpired:
        raise CheckError(f"{name} timed out after {timeout} s") from None
    except OSError as error:
        raise CheckError(f"{name} could not start ({type(error).__name__})") from None
    if result.returncode not in accepted:
        last = next((line.strip() for line in reversed(result.stderr.splitlines()) if line.strip()), "")
        raise CheckError(f"{name} exited {result.returncode}" + (f": {last[:300]}" if last else ""))
    return result.stdout


def parse_report(name: str, text: str) -> dict:
    try:
        report = json.loads(text)
    except json.JSONDecodeError:
        raise CheckError(f"{name} printed malformed JSON") from None
    if not isinstance(report, dict):
        raise CheckError(f"{name} printed JSON that is not an object")
    return report


def field(report: dict, key: str, kind: type, name: str):
    value = report.get(key)
    if not isinstance(value, kind) or (kind is int and (isinstance(value, bool) or value < 0)):
        raise CheckError(f"{name} report has no valid {key!r} ({kind.__name__} expected)")
    return value


def strings(value, label: str, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CheckError(f"{name} report has no valid {label!r} (list of strings expected)")
    return value


def sweep_dates(root: Path) -> dict[str, str]:
    """{sweep_id: date} for the ledger's completed sweeps: a layer's ``last_sweep`` in the saturation report names
    only completed sweeps (saturation_ledger.derive() skips stopped ones)."""
    try:
        ledger = json.loads((root / LEDGER).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise CheckError(f"{LEDGER} is unreadable or not JSON") from None
    sweeps = ledger.get("sweeps") if isinstance(ledger, dict) else None
    if not isinstance(sweeps, list):
        raise CheckError(f"{LEDGER} has no sweeps list")
    return {sweep["sweep_id"]: sweep["date"] for sweep in sweeps
            if isinstance(sweep, dict) and sweep.get("status") == "completed"
            and isinstance(sweep.get("sweep_id"), str) and isinstance(sweep.get("date"), str)}


def collect(root: Path, now_text: str, network: bool) -> dict:
    """Each check's report. The receipt report reaches saturation_ledger.py as a file, the way
    .github/workflows/saturation-tracking.yml composes them, in a temporary directory outside the checkout."""
    with tempfile.TemporaryDirectory(prefix="currency-due-") as scratch:
        receipts_text = run_check(root, RECEIPTS, ["--root", str(root), "--json", "--now", now_text])
        receipts = parse_report(Path(RECEIPTS[0]).name, receipts_text)
        handed = Path(scratch) / "receipt-staleness.json"
        handed.write_text(receipts_text, encoding="utf-8")
        layers = parse_report(Path(LAYERS[0]).name, run_check(
            root, LAYERS, ["--root", str(root), "--report", "--json", "--staleness", str(handed)]))
        pins = parse_report(Path(PINS[0]).name, run_check(
            root, PINS, ["--manifest", str(root / "adoption/manifest.json"), "--pinned-versions", "--json"]))
        skills = None
        if network:
            output = Path(scratch) / "runtime-skill-freshness.json"
            run_check(root, SKILLS, ["--manifest", str(root / SKILLS_MANIFEST), "--output", str(output)])
            try:
                skills_text = output.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                raise CheckError(f"{Path(SKILLS[0]).name} wrote no report") from None
            skills = parse_report(Path(SKILLS[0]).name, skills_text)
    return {"receipts": receipts, "layers": layers, "pins": pins, "skills": skills, "sweep_dates": sweep_dates(root)}


def report_options(network: bool, cadence_days: int) -> list[str]:
    """The options that change what a run reports; the notice's command repeats them so that it reproduces the
    run. --state-dir, --now and --json do not belong in a notice."""
    options = ["--network"] if network else []
    if cadence_days != DEFAULT_SWEEP_CADENCE_DAYS:
        options += ["--sweep-cadence-days", str(cadence_days)]
    return options


def notice_path(path: Path) -> str:
    """``path`` as the notice writes it: under the home directory as ~/..., which every shell expands at the start
    of a word and which keeps the line short, unless the rest would need quoting (a quoted ~ is not expanded);
    otherwise absolute."""
    try:
        relative = path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)
    return "~/" + relative if relative != "." and shlex.quote(relative) == relative else str(path)


def join_command(tokens: list[str]) -> str:
    """shlex.join, except that a ~/... token from notice_path stays unquoted (shlex would quote the ~, and the
    shell expands only an unquoted one; notice_path only emits it when the rest needs no quoting)."""
    return " ".join(token if token.startswith("~/") and shlex.quote(token[2:]) == token[2:] else shlex.quote(token)
                    for token in tokens)


def details_command(root: Path, network: bool, cadence_days: int) -> str:
    """The command that prints the details of a run made with these options from any working directory: the
    inspected checkout's own copy of this script by its path (notice_path; the checkout travels inside it),
    --dry-run and report_options(). A checkout without the script is inspected by this script with --root naming
    it. The SessionStart hook prints the line in whatever project a session starts in, so a cwd-relative command
    would run in the wrong checkout or none."""
    script = root / DETAILS_SCRIPT
    if script.is_file():
        command = ["python3", notice_path(script), "--dry-run"]
    else:
        command = ["python3", notice_path(Path(__file__).resolve()), "--dry-run", "--root", notice_path(root)]
    return join_command([*command, *report_options(network, cadence_days)])


def summary_line(due: dict, command: str = DETAILS_COMMAND, complete: bool = True,
                 pointers: list[str] = ()) -> str:
    """The nonzero counts and the command that prints the details, in at most SUMMARY_LIMIT characters. With no
    count and a check that could not answer, the line says so rather than "nothing due". When ``command`` leaves
    the counts less than MIN_COUNTS_ROOM characters, the first of ``pointers`` (``cat <due-file>``, then the
    symbolic XDG form; the document carries the command in its details_command field) that leaves them that room
    takes its place, else the last pointer with the counts shortened; the line never names a cwd-relative command
    and never exceeds SUMMARY_LIMIT."""
    parts = [f"{due[key]} {LABELS[key][0] if due[key] == 1 else LABELS[key][1]}" for key in DUE_KEYS if due[key]]
    if not parts:
        return ("stack currency: nothing due" if complete else
                "stack currency: nothing known due, skill check incomplete")
    prefix = "stack currency: "
    suffix = f"; details: {command}"
    for candidate in pointers:
        if SUMMARY_LIMIT - len(prefix) - len(suffix) >= MIN_COUNTS_ROOM:
            break
        suffix = f"; details: {candidate}"
    counts, room = ", ".join(parts), SUMMARY_LIMIT - len(prefix) - len(suffix)
    if len(counts) > room:
        counts = counts[:max(room, 3) - 3] + "..."
    line = prefix + counts + suffix
    if len(line) > SUMMARY_LIMIT:
        raise CheckError(f"summary line of {len(line)} characters exceeds {SUMMARY_LIMIT}: {line!r}")
    return line


def due_file_pointers(due_file: Path | None, from_xdg: bool) -> list[str]:
    """The runnable commands that print the document, shortest last: ``cat`` of the resolved path (notice_path),
    then the symbolic XDG form when the state directory came from XDG_STATE_HOME."""
    if due_file is None:
        return []
    pointers = [join_command(["cat", notice_path(due_file)])]
    if from_xdg:
        pointers.append(XDG_POINTER)
    return pointers


def fits_with_a_pointer(due_file: Path, from_xdg: bool) -> bool:
    """Whether some runnable pointer leaves the smallest count text room in the line; an explicit --state-dir that
    does not is refused before the checks run, since no runnable command could name it."""
    prefix_and_smallest = len("stack currency: ") + MIN_COUNTS_ROOM + len("; details: ")
    return any(prefix_and_smallest + len(pointer) <= SUMMARY_LIMIT for pointer in due_file_pointers(due_file, from_xdg))


def aggregate(reports: dict, now: datetime, now_text: str, cadence_days: int, root: Path = ROOT,
              due_file: Path | None = None, from_xdg: bool = False) -> dict:
    """The due-file document from the checks' reports (their JSON shapes; see the module docstring)."""
    details: list[dict] = []

    name = Path(PINS[0]).name
    pins = reports["pins"]
    errors = field(pins, "errors", list, name)
    if errors:
        raise CheckError(f"{name} reported: {'; '.join(str(item) for item in errors)[:300]}")
    mismatched: dict[str, dict] = {}
    unchecked: set[str] = set()
    for profile in field(pins, "profiles", list, name):
        if not isinstance(profile, dict):
            raise CheckError(f"{name} report has a profile that is not an object")
        summary = field(profile, "pinned_versions_summary", dict, name)
        versions = {}
        for item in field(profile, "pinned_versions", list, name):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise CheckError(f"{name} report has a pinned_versions entry that is not an object with a string 'id'")
            versions[item["id"]] = item.get("pinned_version")
        for component in strings(summary.get("mismatched"), "mismatched", name):
            entry = mismatched.setdefault(component, {"kind": "pin_mismatch", "component_id": component,
                                                      "pinned_version": versions.get(component), "profiles": []})
            entry["profiles"].append(profile.get("id"))
        unchecked.update(strings(summary.get("unchecked"), "unchecked", name))
    details += [mismatched[component] for component in sorted(mismatched)]
    pins_behind = len(mismatched)

    # A skill entry or the CLI release that the check could not answer is unresolved, and an error in its report is an
    # error; either makes the check incomplete, which keeps an earlier due-file (main) and is never "nothing due".
    skills, skills_errors, skills_unresolved = reports["skills"], None, None
    if skills is not None:
        name = Path(SKILLS[0]).name
        entries = field(skills, "skills", list, name)
        errors = strings(skills.get("errors"), "errors", name)
        skills_errors, skills_unresolved = len(errors), 0
        for entry in entries:
            if not isinstance(entry, dict):
                raise CheckError(f"{name} report has a skill that is not an object")
            state = entry.get("state")
            if state == SKILL_CURRENT_STATE:
                continue
            if state in SKILL_DRIFT_STATES or state == SKILL_INVALID_STATE:
                details.append({"kind": "skill_drift" if state in SKILL_DRIFT_STATES else "skill_pin_invalid",
                                "skill": entry.get("name"), "source": entry.get("source"), "state": state,
                                "pinned_ref": entry.get("pinned_ref"), "head_ref": entry.get("head_ref")})
                pins_behind += 1
            else:
                skills_unresolved += 1
        cli = skills.get("cli") if isinstance(skills.get("cli"), dict) else {}
        if cli.get("drift") is True:
            details.append({"kind": "skills_cli_drift", "pinned": cli.get("pinned"), "latest": cli.get("latest")})
            pins_behind += 1
        elif cli.get("drift") is not False:
            skills_unresolved += 1
        details += [{"kind": "skills_probe_error", "error": error[:200]} for error in errors[:ERROR_SAMPLES]]
    skills_complete = None if skills is None else not (skills_errors or skills_unresolved)

    name = Path(RECEIPTS[0]).name
    receipts = reports["receipts"]
    stale_receipts = field(receipts, "flagged", int, name)
    for row in field(receipts, "rows", list, name):
        if not isinstance(row, dict):
            raise CheckError(f"{name} report has a row that is not an object")
        flags = strings(row.get("flags"), "flags", name)
        if flags:
            details.append({"kind": "stale_receipt", "platform_id": row.get("platform_id"),
                            "component_id": row.get("component_id"), "flags": flags,
                            "pin_moved_hosts": row.get("pin_moved_hosts") or []})

    name = Path(LAYERS[0]).name
    layers = reports["layers"]
    due_total = len(field(layers, "due", list, name))
    triggers = field(layers, "current_reopen_triggers", dict, name)
    due_layers = 0
    for layer in field(layers, "layers", list, name):
        if not isinstance(layer, dict):
            raise CheckError(f"{name} report has a layer that is not an object")
        if layer.get("due") is not True:
            continue
        last = layer.get("last_sweep")
        swept = reports["sweep_dates"].get(last) if isinstance(last, str) else None
        age = None
        if swept is not None:
            with contextlib.suppress(ValueError):
                age = (now.date() - date.fromisoformat(swept)).days
        if cadence_days == 0 or age is None or age >= cadence_days:
            due_layers += 1
            details.append({"kind": "due_layer", "layer": f"{layer.get('catalog')}/{layer.get('layer_id')}",
                            "last_sweep": last, "last_sweep_date": swept, "age_days": age})
    for key, items in triggers.items():
        if not isinstance(items, list):
            raise CheckError(f"{name} report has current_reopen_triggers[{key!r}] that is not a list")
        details.append({"kind": "reopen_trigger", "layer": key, "triggers": items})
    reopen_triggers = len(triggers)

    details.append({"kind": "coverage", "pins_unchecked": len(unchecked), "due_layers_total": due_total,
                    "sweep_cadence_days": cadence_days, "network": skills is not None,
                    "skills_complete": skills_complete, "skills_fetch_errors": skills_errors,
                    "skills_unresolved": skills_unresolved})
    due = {"pins_behind": pins_behind, "stale_receipts": stale_receipts, "due_layers": due_layers,
           "reopen_triggers": reopen_triggers}
    command = details_command(root, skills is not None, cadence_days)
    if due_file is None:  # a direct caller: the default state directory, as main() would resolve it
        due_file, from_xdg = default_state_dir() / DUE_FILE, os.path.isabs(os.environ.get("XDG_STATE_HOME") or "")
    line = summary_line(due, command, skills_complete is not False, due_file_pointers(due_file, from_xdg))
    return {"generated_at": now_text, "root": str(root), "due": due, "summary_line": line,
            "details_command": command, "details": details}


def incomplete(document: dict) -> bool:
    """True when the run could not see everything it was asked to check; the coverage entry is always the last."""
    return document["details"][-1].get("skills_complete") is False


def write_due_file(directory: Path, document: dict) -> Path:
    """Replace the due-file atomically: os.replace of a fsynced, mode-0600 temporary file in the same directory
    (the pattern of saturation_ledger.write_ledger). A failure before the rename leaves the earlier file."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / DUE_FILE
    handle, temporary = tempfile.mkstemp(dir=directory, prefix=".currency-due-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(document, indent=1) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise
    return target


def remove_due_file(directory: Path) -> bool:
    try:
        (directory / DUE_FILE).unlink()
    except FileNotFoundError:
        return False
    return True


def render_text(document: dict) -> str:
    lines = [document["summary_line"]]
    for item in document["details"]:
        kind = item["kind"]
        if kind == "pin_mismatch":
            lines.append(f"  pin: {item['component_id']} did not report its pin {item['pinned_version']} "
                         f"({', '.join(str(profile) for profile in item['profiles'])})")
        elif kind in ("skill_drift", "skill_pin_invalid"):
            lines.append(f"  skill pin: {item['skill']} ({item['source']}): {item['state']}")
        elif kind == "skills_probe_error":
            lines.append(f"  skill check error: {item['error']}")
        elif kind == "skills_cli_drift":
            lines.append(f"  skills CLI pin: {item['pinned']}, latest release {item['latest']}")
        elif kind == "stale_receipt":
            lines.append(f"  receipt: {item['platform_id']} {item['component_id']}: {', '.join(item['flags'])}")
        elif kind == "due_layer":
            since = ("never swept" if item["last_sweep"] is None else
                     f"last swept {item['last_sweep_date']} ({item['age_days']} days ago)" if item["age_days"] is not None
                     else f"last sweep {item['last_sweep']} has no completed date in the ledger")
            lines.append(f"  layer due: {item['layer']}: {since}")
        elif kind == "reopen_trigger":
            names = sorted({str(trigger.get("trigger")) for trigger in item["triggers"] if isinstance(trigger, dict)})
            lines.append(f"  reopen trigger: {item['layer']}: {len(item['triggers'])} ({', '.join(names)})")
        elif kind == "coverage":
            network = ("off" if not item["network"] else "on" if item["skills_complete"] else
                       f"on, incomplete ({item['skills_fetch_errors']} error(s), {item['skills_unresolved']} "
                       f"unresolved): left unknown, never counted as nothing due")
            lines.append(f"coverage: {item['pins_unchecked']} pinned component(s) unchecked on this host; "
                         f"{item['due_layers_total']} layer(s) not yet saturation candidates, due "
                         f"{item['sweep_cadence_days']} days after their last sweep; network checks {network}")
    due = document["due"]
    kinds = {item["kind"] for item in document["details"]}
    actions = []
    if "pin_mismatch" in kinds:
        actions.append("pins: python3 scripts/adoption_status.py --pinned-versions")
    if kinds & {"skill_drift", "skill_pin_invalid", "skills_cli_drift"}:
        actions.append("skill pins: blueprints/runtime-workers/skills/README.md")
    if due["stale_receipts"]:
        actions.append("receipts: python3 scripts/receipt_staleness.py and adoption/update.md")
    if due["due_layers"] or due["reopen_triggers"]:
        actions.append("layers: recipes/saturation-sweep.md")
    if actions:
        lines.append("next: " + "; ".join(actions))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="the checkout whose checks run (default: this one)")
    parser.add_argument("--state-dir", type=Path,
                        help="directory of currency-due.json, outside the checkout (default: "
                             "$XDG_STATE_HOME/native-agent-stack, else ~/.local/state/native-agent-stack)")
    parser.add_argument("--dry-run", action="store_true", help="print the report; write and remove nothing")
    parser.add_argument("--json", action="store_true", help="print the due-file document instead of text")
    parser.add_argument("--network", action="store_true",
                        help="also run tools/adoption/runtime_skill_freshness.py (gh api calls; off by default); "
                             "an incomplete answer never removes an earlier due-file")
    parser.add_argument("--now", help="evaluate at this UTC time (YYYY-MM-DDTHH:MM:SSZ); default: the clock")
    parser.add_argument("--sweep-cadence-days", type=int, default=DEFAULT_SWEEP_CADENCE_DAYS,
                        help=f"count a due layer once its last sweep is this many days old "
                             f"(default {DEFAULT_SWEEP_CADENCE_DAYS}; 0 counts every due layer)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    state = (args.state_dir if args.state_dir is not None else default_state_dir()).expanduser().resolve()
    if state == root or root in state.parents:
        parser.error(f"--state-dir must be outside the checkout ({root}); the due-file never goes into it")
    from_xdg = args.state_dir is None and os.path.isabs(os.environ.get("XDG_STATE_HOME") or "")
    if not fits_with_a_pointer(state / DUE_FILE, from_xdg):
        parser.error(f"--state-dir {state} is too long for the notice line: no runnable command that prints the "
                     f"due-file fits in {SUMMARY_LIMIT} characters; use XDG_STATE_HOME or a shorter path")
    if not 0 <= args.sweep_cadence_days <= MAX_SWEEP_CADENCE_DAYS:
        parser.error(f"--sweep-cadence-days must be between 0 and {MAX_SWEEP_CADENCE_DAYS}")
    if args.now is None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
    else:
        try:
            if not ISO_UTC.fullmatch(args.now):
                raise ValueError
            now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            parser.error(f"--now must look like 2026-09-30T00:00:00Z, got {args.now!r}")
    now_text = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        document = aggregate(collect(root, now_text, args.network), now, now_text, args.sweep_cadence_days, root,
                             state / DUE_FILE, from_xdg)
        action = "dry run"
        if not args.dry_run:
            if any(document["due"].values()):
                action = f"wrote {write_due_file(state, document)}" + (
                    "; the skill check was incomplete" if incomplete(document) else "")
            elif incomplete(document):
                # Unknown is not "nothing due": leave the state directory as it was.
                action = f"kept {state / DUE_FILE}" if (state / DUE_FILE).exists() else "no due-file"
            else:
                action = f"removed {state / DUE_FILE}" if remove_due_file(state) else "no due-file"
    except (CheckError, OSError) as error:
        print(f"currency_due.py: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(document, indent=1))
    elif args.dry_run:
        print(render_text(document))
    else:
        print(f"{document['summary_line']} ({action})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
