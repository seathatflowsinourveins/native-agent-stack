"""The sealed snapshot: request, page and completion records in quotes.py's ledger format, raw pages, the seal,
and normalized read access (core.records). Evaluation code; nothing here is under study/fetch/.

Ledger lines (JSON): {"event": "request", <request record fields>}; {"event": "page", "key", "attempt", "file",
"status": 200, "sha256", "bytes", "asof", "vintage"}; {"event": "stamp_complete" | "stamp_incomplete", "key",
"kind", "attempt", "pages", "asof", "vintage", "error"}. The asof (the request's session) and the vintage (the
fetch time, UTC) are separate fields. A request's latest attempt governs.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from core import records
from core.canon import dumps, sha256_bytes
from core.plan import record


class SealError(Exception):
    pass


def normalized_sha256(parser: str, raw: bytes) -> str:
    """sha256 of one page's normalized records (the reparse half of the transport reproduction check)."""
    return sha256_bytes(dumps(records.normalize_page(parser, raw)).encode("utf-8"))


class Store:
    def __init__(self):
        self.req = {}       # key -> request
        self.state = {}     # key -> {"status", "pages": [bytes], "vintage", "attempt", "error"}
        self.history = {}   # key -> earlier attempts (the ledger is append-only)
        self.page_norm = {}  # (key, attempt) -> sealed normalized sha256 per page (read from a ledger)
        self._cache = {}

    # ------------------------------------------------------------ writing
    def put(self, req: dict, complete: bool, pages: list, vintage: str, attempt: int = 0, error=None):
        self.req[req["key"]] = req
        if req["key"] in self.state:
            self.history.setdefault(req["key"], []).append(self.state[req["key"]])
        self.state[req["key"]] = {"status": "complete" if complete else "incomplete", "pages": list(pages),
                                  "vintage": vintage, "attempt": attempt, "error": error}
        self._cache.pop(req["key"], None)

    # ------------------------------------------------------------ reading
    def status(self, key: str):
        st = self.state.get(key)
        return None if st is None else st["status"]

    def has(self, key: str) -> bool:
        return key in self.state

    def bodies(self, key: str) -> list:
        return [json.loads(p) if p else {} for p in self.state[key]["pages"]]

    def parsed(self, key: str):
        if key not in self._cache:
            parser = self.req[key]["parser"]
            parts = [records.PARSERS[parser](b) for b in self.bodies(key)]
            if parser == "daily_bars":
                out = {}
                for p in parts:
                    for sym, rows in p.items():
                        out.setdefault(sym, {}).update(rows)
            elif parser == "auctions":
                out = {}
                for p in parts:
                    for sym, days in p.items():
                        out.setdefault(sym, {}).update(days)
            elif parser == "minute_bars":
                out = {}
                for p in parts:
                    for sym, rows in p.items():
                        out.setdefault(sym, []).append(rows)
                out = {sym: records.merge_minute(chunks) for sym, chunks in out.items()}
            elif parser == "quotes":
                out = {}
                for p in parts:
                    for sym, rows in p.items():
                        out.setdefault(sym, []).append(rows)
                out = {sym: records.merge_quotes(chunks) for sym, chunks in out.items()}
            else:
                out = [r for p in parts for r in p]
            self._cache[key] = out
        return self._cache[key]

    def empty(self, key: str, symbol: str | None = None) -> bool:
        return self.status(key) == "complete" and records.is_empty(self.req[key]["parser"], self.bodies(key), symbol)

    def vintages(self) -> list:
        return sorted({st["vintage"] for st in self.state.values()})

    def incomplete_by_kind(self) -> dict:
        out = {}
        for key, st in self.state.items():
            kind = self.req[key]["kind"]
            row = out.setdefault(kind, {"requests": 0, "incomplete": 0})
            row["requests"] += 1
            row["incomplete"] += st["status"] == "incomplete"
        return out

    def request_records(self) -> list:
        return sorted(record(r) for r in self.req.values())

    # ------------------------------------------------------------ disk
    def write(self, directory) -> str:
        """Write the ledger and pages; returns the snapshot sha256 (the ledger's sha256; the ledger carries every
        page's sha256)."""
        d = Path(directory)
        (d / "pages").mkdir(parents=True, exist_ok=True)
        lines = []
        for key in sorted(self.req):
            req = self.req[key]
            lines.append(dumps({"event": "request", **json.loads(record(req))}))
            name = sha256_bytes(key.encode())[:24]
            for st in self.history.get(key, []) + [self.state[key]]:
                lines.extend(self._attempt_lines(d, key, req, name, st))
        data = ("\n".join(lines) + "\n").encode("utf-8")
        (d / "ledger.jsonl").write_bytes(data)
        return sha256_bytes(data)

    @staticmethod
    def _attempt_lines(d, key, req, name, st) -> list:
        lines = []
        for i, raw in enumerate(st["pages"]):
            fname = f"pages/{name}-{st['attempt']}-{i:04d}.json.gz"
            (d / fname).write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
            lines.append(dumps({"event": "page", "key": key, "attempt": st["attempt"], "file": fname, "status": 200,
                                "sha256": sha256_bytes(raw), "bytes": len(raw),
                                "normalized_sha256": normalized_sha256(req["parser"], raw),
                                "asof": req["params"].get("asof"), "vintage": st["vintage"]}))
        lines.append(dumps({"event": "stamp_complete" if st["status"] == "complete" else "stamp_incomplete",
                            "key": key, "kind": req["kind"], "attempt": st["attempt"], "pages": len(st["pages"]),
                            "asof": req["params"].get("asof"), "vintage": st["vintage"], "error": st["error"]}))
        return lines

    @classmethod
    def read(cls, directory, expected_sha256: str | None = None) -> "Store":
        d = Path(directory)
        data = (d / "ledger.jsonl").read_bytes()
        if expected_sha256 is not None and sha256_bytes(data) != expected_sha256:
            raise SealError("snapshot ledger sha256 differs from the sealed value")
        store, pages = cls(), {}
        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue   # the ledger of a snapshot that sealed no new request (a later holdout count)
            rec = json.loads(line)
            ev = rec.pop("event")
            if ev == "request":
                store.req[rec["key"]] = rec
            elif ev == "page":
                raw = gzip.decompress((d / rec["file"]).read_bytes())
                if sha256_bytes(raw) != rec["sha256"] or len(raw) != rec["bytes"]:
                    raise SealError(f"page {rec['file']}: sha256 or length mismatch")
                pages.setdefault((rec["key"], rec["attempt"]), []).append(raw)
                store.page_norm.setdefault((rec["key"], rec["attempt"]), []).append(rec.get("normalized_sha256"))
            else:
                if rec["key"] in store.state:
                    store.history.setdefault(rec["key"], []).append(store.state[rec["key"]])
                store.state[rec["key"]] = {"status": "complete" if ev == "stamp_complete" else "incomplete",
                                           "pages": pages.get((rec["key"], rec["attempt"]), []),
                                           "vintage": rec["vintage"], "attempt": rec["attempt"], "error": rec["error"]}
        return store
