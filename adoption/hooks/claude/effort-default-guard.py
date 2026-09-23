#!/usr/bin/env python3
"""Keep the main-session effort at the ecosystem default (xhigh) across model releases.

Claude Code 2.1.251+ saves effort per model under `modelSettings`. In USER settings the
top-level `effortLevel` applies only to Opus 5, Fable 5.1 and earlier models; Opus 5.5 and
later ignore it and start at their own default (Opus 5.5: medium). In project, local and
managed settings a top-level `effortLevel` applies to every model. Resolution: env
CLAUDE_CODE_EFFORT_LEVEL, then the highest-precedence file (managed > local > project > user)
that sets `modelSettings.<model>.effortLevel` or an applicable top-level `effortLevel`; an
`ultracode: true` session runs at xhigh; any `maxEffortLevel` caps it.
Source: https://code.claude.com/docs/en/settings-reference (fetched 2026-09-23).

Events:
  SessionStart: predictive warning when the resolved level for the model (if the event carries
    `model`; headless sessions omit it) is below xhigh.
  SessionEnd: reads the finished transcript for the model and effort the session actually used
    (Stop hooks run before the turn's assistant row is written, so they cannot see the model). When that effort is below xhigh only because the model has no saved
    per-model level anywhere, saves `modelSettings.<model>.effortLevel = "xhigh"` in the user
    settings (what `/effort xhigh` writes) and says so. Never overrides a saved level, never
    blocks, and exits 0 on any error.
"""
import json
import os
import re
import sys
import tempfile

WANT = "xhigh"
RANK = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}
USER = os.path.expanduser("~/.claude/settings.json")
MANAGED = "/etc/claude-code/managed-settings.json"
# Models where a USER-settings top-level effortLevel still applies (docs: "Opus 5, Fable 5.1, and
# earlier models"; Sonnet 5 observed at xhigh from the top-level key on 2026-09-23).
LEGACY_EXACT = {"claude-opus-5", "claude-fable-5-1", "claude-fable-5", "claude-mythos-5-1", "claude-mythos-5", "claude-sonnet-5"}
LEGACY_PREFIX = ("claude-opus-4-", "claude-sonnet-4-", "claude-haiku-4-", "claude-3")


def canonical(model):
    m = model.strip().lower()
    m = re.sub(r"\[[^\]]*\]$", "", m)
    m = re.sub(r"^(?:[a-z]{2}\.)?anthropic\.", "", m)
    m = re.sub(r"(?:-v\d+(?::\d+)?)$", "", m)
    m = re.sub(r"[-@]\d{8}$", "", m)
    return m


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def project_files(cwd):
    d = os.path.abspath(cwd or os.getcwd())
    home = os.path.expanduser("~")
    while True:
        cand = [os.path.join(d, ".claude", n) for n in ("settings.local.json", "settings.json")]
        if d != home and any(os.path.exists(c) for c in cand):
            return [(c.rsplit("/", 1)[1].replace("settings.json", "project").replace("settings.local.json", "local"), load(c) or {}) for c in cand]
        parent = os.path.dirname(d)
        if parent == d or d == home:
            return []
        d = parent


def resolve(name, cwd):
    """Return (level, source, capped_by) for the main session of model `name`."""
    env = os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")
    files = []  # highest precedence first
    managed = load(MANAGED)
    if managed:
        files.append(("managed", managed))
    files += project_files(cwd)          # local, then project
    user = load(USER) or {}
    files.append(("user", user))
    caps = []
    for tag, s in files:
        per = {canonical(k): v for k, v in (s.get("modelSettings") or {}).items() if isinstance(v, dict)}
        if s.get("maxEffortLevel") in RANK:
            caps.append((s["maxEffortLevel"], tag))
        if (per.get(name) or {}).get("maxEffortLevel") in RANK:
            caps.append((per[name]["maxEffortLevel"], tag + " modelSettings"))
    cap = min(caps, key=lambda c: RANK[c[0]]) if caps else None
    level, source = None, None
    if env:
        level, source = env.lower(), "CLAUDE_CODE_EFFORT_LEVEL"
    else:
        ultra = next((s.get("ultracode") for tag, s in files if "ultracode" in s), None)
        if ultra is True:
            level, source = "xhigh", "ultracode"
        else:
            for tag, s in files:
                per = {canonical(k): v for k, v in (s.get("modelSettings") or {}).items() if isinstance(v, dict)}
                if (per.get(name) or {}).get("effortLevel") in RANK:
                    level, source = per[name]["effortLevel"], tag + " modelSettings"
                    break
                top = s.get("effortLevel")
                if top in RANK and (tag != "user" or name in LEGACY_EXACT or name.startswith(LEGACY_PREFIX)):
                    level, source = top, tag + " effortLevel"
                    break
    if level in RANK and cap and RANK[cap[0]] < RANK[level]:
        return cap[0], source, cap[1]
    return level, source, None


