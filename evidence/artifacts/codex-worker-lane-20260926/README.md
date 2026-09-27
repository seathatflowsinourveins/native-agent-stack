# Codex worker lane: dry run, rehearsals and probes (2026-09-26)

These are the retained outputs behind [the decision](../../../docs/decisions/2026-09-26-codex-worker-lane.md). The
lane itself lives in `tools/adoption/apply_codex_lane.py`, `tools/adoption/prove_codex_lane.py`,
`adoption/templates/codex.AGENTS.template.md` and `adoption/templates/codex.stack-worker.config.toml`.

**Where and with what.** The NativeStack WSL2 workstation, 2026-09-26 UTC: codex-cli 0.157.1, rtk 0.50.0, npm
context-mode 1.0.169 (`start.mjs` sha256 `0324441841b2…`). Paths are masked: `~` is the home directory, `$SCRATCH` a
private scratch directory, `<uuid>` an installation id.

**What was not done.** The lane was not applied to the host. The retained before-and-after hashes and mtimes cover
the Codex home's `config.toml`, `AGENTS.md`, `RTK.md` and `hooks.json` in the dry run and live rehearsal, and the
Claude home's `settings.json` and `plugins/installed_plugins.json` in the live rehearsal. Those enumerated files
were unchanged; the snapshots do not cover every file under either home. No credential store was opened, copied
or linked. The live workers ran with the host's own Codex home and signed in natively.

## Records

| File | Evidence class | What it shows |
| --- | --- | --- |
| [`host-dry-run.txt`](host-dry-run.txt) | local integration, on the real Codex home | The dry run with the final script (22:53Z): all ten preconditions pass, with no `codex` process running at that moment; an earlier run at 22:20Z had warned about two peer processes. Every planned key and the host step's three tables are listed. The rehearsal on private copies passes, and the output gives the two hashes and the worker command line. The four enumerated Codex configuration files are unchanged. |
| [`host-prove-before-apply.txt`](host-prove-before-apply.txt) | local integration, on the real Codex home | Before any apply: 0 top-rule lines, RTK text not inline, and context-mode bound to the plugin cache from `/` and to the checkout from the checkout (2 pass, 5 fail). `rtk git show` returns 8,248 of 21,300 bytes, while native `git show` is exact. |
| [`rehearsal-cycle.txt`](rehearsal-cycle.txt) | local integration, on scratch copies | Dry run, then apply without the hashes (exit 2), apply, a second apply ("already in place"), rollback (`config.toml` and `AGENTS.md` byte-identical, profile removed), and a second rollback ("already"). |
| [`rehearsal-static.txt`](rehearsal-static.txt) | local integration, on scratch copies | Prove before apply fails (2 of 7); after apply it passes 7 of 7. A scratch project stands in for the main checkout after the host step. |
| [`live-rehearsal.json`](live-rehearsal.json) | local integration with real model calls; not host acceptance | The post-apply state given as `-c` overrides on the real home: two concurrent workers each bound to their own directory; `memory_query` completed with the profile's keys and was refused without them; the rtk worker (block as a project `AGENTS.md`). The first rtk run read the blob through `ctx_execute`, so the check failed. The rerun names the shell tool and gets `rtk git status --short` plus a byte-exact `rtk proxy git show HEAD:big.txt`. Usage per run, not summed. |
| [`writer-probes.txt`](writer-probes.txt) | local integration against the pinned binary | `config/batchWrite`: a stale `expectedVersion` gives `configVersionConflict`; comments and integers are kept; an unknown key under `mcp_servers.<id>` is accepted; a wrong type is refused. Deleting a nested leaf leaves an empty header, and deleting the table the write created restores the file byte for byte. |
| [`tool-annotations.json`](tool-annotations.json) | local integration (Codex's own `mcpServerStatus/list`) and source | ai-memory and Headroom declare no annotations, and SocratiCode registers none, so all their tools need approval under Codex's `auto` mode. qmd and Serena's read tools declare `readOnlyHint`. codebase-memory did not finish its handshake from the scratch home. |
| [`prompt-input-effort.json`](prompt-input-effort.json) | local integration | `ultra` gives "Proactive multi-agent delegation is active"; the profile's `max` gives "Do not spawn sub-agents unless ...". |
| [`model-catalog-efforts.txt`](model-catalog-efforts.txt) | local integration (the binary's bundled catalog) | `gpt-6-astra` lists `multi_agent_reasoning_effort = "xhigh"`, so `ultra` sends `xhigh` in its requests, while `max` sends `max`. |
| [`precedence.txt`](precedence.txt) | local integration | In a trusted scratch project whose `.codex/config.toml` sets `ultra`, the profile's `max` loses (proactive delegation), and `-c model_reasoning_effort="max"` on the command line wins. This is why every worker launch pins the values. When trust was given only as a `-c` flag, the project value did not apply; the cause was not traced. |
| [`integration-test.txt`](integration-test.txt) | local integration | The opt-in real-app-server test: comment and integer kept, byte-exact rollback. |
| [`scripts/`](scripts/) | record | Every driver and probe as run (paths masked), including the one that built this directory. |

## How to repeat on another host

This host's results are not another host's acceptance. On a new host, run the dry run first; there it also rehearses
on copies of that host's own files. Then apply in a quiet window with the two hashes it prints, and run
`prove_codex_lane.py --live`. The `scripts/` records need their masked paths filled in. They show method, not
maintained tools.
