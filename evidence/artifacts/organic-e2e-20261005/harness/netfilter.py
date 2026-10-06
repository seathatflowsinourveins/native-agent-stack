"""Round 6 of #786 (CC item task-ns2604-coop-20261006T155742Z, section 2 (B)): the only routes out of a trial's network
namespace.

Each trial runs in a network namespace of its own (bwrap --unshare-net, isolation.plan), so its only routes out are the
forwards isolation.NET_FORWARDS names, each with its reason. The pattern is Anthropic's sandbox-runtime
(anthropics/sandbox-runtime, tag v0.0.78, README.md):
- line 108: on Linux, bubblewrap with network namespace isolation;
- line 124: the sandboxed process's network namespace is removed, so all traffic goes through proxies on the host,
  reached over Unix sockets bound into the sandbox;
- line 365: an allowlist entry may be an IP literal;
- line 553: socat is the socket relay that bridges the proxies.

Inside the namespace, socat listens on each forward's usual loopback port and connects to a Unix socket bound in from
the trial's private folder (isolation.NET_PRELUDE). Outside, this process serves those sockets. sandbox-runtime's own
proxies filter by host and port, but OmniRoute v3.8.51 serves /v1 and /api on one port, so a path filter is the gap this
module fills:
- an HTTP filter: one request per connection. The request goes upstream with `Connection: close`, and no byte the
  client sends after its body is relayed. It is admitted only when its method and path match the forward's rules, its
  path is plain (no percent-encoding, dot segment or doubled slash), it asks for no Upgrade, and its body has one
  framing. ai-memory's hook routes must also name the trial's own scope.
- a CONNECT proxy: a tunnel only to the listed host:port pairs. TLS stays end to end.

Every decision goes to the access log: forward, method, path (never the query, a header or a body), decision, reason,
upstream status. Round 6e (GPT read of b2d44f73, P2): an admitted HTTP request gets its row at admission ("admitted",
with the connection's id), before the upstream is contacted, and its outcome row names the same connection. So a model
call is counted whatever its response carries, and also when the relay fails or the forwarder stops while it is in
flight (summarize).

    python3 -B netfilter.py serve --spec <spec.json>     prints READY once every socket listens; SIGTERM ends it
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_HEAD = 64 * 1024
# ai-memory's own cap on a /hook body (crates/ai-memory-cli/src/commands/serve.rs:53 at v2.5.2).
MAX_SCOPED_BODY = 10 * 1024 * 1024
TOKEN = re.compile(r"\A[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
# An origin-form path in plain form: no '%', '?', '#', '\', space or control character.
PLAIN_PATH = re.compile(r"\A/[A-Za-z0-9._~!$&'()*+,;=:@/-]*\Z")
HOP_BY_HOP = {"connection", "keep-alive", "proxy-connection", "te", "trailer", "upgrade", "proxy-authorization",
              "proxy-authenticate"}
DENIED_HEADER = b"X-Trial-Network: denied"
# The model-call routes on the gateway (OpenAI Responses and Chat Completions; Codex's compaction is under /v1/responses).
MODEL_CALL_PATHS = ("/v1/responses", "/v1/chat/completions", "/v1/completions")
# Response headers the access log keeps (no other header, no body).
RESPONSE_META = {"x-omniroute-request-id": "request_id", "x-omniroute-cache": "cache",
                 "x-omniroute-cache-hit": "cache_hit"}


class Denied(Exception):
    """A request the forward does not admit; the message is the logged reason."""


def parse_head(head: bytes) -> tuple[str, str, str, list[tuple[str, str]]]:
    """(method, target, version, headers) of a request head without its final CRLF CRLF."""
    lines = head.split(b"\r\n")
    try:
        request_line = lines[0].decode("ascii")
    except UnicodeDecodeError:
        raise Denied("request line not ASCII") from None
    parts = request_line.split(" ")
    if len(parts) != 3:
        raise Denied("malformed request line")
    method, target, version = parts
    if version not in ("HTTP/1.1", "HTTP/1.0"):
        raise Denied("unsupported HTTP version")
    if not TOKEN.match(method):
        raise Denied("malformed method")
    headers = []
    for raw in lines[1:]:
        if not raw:
            continue
        if raw[:1] in (b" ", b"\t"):
            raise Denied("folded header")
        name, sep, value = raw.partition(b":")
        try:
            name_text = name.decode("ascii")
        except UnicodeDecodeError:
            raise Denied("header name not ASCII") from None
        if not sep or not TOKEN.match(name_text):
            raise Denied("malformed header")
        headers.append((name_text, value.decode("latin-1").strip()))
    return method, target, version, headers


def header_values(headers: list[tuple[str, str]], name: str) -> list[str]:
    return [value for key, value in headers if key.lower() == name]


def plain_target(target: str) -> tuple[str, str]:
    """(path, query) of an origin-form target whose path is plain; Denied otherwise."""
    if not target.startswith("/"):
        raise Denied("request target not in origin form")
    if "#" in target:
        raise Denied("fragment in the request target")
    path, _, query = target.partition("?")
    if not PLAIN_PATH.match(path):
        raise Denied("path not in plain form")
    if "//" in path or any(segment in (".", "..") for segment in path.split("/")[1:]):
        raise Denied("dot segment or doubled slash")
    return path, query


def framing(headers: list[tuple[str, str]]) -> tuple[str, int]:
    """The request body's one framing: ("chunked", 0), ("length", n) or ("none", 0)."""
    codings, lengths = header_values(headers, "transfer-encoding"), header_values(headers, "content-length")
    if codings and lengths:
        raise Denied("both Transfer-Encoding and Content-Length")
    if codings:
        if len(codings) != 1 or codings[0].lower() != "chunked":
            raise Denied("a transfer coding other than chunked")
        return "chunked", 0
    if lengths:
        if len(set(lengths)) != 1 or not lengths[0].isdigit():
            raise Denied("malformed Content-Length")
        return "length", int(lengths[0])
    return "none", 0


