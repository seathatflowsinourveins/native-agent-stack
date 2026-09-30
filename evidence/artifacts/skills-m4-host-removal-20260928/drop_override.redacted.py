"""Remove the skillOverrides key of the removed skill verification-before-completion from
~/.claude/settings.json, after a backup; touch no other key. Prints listing states and counts only."""
import json, os, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
NAME = "verification-before-completion"
path = Path.home() / ".claude" / "settings.json"
backups = Path("<settings backup directory>")  # redacted in this artifact
text = path.read_text(); data = json.loads(text)
assert json.dumps(data, indent=2, ensure_ascii=False) + "\n" == text, "format would change"
ov = data["skillOverrides"]; print("before", ov.get(NAME, "<absent>"), len(ov))
if NAME in ov:
    others = {k: v for k, v in ov.items() if k != NAME}; keys = list(data)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"settings.json.{stamp}.pre-m4-override-drop"
    shutil.copy2(path, backup); os.chmod(backup, 0o600)
    del ov[NAME]
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings.", suffix=".tmp")
    with os.fdopen(fd, "w") as h: h.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.chmod(tmp, os.stat(path).st_mode & 0o777); os.replace(tmp, path)
    after = json.loads(path.read_text())
    assert list(after) == keys and after["skillOverrides"] == others
    print("after <absent>", len(after["skillOverrides"]), "backup_label", backup.name)
