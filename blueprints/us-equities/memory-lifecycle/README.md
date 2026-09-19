# Disposable native memory lifecycle acceptance

Native **ai-memory 2.3.1** completed **31 MCP tool calls**, with **23 fixture checks passed** and **three expected protocol rejections**. This run used an empty disposable store, two fixture projects, no imported sessions, and no model or embedding provider. [The receipt](receipt.json) retains exact counts and hashes; [sanitized native responses](outcomes.json) retain bodies, hits and errors.

The same page path returned each project's own body; searches for the other project's unique term returned zero hits. An absent project, incompatible scope arguments and malformed expiry were rejected. A superseded page was absent from current search and available at its earlier ingestion-time instant. Deleting it removed both current and historical query results. The sibling project remained intact.

**Expiry is not immediate access revocation.** An already expired pinned page was hidden from ordinary search, but `include_expired` and an exact-path read returned it before the sweep. The preview preserved it; the explicit sweep reported `expired[0].deleted=true`, and subsequent retrieval returned zero hits. Its separate native `hard_deleted` counter was `0`; these counters are not interchangeable. The future-expiring page survived.

Use the installed native ELF executable and a new output directory on a Linux/WSL host with Python 3.11+ and Bubblewrap supporting unprivileged namespaces:

```sh
python3 blueprints/us-equities/memory-lifecycle/run.py \
  --binary "$AI_MEMORY_BINARY" --out "$NEW_PRIVATE_RUN_DIRECTORY"
```

The wrapper invokes these upstream commands inside the disposable namespace:

```sh
ai-memory --version
ai-memory --data-dir /run/data --config /run/config.toml serve \
  --transport stdio --no-watcher --workspace lifecycle --project alpha
```

The native stdio handshake advertises MCP `2025-03-26`, then `tools/list` and the recorded `tools/call` sequence. This is the upstream MCP server, driven by a small standard-library fixture client. The wrapper exits unsuccessfully on command failure, timeout, changed executable hash or failed fixture assertions. It rejects an existing output directory and an output below the selected binary's installation directory.

The namespace clears inherited environment variables and mounts no real home, account or memory directory. It exposes only the selected executable, system runtime and driver as read-only plus the fresh output directory. Network isolation exposes only loopback. The generated configuration explicitly selects `embedding_provider="none"`, disables history backfill, routing autowiring, watcher, maintenance and auto-improve scheduling, and configures no LLM. This explicit embedding opt-out matters because the inspected source otherwise supports best-effort local model loading. Raw protocol, server diagnostics, exact native argument arrays, namespace evidence and the disposable store stay in the private run directory.

The acceptance covers project routing, not tenant authorization; ingestion-time retrieval, not market valid-time data or historical ranking; search deletion, not secure erasure of Git checkpoints/backups. It does not exercise the active Codex/Claude hooks, service restart durability, a TTL crossing in real time, semantic retrieval quality or automated learning. No provider tokens or token savings were measured. macOS and Windows require separate native isolation and acceptance.

The source review pins the release commit separately from newer main. Main's scope-error classification has changed since the installed release: this native binary returned `-32603` for the three rejected inputs. The receipt preserves those actual errors.

To inspect the artifact checks without rerunning the server:

```sh
python3 blueprints/us-equities/memory-lifecycle/analyze.py \
  blueprints/us-equities/memory-lifecycle/outcomes.json
python3 -m unittest discover -s tests -p test_memory_lifecycle.py
```

The public response file replaces generated page IDs with consistent aliases and omits Git checkpoint IDs. The original private responses and requests remain hash-bound. Two earlier disposable observations (schema discovery and the first fixture run) are retained as history; the final fixture added namespace evidence and automatic assertion reporting.