def scope_ok(query: str, scope: dict) -> bool:
    """The query names exactly the trial's ai-memory scope (workspace and project, once each)."""
    try:
        values = parse_qs(query, keep_blank_values=True, strict_parsing=True) if query else {}
    except ValueError:
        return False
    return values.get("workspace") == [scope.get("workspace")] and values.get("project") == [scope.get("project")]


# Round 6d (GPT read of 50752dde, P1): the Qdrant operations socraticode 1.15.0 performs, and no other. Its dist calls
# getCollections, createCollection, getCollection, deleteCollection, createPayloadIndex, upsert, retrieve, delete
# (points), scroll and query (services/qdrant.js and services/symbol-graph-store.js), which @qdrant/js-client-rest
# 1.18.0 sends as the routes below (dist/types/openapi/generated_schema.d.ts). Grouped, batch, search, recommend,
# discover, snapshot, alias and cluster routes stay out. Each body is parsed, and every collection it names
# (with_lookup in both forms, lookup_from at any depth) must carry the trial's own prefix.
QDRANT_ROUTES = {"": {"GET", "PUT", "DELETE"}, "/index": {"PUT"}, "/points": {"PUT", "POST"},
                 "/points/delete": {"POST"}, "/points/scroll": {"POST"}, "/points/query": {"POST"}}
QDRANT_NAME = re.compile(r"\A[A-Za-z0-9_-]+\Z")
MAX_QDRANT_BODY = 64 * 1024 * 1024


def judge_qdrant(prefix: str, method: str, path: str) -> dict:
    """The Qdrant rule a request matches: health, the collection list (filtered on the way back), or one of
    QDRANT_ROUTES on a collection of the trial's own prefix. Denied otherwise."""
    if path == "/healthz" and method == "GET":
        return {"name": "health"}
    if path == "/collections" and method == "GET":
        return {"name": "list", "rewrite": "qdrant-collections"}
    if not path.startswith("/collections/"):
        raise Denied("Qdrant route not admitted")
    name, _, rest = path[len("/collections/"):].partition("/")
    suffix = "/" + rest if rest else ""
    if not name.startswith(prefix) or not QDRANT_NAME.match(name) or len(name) == len(prefix):
        raise Denied("a collection outside the trial's own prefix")
    if suffix not in QDRANT_ROUTES:
        raise Denied("Qdrant operation not admitted (not one socraticode 1.15.0 uses)")
    if method not in QDRANT_ROUTES[suffix]:
        raise Denied(f"method {method} not admitted on this Qdrant operation")
    return {"name": "collection", "body": "qdrant-selectors" if method in ("POST", "PUT") else None}


