#!/usr/bin/env python3
"""Value-free: since the wave-1 cutover backup (.bak-1790369060, 16:44:20 EDT), did anything but the
2.3.2 -> 2.4.0 path swap change the Claude hooks subtree? Also: which top-level keys changed (names
only) between that backup and the 22:51:48Z pre-edit backup (content from 22:38:28Z on)."""
import json
import os
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
pre_w1 = (HOME / ".claude/settings.json.bak-1790369060").read_text()
mid = (HOME / ".claude/settings.json.bak.20260925T225148Z").read_text()
cur = (HOME / ".claude/settings.json").read_text()
swap = pre_w1.replace("tools/ai-memory-2.3.2/ai-memory", "tools/ai-memory-2.4.0/ai-memory")
a, m, c = json.loads(swap), json.loads(mid), json.loads(cur)
out = {"hooks_pre_wave1_path_swapped_equals_22:38Z_state": a.get("hooks") == m.get("hooks"),
       "hooks_22:38Z_state_equals_current": m.get("hooks") == c.get("hooks"),
       "top_level_keys_changed_16:44_to_22:38": sorted(k for k in set(a) | set(m) if a.get(k) != m.get(k)),
       "top_level_keys_changed_22:38_to_now": sorted(k for k in set(m) | set(c) if m.get(k) != c.get(k))}
print(json.dumps(out, indent=1))
