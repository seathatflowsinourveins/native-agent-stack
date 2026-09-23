#!/usr/bin/env python3
"""Redact the gap-0 codex-acp adapter log (APP_SERVER_LOGS) for commit.

Each line is `<date> <time> [DIR] <payload>`. JSON-RPC messages carrying account, config, skills,
remote-control or rate-limit payloads (account identity, the user's full Codex config, installed
skill paths, host name, quota) have their params/result replaced by "<withheld: METHOD payload>";
responses are matched to their request by id. All other messages stay verbatim apart from the
generic redactions: e-mail addresses, the Windows host name, /home/<user>, UUIDs (<id-N>).
Usage: redact_adapter_log.py SRC DST
"""
import json
import re
import sys

WITHHOLD = {"account/read", "config/read", "skills/list", "remoteControl/status/changed", "account/rateLimits/updated"}
LINE = re.compile(r"^(\S+ \S+ \[(?:IN|OUT|SYS|ERR)\] )(.*)$")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


def main(src, dst):
    pending = {}  # request id -> method
    ids = {}
    withheld = {}
    out = []
    for line in open(src, encoding="utf-8", errors="replace").read().splitlines():
        m = LINE.match(line)
        if m:
            head, payload = m.groups()
            try:
                msg = json.loads(payload)
            except ValueError:
                msg = None
            if isinstance(msg, dict):
                method = msg.get("method")
                if method and "id" in msg:
                    pending[msg["id"]] = method
                target = method or pending.get(msg.get("id"))
                if target in WITHHOLD:
                    for k in ("params", "result"):
                        if k in msg:
                            msg[k] = f"<withheld: {target} payload>"
                    withheld[target] = withheld.get(target, 0) + 1
                    line = head + json.dumps(msg, separators=(",", ":"))
        line = UUID.sub(lambda u: ids.setdefault(u.group(0).lower(), f"<id-{len(ids) + 1}>"), line)
        line = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<email>", line)
        line = re.sub(r"DESKTOP-[A-Z0-9]+", "<host>", line)
        line = re.sub(r"/home/[A-Za-z0-9_.-]+", "$HOME", line)
        out.append(line)
    open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(json.dumps({"lines": len(out), "withheld_messages": withheld, "uuids_redacted": len(ids)}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
