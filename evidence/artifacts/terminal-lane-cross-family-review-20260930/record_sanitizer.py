#!/usr/bin/env python3
"""The sanitizer rules that the record builders of the terminal-lane review share (build_findings_record.py, sanitize_results.py, build_recheck_record.py, build_final_record.py).

Paths of the review's private work directories become placeholders, the host user name and every home path are replaced (only the placeholder /home/example is allowed in published files), scratch directories are
replaced, and the names of private project profiles are replaced by <project>. Those names are read from a PRIVATE file that is never committed (~/.local/state/native-agent-stack/private-labels.txt, one label per
line), so no file of this repository names them; a builder refuses to run without the file, and `assert_clean` refuses a record that still holds a home path, the user name or a label."""
import re
import sys
from pathlib import Path

HOME, USER = str(Path.home()), Path.home().name
PRIVATE_FILE = Path.home() / ".local/state/native-agent-stack/private-labels.txt"
STATE_DIRS = ("terminal-lane-review-20260930", "terminal-lane-final-review-20260930")


def private_labels():
    if not PRIVATE_FILE.is_file():
        sys.exit("refused: the private label file (one private project label per line, outside every checkout) is missing, so a label could slip into a record")
    labels = [line.strip() for line in PRIVATE_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not labels:
        sys.exit("refused: the private label file is empty")
    return labels


def rules(extra=()):
    """The (compiled pattern, replacement) pairs, applied in order. `extra` are further private strings (replaced by <private>)."""
    found = []
    for state in STATE_DIRS:
        found += [(re.compile(re.escape(f"{HOME}/.local/state/native-agent-stack/{state}/checkout")), "<checkout>"),
                  (re.compile(re.escape(f"{HOME}/.local/state/native-agent-stack/{state}")), "<work>")]
    found += [(re.compile(r"/var/tmp/(?:rv|vf|sm|ss|rb|tb|ts|srm|rbc|rbm|pm)-?[A-Za-z0-9_]*"), "<scratch>"),
              (re.compile(r"/tmp/(?:rv|vf|sm|ss|rb|tb|ts)-?[A-Za-z0-9_]*"), "<scratch>"),
              (re.compile(re.escape(HOME)), "~"),
              (re.compile(r"\b" + re.escape(USER) + r"\b"), "<user>"),
              *[(re.compile(re.escape(item)), "<private>") for item in extra],
              (re.compile(r"\b(?:" + "|".join(re.escape(label) for label in private_labels()) + r")\b", re.I), "<project>"),
              (re.compile(r"/(?:home|Users)/(?!example(?:/|\b))[A-Za-z0-9_.-]+"), "/home/example")]   # a reviewer's synthetic fixture home: the repository's publication rule allows only /home/example
    return found


def assert_clean(text, what):
    """Refuse a record that still holds the home path, the user name or a private label."""
    assert HOME not in text and USER not in text.replace("<user>", ""), f"{what} still holds a home path or the user name"
    assert not re.search(r"\b(?:" + "|".join(re.escape(label) for label in private_labels()) + r")\b", text, re.I), f"{what} still holds a private project label"
