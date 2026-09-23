# Gap wave 2 (2026-09-23): foundation / mcp-surfaces

Gap list: crosswalk at main 92bb279 (PR #85), layer `mcp-surfaces`, indices 0-10 and 12.
Branch `claude/g2-mcp-surfaces-20260923`, base 41d39b3. `results.json` is generated from the receipts by
`blueprints/gap-wave2-20260923/foundation__mcp-surfaces/make_results.py`. `verify_receipts.py` (fix round 3) recomputes
each gap text's sha256 from the unit list and checks it, the required receipt fields, cited-file hashes, preregistration
timestamps and results.json equality; its output is `raw/verify-receipts.txt`.

| Gap | Outcome | Receipt | One line |
|---|---|---|---|
| 0 | settled | `0-retained-bridge-rerun.json` | The retained mcporter/Inspector calls were repeated on this host with the installed binaries and the unmodified host config. |
| 1 | settled | `1-mcporter-0.14.0-matched.json` | mcporter 0.14.0 matched 0.13.13 on all 13 calls and on every lifecycle stage. |
| 2 | settled | `2-owned-daemon-lifecycle-stages.json` | Persistence, restart and cleanup pass. Recovery from stale metadata is established as not automatic: the next call is refused by design. |
| 3 | settled | `3-retained-operation-ids-defined.json` | The four retained operation ids are published with their commands and were re-run. |
| 4 | advanced | `4-inspector-tools-list-local-servers.json` | Inspector tools/list passed on 5 local servers and on agent-lab's ai-memory and SocratiCode. Plugin, hooks and Desktop remain. |
| 5 | settled | `5-project-config-without-registry.json` | claude and codex list servers from project files alone, with no network and fresh client homes. |
| 6 | settled | `6-alternative-bridge-comparison.json` | Head-to-head with @wong2/mcp-cli 2.0.0, every list and call op run x3. Calls: mcporter 8/8, Inspector 8/8, wong2 7/8. Complete lists: 5/5, 5/5, 4/5. wong2 lists only interactively and crashes on jcodemunch's unimplemented resources/templates/list. |
| 7 | settled | `7-awesome-mcp-servers-recovery-review.json` | All five pinned awesome-mcp-servers entries selected by the section rule were reviewed against the recovery gap. 1mcp is keep-but-compare; mcp-hub, mcpproxy-go and chrishayuk/mcp-cli are rejected; wong2/mcp-cli was the executed CLI alternative. |
| 8 | advanced | `8-inspector-project-file-scope.json` | Inspector project scope is explicit (`--config`), not discovered from cwd. Plugin, hooks and Desktop remain. |
| 9 | settled | `9-induced-stale-metadata-and-startup-timeout.json` | Stale metadata needs a manual step on both versions. A startup timeout (held lock) fails while held, then the first call after the holder exits on its own recovers with no step. |
| 10 | settled | `10-disposable-daemon-lifecycle-fixture.json` | Enforced isolation (shared socket path ENOENT; owned control connects), persistence, scoped cleanup and changed-root recovery. A removed plain keep-alive entry keeps running until `daemon stop`. |
| 12 | settled | `12-matched-set-three-bridges.json` | Same 13-op set x3: 13/13 under 0.13.13, 13/13 under 0.14.0, 11/13 under the reviewed registry alternative (its list ops run interactively and scrolled). |

## Review and fix round

Round-1 independent review: `raw/review-codex-round1.txt` (one `codex exec --sandbox read-only --ephemeral`, gpt-6-astra,
received 04:35:13Z). It had 5 findings:

1. Gap 10 isolation probe could not detect contact (high).
2. Gap 12 wong2 list rows were synthetic (high).
3. Gap 9 lock holder killed by the harness (medium).
4. Gap 1 install/diff claims not retained as raw (medium).
5. Gap 0 README byte numbers not retained as raw (low).

It also said lifecycle `started` stamps were taken after the actions. Fix round 1 was preregistered at 04:36:13Z (last
addendum) and made these changes:

- Every bridge and lifecycle run was repeated under `enforce.py`: `unshare -rnm` with an empty tmpfs over `$HOME/.mcporter`
  and a fresh network namespace. A pathname AF_UNIX probe of the shared socket returns ENOENT, while the same probe
  connects to each owned daemon socket (the owned control).
- wong2 interactive listing was executed x3 for all 5 servers.
- The lock holder now has a fixed lifetime and exits on its own.
- `started` timestamps are now captured before each stage's actions.
- `raw/1-install-identity.txt` and `raw/0-readme-measure.txt` were added.
- Round-1 raw files moved to `raw/round1/`; they are not cited for the no-contact claim.
- `sanitize_raw.py` replaced host paths with `$HOME` and UUIDs with per-file `uuid-N` tokens, because the publication
  validator rejects both. This also changed one `/home/...` path string in the committed `preregistrations.json` to
  `$HOME`. The written_at values and texts are otherwise unchanged; see git history.

Round-2 review: `raw/review-codex-round2.txt` (received 04:59:39Z). It found all round-1 findings resolved and raised
two new ones. First, the wong2 listing counted unseen autocomplete choices as missing (high). Second, wong2 listing
time included harness waits (medium). Fix round 2 was preregistered at 04:59:55Z. The pty driver now scrolls with
Down x45 and compares the collected tool-name set with Inspector's tools/list names. It also records spawn-to-ready
time separately from harness time. The result: wong2 lists every tool for 4 of 5 servers, and the jcodemunch crash
is explained in `raw/6-jcodemunch-method-probe.txt`. The fix-round-1 wong2 file is kept as
`raw/round1/wong2-interactive-list.fix1.json`.

Round-3 check: `raw/review-codex-round3.txt` (05:05:17Z). Both round-2 findings are resolved and there are no new
findings.

Round-4 review (independent Opus, relayed by the coordinator; `raw/review-opus-round4.json`) raised five minor findings.
Fix round 3 was preregistered at 13:07:02Z, before the new clone:

- Gap 7: chrishayuk/mcp-cli (README line 4527) was selected but never reviewed. It is now cloned at 6d806241 (8.7 MB
  download) and reviewed with verbatim citations. Disposition: rejected, because each command starts its servers in
  process and closes them on exit, and its declared reconnect defaults have no reference in `src/`. The receipt's
  disposition arm now lists all five entries, and a coverage check asserts that every selected entry was reviewed.
- Verification: `verify_receipts.py` was added (see above). It was mutation-tested: an edited gap text and an
  edited results.json outcome each made it fail.
- Slugs: `sanitize_raw.py` now rewrites the dash-encoded `home-<user>-` project slug to `home-$USER-`, so both
  `bridges-matched.json` files and receipt 3 no longer contain the host username.
- Gap 5: the receipt now discloses that the approved Claude arm tried to connect to the live ai-memory URL
  hard-coded in agent-lab's `.mcp.json`. The no-network namespace blocked the attempt (ENETUNREACH).
- Gap 1: the lifecycle comparison now gives each version's stage fields plus an `identical_between_versions` flag
  (`lifecycle_per_stage`).

No outcome changed in fix round 3.

Outcome changes: gap 6 moved from advanced to settled, and gap 12 stayed settled. Both were re-decided under the
preregistered criteria once the list arms were executed. Gap 10 stayed settled on the enforced run.

## How it was run

- Preregistration: `preregistrations.json` was committed at 03:54:03Z before any check ran. Three added arms have dated
  addenda that were committed before those arms ran: 04:14:45Z (startup-timeout arm, gap 9), 04:23:01Z (Claude
  approved-project arm, gap 5) and 04:24:12Z (unmodified-config namespace arm, gaps 0/3/4/8).
- `iso.py` is an owned fixture. It gives each run a temp HOME/XDG and `MCPORTER_DAEMON_DIR` on a short path under
  `$HOME/.cache/gap-wave2-20260923/mcp-surfaces/d/`, because Unix socket paths are limited to 108 bytes and a long
  path gives `connect EINVAL`. It also starts an owned `ai-memory serve --data-dir <temp>` and an owned Qdrant 1.19.1 on
  free loopback ports. `enforce.py` (fix round 1) wraps the bridge, lifecycle and wong2 runs in `unshare -rnm` with an
  empty tmpfs over `$HOME/.mcporter`, and records the outside stat() of the shared daemon before and after in `*.enforce.json`.
- `ns_exact.py` runs the unmodified `$HOME/codex-ecosystem/config/mcporter.json` and agent-lab `.mcp.json` inside
  `unshare -rnm --fork --kill-child`. There, `$HOME` and `/mnt/c` are read-only, `$HOME/.mcporter` is an empty tmpfs, loopback starts empty, and owned
  ai-memory and Qdrant listen on the configured ports 49374 and 16333. A connect probe before they start is refused on
  49374, 16333 and 8231, which shows that a live listener would have been detected.
- `run_bridges.py`: 13 retained operations x 3 reps x 5 bridges (installed 0.13.13, fresh 0.13.13, 0.14.0, Inspector
  2.7.0, @wong2/mcp-cli 2.0.0).
- `run_lifecycle.py`: owned-daemon stages on 0.13.13 and 0.14.0. The server pid comes from `ctx_execute` printing
  `process.ppid`. An ephemeral twin is the negative control and shows 3 pids where keep-alive shows 1. The
  scoped-cleanup stage detected a surviving plain keep-alive server, which shows the /proc scan can detect leftovers.
- `run_mcp_list.sh`: `claude mcp list` / `codex mcp list --json` in agent-lab and in scratch projects inside a no-network,
  read-only namespace with temp client homes.
- `source_review.py`: pinned clones, with cited lines copied verbatim into `raw/7-source-review.json`.

## Downloads (network)

npm: mcporter@0.13.13 and mcporter@0.14.0 (41 packages each, about 67 MB per prefix), @wong2/mcp-cli@2.0.0 (134
packages, 35 MB). All were installed through `ecosystem-bounded-run` into `$HOME/.cache/gap-wave2-20260923/mcp-surfaces/`.
git shallow clones: punkpeye/awesome-mcp-servers, 1mcp-app/agent (22 MB), ni-c/mcp-hub (4.6 MB),
smart-mcp-proxy/mcpproxy-go (147 MB) and wong2/mcp-cli. No PATH binary, ~/.config file, live store or service was changed.

## Limits shared by the receipts

- The live ai-memory store, live Qdrant index and shared mcporter daemon were deliberately not contacted. Every
  store-backed result, such as memory counts of 0 or SocratiCode's "No index found", comes from an owned empty
  instance.
- `/tmp` was not isolated. SocratiCode read host watcher state ("watched by another process").
- The Serena wrapper writes logs under `$HOME/.local/share/codex-ecosystem/context/serena-home` whatever HOME is set
  to, so it fails under the read-only mount. It was not retried with write access.
- The codebase-memory-mcp 0.11.0 binary used for fresh-static-graph and fresh-static-callees is the one kept at
  `tools/codebase-memory-mcp-0.11.0.removed-20260921`, which is no longer in the host config. It indexed an owned copy
  of one file. Project names derived from that path had the host username in a `home-<user>-` prefix; fix round 3
  rewrote it to `home-$USER-`.
- No Claude model call or multi-agent run was made. Independent review used one `codex exec --sandbox read-only
  --ephemeral` call per round (`raw/review-codex-round*.txt`). The round-4 review was an Opus review run by the
  coordinator, not by this unit.