def qdrant_selectors_ok(value, prefix: str) -> bool:
    """Every collection a Qdrant request body names carries the trial's prefix: with_lookup as a string or an object
    with collection, and lookup_from objects at any depth (prefetch, batch searches)."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "with_lookup":
                name = item if isinstance(item, str) else item.get("collection") if isinstance(item, dict) else None
                if not isinstance(name, str) or not name.startswith(prefix):
                    return False
            elif key == "lookup_from":
                name = item.get("collection") if isinstance(item, dict) else None
                if not isinstance(name, str) or not name.startswith(prefix):
                    return False
            if not qdrant_selectors_ok(item, prefix):
                return False
    elif isinstance(value, list):
        return all(qdrant_selectors_ok(item, prefix) for item in value)
    return True


def filter_collection_list(body: bytes, prefix: str) -> bytes:
    """Round 6d (P2): GET /collections answered with only the receiving trial's own collection names; the envelope
    (status, time, result) is kept."""
    data = json.loads(body)
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict) or not isinstance(result.get("collections"), list):
        raise ValueError("not a Qdrant collection list")
    result["collections"] = [c for c in result["collections"]
                             if isinstance(c, dict) and str(c.get("name", "")).startswith(prefix)]
    return json.dumps(data, separators=(",", ":")).encode()


def judge(forward: dict, scope: dict, method: str, target: str, headers: list[tuple[str, str]]) -> dict:
    """The rule an HTTP request matches; Denied when none admits it. Pure: the tests call it with no network."""
    if method in ("CONNECT", "TRACE"):
        raise Denied(f"{method} on an HTTP forward")
    if header_values(headers, "upgrade"):
        raise Denied("Upgrade requested")
    path, query = plain_target(target)
    framing(headers)
    if forward.get("qdrant_prefix"):
        return judge_qdrant(forward["qdrant_prefix"], method, path)
    for rule in forward["rules"]:
        if path == rule.get("exact") or ("prefix" in rule and path.startswith(rule["prefix"])):
            if method not in rule["methods"]:
                raise Denied(f"method {method} not admitted on this path")
            if rule.get("scope") == "query" and not scope_ok(query, scope):
                raise Denied("the query names another ai-memory scope")
            return rule
    raise Denied("path not admitted")


def batch_ok(body: bytes, scope: dict) -> bool:
    """ai-memory's POST /hook/batch body, a JSON array of {url, body} (crates/ai-memory-cli/src/commands/hook_spool.rs
    batch_payload at v2.5.2): every item is a /hook event of the trial's own scope."""
    try:
        items = json.loads(body)
    except ValueError:
        return False
    if not isinstance(items, list) or not items:
        return False
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            return False
        parts = urlsplit(item["url"])
        if not parts.path.endswith("/hook") or not scope_ok(parts.query, scope):
            return False
    return True


def connect_target(target: str, allow: list) -> tuple[str, int]:
    """(host, port) of a CONNECT target the forward lists; Denied otherwise."""
    host, sep, port = target.rpartition(":")
    if not sep or not port.isdigit() or not host:
        raise Denied("malformed CONNECT target")
    pair = [host.lower(), int(port)]
    if pair not in [[h.lower(), int(p)] for h, p in allow]:
        raise Denied("host not on the forward's list")
    return pair[0], pair[1]


