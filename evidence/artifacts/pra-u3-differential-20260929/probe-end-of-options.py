"""Counts only: shell argv forms in the host's Codex rollouts that the -- / - end-of-options fix reads differently.

Usage: python3 -B probe-end-of-options.py <skill_usage dir> <codex sessions root>
Reads every CommandExecution item command and local_shell_call action command (all records, copied ones included), and
compares resolve_command at this revision with the reading before the fix (the marker returned as the script)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import skill_usage as S  # noqa: E402


def old_posix_script(parts):
    index, run = 1, False
    while index < len(parts):
        word = parts[index]
        letters = word[1:]
        if not (word[:1] in ("-", "+") and letters and letters.isascii() and letters.isalpha()):
            break
        run |= word[0] == "-" and "c" in letters
        index += 1 + letters.count("o") + letters.count("O")
    return parts[index] if run and index < len(parts) else None


def old_resolve(command):
    if not isinstance(command, list):
        return (command if isinstance(command, str) else ""), None
    parts = [str(part) for part in command]
    stem = S._program_stem(parts[0]) if parts else ""
    if stem.isascii() and stem.lower() in S.NON_POSIX_PROGRAMS:
        return "", "non_posix_shell"
    script = old_posix_script(parts) if stem in S.SCRIPT_SHELLS else None
    return (S.shlex.join(parts) if script is None else script), None


files = argvs = differ = marker_words = parse_errors = 0
for path in sorted(Path(sys.argv[2]).rglob("rollout-*.jsonl")):
    files += 1
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                parse_errors += 1
                continue
            payload = record.get("payload") if isinstance(record, dict) and isinstance(record.get("payload"), dict) else {}
            command = None
            if record.get("type") == "event_msg" and payload.get("type") == "item_completed":
                item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
                if item.get("type") == "CommandExecution":
                    command = item.get("command")
            elif record.get("type") == "response_item" and payload.get("type") == "local_shell_call":
                command = (payload.get("action") or {}).get("command")
            if not isinstance(command, list):
                continue
            argvs += 1
            marker_words += any(str(word) in ("--", "-") for word in command[1:])
            differ += S.resolve_command(command) != old_resolve(command)
print(f"files={files} parse_errors={parse_errors} argv_commands={argvs} argv_with_a_--_or_-_word={marker_words} "
      f"read_differently={differ}")
