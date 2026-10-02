# Status: work in progress, nothing has run (2026-10-02)

This folder is the source build for the memory head-to-head of the new WSL. No memory system was installed or run for
it, no question was answered or judged, and it is not yet a pull request.

## What is here

- `h2h/types.py`: the fixed adapter interface (`start`, `reset`, `ingest`, `retrieve`, `stop`).
- `h2h/adapters/<system>.py` with `<system>.md`: one adapter per system, written from the system's own documented
  ingestion and recall interface at a pinned release, with the upstream file and line for every endpoint and
  parameter. Systems: ai-memory 2.5.2, Hindsight 0.10.2, cognee 1.6.2, OpenViking 0.4.22, agentmemory 0.9.29, MemPalace,
  memsearch. Controls: `bm25`, `none`.
- `h2h/{data,protocol,score,stats,run}.py`: a self-written runner around LongMemEval's official answer and judge
  prompts.
- `tests/`: 208 offline tests (HTTP, subprocesses and sockets stubbed). Two modules import `httpx`; run them with it
  installed, for example `uv run --no-project --with httpx==0.28.1 python -B -m unittest discover -s tests`.

Each part was written by a GPT-6.1 Sol builder from one brief; the coordinator ran the tests and has not yet reviewed
the code line by line.

## Decision for the scored run

The scored path is the upstream benchmark harness, not the runner in this folder: vectorize-io/agent-memory-benchmark
at `03c1d0f1d27da63034f0931121c858faba512383`, unchanged, with its own providers where it ships one (Hindsight,
cognee, Mem0, `bm25`, `none`) and one shim provider that maps its `MemoryProvider` interface (`initialize`, `prepare`,
`ingest`, `retrieve`, `cleanup`) onto this folder's adapter interface for the other systems. The repository's rule is
to measure with upstream harnesses. The self-written runner stays as reference for the shim and for the paired
statistics until the shim exists; it is not evidence.

## Owed before anything runs

1. The shim provider and the sampling of the harness's LongMemEval data to the 60 preregistered question ids.
2. A line-by-line review of each adapter against its upstream citations (cross-family: Claude reads what GPT built).
3. The frozen preregistration (bounded design: gates, 60 questions, screens before accuracy, one winner).
4. The Hindsight image's own home-directory path appears in its adapter and document; the repository's publication
   patterns flag any home-directory path, so these need a neutral spelling before a pull request.
5. A first live run of each adapter against its installed system on the new distribution.