async def _respond(writer: asyncio.StreamWriter, status: int, reason: str) -> None:
    body = f"{status} {reason}\n".encode()
    writer.write(f"HTTP/1.1 {status} {reason}\r\n".encode() + DENIED_HEADER + b"\r\nContent-Type: text/plain\r\n"
                 + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
    try:
        await writer.drain()
    except ConnectionError:
        pass


async def _copy_exact(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, count: int) -> None:
    while count > 0:
        data = await reader.read(min(count, 65536))
        if not data:
            raise ConnectionError("the client closed inside its body")
        writer.write(data)
        await writer.drain()
        count -= len(data)


async def _copy_chunked(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    while True:
        line = await reader.readuntil(b"\r\n")
        writer.write(line)
        size = int(line.split(b";", 1)[0].strip() or b"x", 16)
        if size == 0:
            while True:
                trailer = await reader.readuntil(b"\r\n")
                writer.write(trailer)
                if trailer == b"\r\n":
                    await writer.drain()
                    return
        await _copy_exact(reader, writer, size + 2)


async def _pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int:
    total = 0
    while True:
        data = await reader.read(65536)
        if not data:
            return total
        writer.write(data)
        await writer.drain()
        total += len(data)


def _close(*writers: asyncio.StreamWriter) -> None:
    for writer in writers:
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


class Filter:
    def __init__(self, spec: dict):
        self.spec = spec
        self.scope = spec.get("scope") or {}
        fd = os.open(spec["access_log"], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        self.log = os.fdopen(fd, "a", buffering=1)
        self.admitted = 0

    def record(self, **row) -> None:
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **row}
        self.log.write(json.dumps(row, sort_keys=True) + "\n")

    def admit(self, name: str, method: str, path: str) -> str:
        """The admission row of one HTTP request, written before anything is forwarded; returns the connection's id
        (this forwarder's pid and a counter, so ids stay distinct when a log is appended to)."""
        self.admitted += 1
        conn = f"{os.getpid()}-{self.admitted}"
        self.record(forward=name, method=method, path=path, decision="admitted", conn=conn)
        return conn

    async def handle(self, name: str, forward: dict, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        seen: dict = {}   # the admitted request of this connection (conn, method, path), for a failure's row
        try:
            if forward["kind"] == "connect":
                await self.tunnel(name, forward, reader, writer)
            else:
                await self.http(name, forward, reader, writer, seen)
        except Exception as error:  # noqa: BLE001 - one connection's failure never ends the forwarder
            self.record(forward=name, decision="error", reason=type(error).__name__, **seen)
        finally:
            _close(writer)

    async def _head(self, reader: asyncio.StreamReader):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 60)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            return None
        except asyncio.LimitOverrunError:
            raise Denied("request head too long") from None
        return parse_head(head[:-4])

    async def http(self, name: str, forward: dict, reader, writer, seen: dict | None = None) -> None:
        method, path = "?", "?"
        try:
            parsed = await self._head(reader)
            if parsed is None:
                return
            method, target, version, headers = parsed
            path = target.split("?", 1)[0][:200]
            rule = judge(forward, self.scope, method, target, headers)
            mode, length = framing(headers)
            body = None
            if rule.get("scope") == "batch":
                if mode != "length" or length > MAX_SCOPED_BODY:
                    raise Denied("batch body without a bounded Content-Length")
                body = await reader.readexactly(length)
                if not batch_ok(body, self.scope):
                    raise Denied("a batch item names another ai-memory scope")
            if rule.get("body") == "qdrant-selectors" and mode != "none":
                if mode != "length" or length > MAX_QDRANT_BODY:
                    raise Denied("Qdrant body without a bounded Content-Length")
                body = await reader.readexactly(length)
                try:
                    parsed_body = json.loads(body) if body.strip() else {}
                except ValueError:
                    raise Denied("Qdrant body is not JSON") from None
                if not qdrant_selectors_ok(parsed_body, forward["qdrant_prefix"]):
                    raise Denied("the body names a collection outside the trial's own prefix")
        except Denied as denial:
            await _respond(writer, 403, "Forbidden")
            self.record(forward=name, method=method, path=path, decision="denied", reason=str(denial))
            return
        # Round 6e (GPT read of b2d44f73, P2): the request is admitted, so it is counted here, independently of the
        # response and its headers. Every later row of this connection carries the same id.
        conn = self.admit(name, method, path)
        if seen is not None:
            seen.update(conn=conn, method=method, path=path)
        host, port = forward["upstream"]
        try:
            up_reader, up_writer = await asyncio.wait_for(asyncio.open_connection(host, port, limit=4 * MAX_HEAD), 15)
        except (OSError, asyncio.TimeoutError):
            await _respond(writer, 502, "Bad Gateway")
            self.record(forward=name, method=method, path=path, decision="upstream-unreachable", conn=conn)
            return
        # Round 6e: an answer this filter rewrites must arrive uncompressed, so its request goes upstream without
        # Accept-Encoding. Qdrant 1.19.1 on this host compresses the listing when asked (measured 2026-10-06: gzip and
        # br), and Node's fetch, which @qdrant/js-client-rest 1.18.0 uses, asks by default.
        unsent = HOP_BY_HOP | ({"accept-encoding"} if rule.get("rewrite") else frozenset())
        kept = [(k, v) for k, v in headers if k.lower() not in unsent]
        up_writer.write(f"{method} {target} {version}\r\n".encode("ascii")
                        + b"".join(f"{k}: {v}\r\n".encode("latin-1") for k, v in kept) + b"Connection: close\r\n\r\n")

        async def request_body() -> None:
            if body is not None:
                up_writer.write(body)
                await up_writer.drain()
            elif mode == "length":
                await _copy_exact(reader, up_writer, length)
            elif mode == "chunked":
                await _copy_chunked(reader, up_writer)
            else:
                await up_writer.drain()

        status, meta = None, {}
        sender = asyncio.ensure_future(request_body())
        try:
            head = await up_reader.readuntil(b"\r\n\r\n")
            parts = head.split(b"\r\n", 1)[0].split(b" ", 2)
            status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            # The gateway's own call id and cache headers (OmniRoute v3.8.51 src/shared/constants/headers.ts:
            # X-OmniRoute-Request-Id, X-OmniRoute-Cache, X-OmniRoute-Cache-Hit): the collector later reads the call
            # log only for ids this trial's own responses carried.
            for line in head.split(b"\r\n")[1:]:
                key, _, value = line.partition(b":")
                key_text = key.decode("latin-1").strip().lower()
                if key_text in RESPONSE_META:
                    meta[RESPONSE_META[key_text]] = value.decode("latin-1").strip()[:120]
            if rule.get("rewrite") == "qdrant-collections":
                await self._rewrite_listing(head, up_reader, writer, forward["qdrant_prefix"])
            else:
                writer.write(head)
                await _pump(up_reader, writer)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            pass
        finally:
            if not sender.done():
                sender.cancel()
            _close(up_writer)
        self.record(forward=name, method=method, path=path, decision="allowed", status=status, conn=conn, **meta)

    async def _rewrite_listing(self, head: bytes, up_reader, writer, prefix: str) -> None:
        """Read the whole upstream response (Content-Length, chunked or until close), filter its collection names to
        the trial's prefix, and answer with the same status and a recomputed Content-Length. An answer that arrives
        compressed although none was asked for cannot be filtered: it is refused with 502, never passed through."""
        lines = head[:-4].split(b"\r\n")
        headers = [line.partition(b":") for line in lines[1:]]
        lowered = {k.decode("latin-1").strip().lower(): v.decode("latin-1").strip() for k, _, v in headers}
        if lowered.get("content-encoding", "identity").lower() not in ("", "identity"):
            await _respond(writer, 502, "Bad Gateway")
            return
        if lowered.get("transfer-encoding", "").lower() == "chunked":
            body = b""
            while True:
                size = int((await up_reader.readuntil(b"\r\n")).split(b";", 1)[0].strip() or b"0", 16)
                if size == 0:
                    while (await up_reader.readuntil(b"\r\n")) != b"\r\n":
                        pass
                    break
                body += (await up_reader.readexactly(size + 2))[:-2]
        elif lowered.get("content-length", "").isdigit():
            body = await up_reader.readexactly(int(lowered["content-length"]))
        else:
            body = await up_reader.read()
        try:
            filtered = filter_collection_list(body, prefix)
        except ValueError:
            await _respond(writer, 502, "Bad Gateway")
            return
        keep = [lines[0]] + [line for line in lines[1:] if line.partition(b":")[0].strip().lower()
                             not in (b"content-length", b"transfer-encoding", b"connection")]
        writer.write(b"\r\n".join(keep) + f"\r\nContent-Length: {len(filtered)}\r\nConnection: close\r\n\r\n".encode()
                     + filtered)
        await writer.drain()

    async def tunnel(self, name: str, forward: dict, reader, writer) -> None:
        target = "?"
        try:
            parsed = await self._head(reader)
            if parsed is None:
                return
            method, target, _, _ = parsed
            if method != "CONNECT":
                raise Denied(f"{method} on the CONNECT proxy")
            host, port = connect_target(target, forward["allow"])
        except Denied as denial:
            await _respond(writer, 403, "Forbidden")
            self.record(forward=name, method="CONNECT", path=target[:200], decision="denied", reason=str(denial))
            return
        try:
            up_reader, up_writer = await asyncio.wait_for(asyncio.open_connection(host, port), 20)
        except (OSError, asyncio.TimeoutError):
            await _respond(writer, 502, "Bad Gateway")
            self.record(forward=name, method="CONNECT", path=f"{host}:{port}", decision="upstream-unreachable")
            return
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        up = asyncio.ensure_future(_pump(reader, up_writer))
        down = asyncio.ensure_future(_pump(up_reader, writer))
        await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
        for task in (up, down):
            if not task.done():
                task.cancel()
        _close(up_writer)
        self.record(forward=name, method="CONNECT", path=f"{host}:{port}", decision="allowed", status=200)


async def serve(spec: dict) -> None:
    filt = Filter(spec)
    servers = []
    for name, forward in spec["forwards"].items():
        socket_path = Path(forward["socket"])
        socket_path.unlink(missing_ok=True)

        def handler(reader, writer, _name=name, _forward=forward):
            return filt.handle(_name, _forward, reader, writer)

        servers.append(await asyncio.start_unix_server(handler, path=str(socket_path), limit=MAX_HEAD))
        os.chmod(socket_path, 0o600)
    print("READY", flush=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    for server in servers:
        server.close()


def summarize(access_log) -> dict:
    """Counts per forward and decision, the first denied requests (forward, method, path, reason), and the gateway
    forward's model calls.

    Round 6e (GPT read of b2d44f73, P2): a model call is counted from its admission row, so the count never depends on
    the response. gateway_model_requests is every admitted model call. gateway_request_ids holds the ids of the calls
    whose response carried one, and gateway_model_calls_without_id the other calls, each identifiable by its
    connection, time, method, path, outcome and status. A call with no outcome row (the forwarder stopped while it was
    in flight), one whose upstream was unreachable and one whose relay failed are calls without an id. An allowed model
    row with no admission row (a log from before round 6e) is counted the same way. An admission is not a second
    request: requests and by_forward count outcomes, and admitted counts the admissions."""
    out: dict = {"requests": 0, "admitted": 0, "by_forward": {}, "denied": [], "gateway_request_ids": [],
                 "gateway_model_requests": 0, "gateway_model_calls_without_id": [], "gateway_cache_hits": 0,
                 "unparsed_rows": 0}
    try:
        lines = Path(access_log).read_text().splitlines()
    except OSError:
        # No log, no count: the admitted model calls are unknown, never zero.
        return {**out, "gateway_model_requests": None, "gateway_model_calls_without_id": None, "unparsed_rows": None,
                "log": "missing"}
    calls: dict = {}   # the gateway forward's model calls by connection, in admission order
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except ValueError:
            out["unparsed_rows"] += 1
            continue
        forward, decision, conn = row.get("forward") or "?", row.get("decision") or "?", row.get("conn")
        model_call = forward == "gateway" and str(row.get("path") or "").startswith(MODEL_CALL_PATHS)
        fresh = {"conn": conn, "at": row.get("at"), "method": row.get("method"), "path": row.get("path"),
                 "outcome": None, "status": None, "request_id": None}
        if decision == "admitted":
            out["admitted"] += 1
            if model_call:
                calls.setdefault(conn or f"line-{number}", fresh)
            continue
        out["requests"] += 1
        counts = out["by_forward"].setdefault(forward, {})
        counts[decision] = counts.get(decision, 0) + 1
        if decision == "denied" and len(out["denied"]) < 30:
            out["denied"].append({k: row.get(k) for k in ("forward", "method", "path", "reason")})
        if forward != "gateway":
            continue
        if conn in calls or (decision == "allowed" and model_call):
            # The outcome of a model call: the trial's required calls are these (each leaves a call-log row).
            call = calls.setdefault(conn or f"line-{number}", fresh)
            call.update(outcome=decision, status=row.get("status"), request_id=row.get("request_id") or call["request_id"])
        elif decision == "allowed" and row.get("request_id"):
            # Other /v1 reads, such as the model list, are kept apart.
            out.setdefault("gateway_other_request_ids", []).append(row["request_id"])
        if decision == "allowed" and (str(row.get("cache_hit") or "").lower() in ("true", "1", "hit")
                                      or str(row.get("cache") or "").upper() == "HIT"):
            out["gateway_cache_hits"] += 1
    out["gateway_model_requests"] = len(calls)
    out["gateway_request_ids"] = [call["request_id"] for call in calls.values() if call["request_id"]]
    out["gateway_model_calls_without_id"] = [{k: call[k] for k in ("conn", "at", "method", "path", "outcome", "status")}
                                             for call in calls.values() if not call["request_id"]]
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        asyncio.run(serve(json.loads(Path(args.spec).read_text())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