def saved_anywhere(name, cwd):
    for tag, s in ([("managed", load(MANAGED) or {})] + project_files(cwd) + [("user", load(USER) or {})]):
        per = {canonical(k): v for k, v in (s.get("modelSettings") or {}).items() if isinstance(v, dict)}
        if (per.get(name) or {}).get("effortLevel"):
            return True
    return False


def save_user_level(name):
    s = load(USER)
    if not isinstance(s, dict):
        return False
    ms = s.setdefault("modelSettings", {})
    if any(canonical(k) == name and isinstance(v, dict) and v.get("effortLevel") for k, v in ms.items()):
        return False
    ms.setdefault(name, {})["effortLevel"] = WANT
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(USER), prefix=".settings.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    try:
        os.chmod(tmp, os.stat(USER).st_mode & 0o777)
    except OSError:
        pass
    os.replace(tmp, USER)
    return True


def observed(transcript):
    model = effort = None
    try:
        with open(transcript) as f:
            for line in f:
                if '"assistant"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("type") == "assistant" and (r.get("message") or {}).get("model") not in (None, "<synthetic>"):
                    model, effort = r["message"]["model"], r.get("effort")
    except Exception:
        pass
    return model, effort


def emit(msg, event):
    out = {"systemMessage": msg}
    if event == "SessionStart":
        out["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": msg}
    print(json.dumps(out))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    event = data.get("hook_event_name") or ("Stop" if "stop_hook_active" in data else "SessionStart")
    cwd = data.get("cwd") or os.getcwd()
    if event == "SessionStart":
        model = data.get("model")
        if not isinstance(model, str) or not model:
            return
        name = canonical(model)
        if not name.startswith("claude-"):
            return
        level, source, capped = resolve(name, cwd)
        if level in RANK and RANK[level] >= RANK[WANT]:
            return
        why = (f"capped at {level} by maxEffortLevel ({capped})" if capped else
               f"set to {level} by {source}" if level else "without a saved level, so it runs at the model's own default")
        emit(f"Effort default check: {name} is {why}; the ecosystem default is {WANT}. "
             f"Run `/effort {WANT}` to save it for this model (user-settings top-level effortLevel does not apply to Opus 5.5 and later).", event)
        return
    if event != "SessionEnd":
        return
    model, effort = observed(data.get("transcript_path") or "")
    if not model:
        return
    name = canonical(model)
    if not name.startswith("claude-") or effort not in RANK or RANK[effort] >= RANK[WANT]:
        return
    if os.environ.get("CLAUDE_CODE_EFFORT_LEVEL") or saved_anywhere(name, cwd):
        return  # an explicit or saved choice: respect it
    level, source, capped = resolve(name, cwd)
    if capped or level is not None:
        return  # some settings file already gives this model a level; a lower effort was an explicit session choice (--effort, /effort)
    if save_user_level(name):
        emit(f"Effort default: {name} ran this session at {effort} because it had no saved effort level. "
             f"Saved modelSettings.{name}.effortLevel = {WANT} in ~/.claude/settings.json, so new sessions start at {WANT}; "
             f"use `/effort {WANT}` to raise this session now.", event)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
