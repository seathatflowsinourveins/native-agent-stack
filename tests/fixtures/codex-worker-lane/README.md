# Codex worker lane: event fixtures

Item events from real `codex exec --json` runs of codex-cli 0.157.1 on the NativeStack WSL2 workstation, 2026-09-26.
Paths are masked (`/scratch/...`). `tests/test_codex_worker_lane.py` feeds them to `prove_codex_lane.py`'s verdicts.

| File | Run |
| --- | --- |
| `pwd-bound.events.json` | The cm-deep npm-live proof, worker `AN-cd-wP1`. context-mode ran as `node <npm pin>/start.mjs` with no `cwd`, the template's form, and `ctx_execute pwd` printed the worker's own directory. |
| `pwd-adversary.events.json` | The same proof's control, `CN-cd-wC1`. The bare `context-mode` CLI with no `cwd` followed another session's log, so `pwd` printed the adversary's directory. |
| `approval-items.json` | The approval rehearsal (`evidence/artifacts/codex-worker-lane-20260926/`). `memory_query` completed with the profile's ai-memory keys, and was refused without them. The completed call's result text is omitted. |
| `rtk-worker-items.json` | The rtk rehearsal's two command items. The output bytes were not kept; they were the fixture blob (sha256 recorded), measured byte-exact in the run. |
