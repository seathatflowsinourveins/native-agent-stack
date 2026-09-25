"""Kill-switch drill trigger for one adaptive paper run (stdlib only, no broker access).

Watches the runner's --live-dir events.jsonl and creates the shared STOP file
(safety.DEFAULT_STOP, ~/.local/state/native-agent-stack/alpaca-paper/STOP) as soon
as the first buy intent is journaled, so an entry order is most likely still
working at the broker when the engine's next loop tick sees STOP. If no buy intent
appears before --deadline-seconds after the events file appears, it creates STOP
anyway (that case can show the halt of new orders, not the cancel of a working one).
It never reads credentials, never talks to the broker and never removes STOP.
Writes one JSON record (no host paths) to --out.
"""
import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

STOP = Path.home() / ".local/state/native-agent-stack/alpaca-paper/STOP"


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--deadline-seconds", type=float, default=200.0)
    parser.add_argument("--appear-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-seconds", type=float, default=0.01)
    args = parser.parse_args()
    if STOP.exists():
        raise SystemExit("refused: STOP already exists; this drill only creates it")
    record = {"kind": "adaptive_paper_stop_drill_trigger", "stop_file": "~/.local/state/native-agent-stack/alpaca-paper/STOP",
              "watcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "deadline_seconds": args.deadline_seconds, "watch_started_at": utc(time.time())}
    t0 = time.monotonic()
    while not args.events.exists():
        if time.monotonic() - t0 > args.appear_timeout_seconds:
            record.update(trigger="none", error="events_file_never_appeared")
            args.out.write_text(json.dumps(record, indent=1) + "\n")
            raise SystemExit(2)
        time.sleep(args.poll_seconds)
    appeared = time.time()
    record["events_file_appeared_at"] = utc(appeared)
    offset, buffer, trigger, intent = 0, b"", None, None
    while trigger is None:
        with args.events.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read()
        offset += len(chunk)
        buffer += chunk
        *lines, buffer = buffer.split(b"\n")
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "intent" and event.get("side") == "buy":
                trigger, intent = "first_buy_intent", event
                break
        if trigger is None and time.time() - appeared >= args.deadline_seconds:
            trigger = "deadline"
        if trigger is None:
            time.sleep(args.poll_seconds)
    fd = os.open(STOP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    created = time.time()
    try:
        os.write(fd, ("adaptive paper STOP drill %s\n" % utc(created)).encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    record.update(trigger=trigger, stop_created_at=utc(created), stop_created_epoch=created)
    if intent is not None:
        record["intent"] = {k: intent.get(k) for k in ("client_id", "symbol", "side", "strategy", "reason")}
        record["intent_journaled_at"] = utc(intent["at"])
        record["stop_after_intent_ms"] = round((created - intent["at"]) * 1000, 1)
    args.out.write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps({"trigger": trigger, "stop_created_at": record["stop_created_at"]}))


if __name__ == "__main__":
    main()
