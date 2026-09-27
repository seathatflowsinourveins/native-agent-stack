# Token stack cards, 2026-09-27 edition

Sanitized per-tool cards for 18 token-stack tools, the invoke-rate snapshot they
use, the returned-result records they cite and an index of their GPT-6 reviews.
[`docs/token-efficiency-stack.json`](../../../docs/token-efficiency-stack.json)
condenses 17 of these cards into its rows (`rows[].card`), and
`scripts/build_ecosystem.py` renders them in the explorer's token topic.
`gpt-tokenizer` has a card here but no row: the topic joins only
`manifests/stack.json` components, and gpt-tokenizer is pinned (3.4.0) in
`tools/token-report/token_manifest.py` instead. Its card records upstream
4.0.0, published 2026-08-16.

This is dated evidence from one source host. It is not a new host's acceptance,
an unchanged upstream test suite or a new provider run.

## Dates

| Item | Date (UTC) |
| --- | --- |
| E2E upstream-command runs behind the cards | 2026-09-26 |
| Returned results captured (host `nativestack-5975wx-20260925`, NativeStack WSL2, fixture commit `803bc351`) | 2026-09-26T22:53:19Z |
| Upstream latest-release reads (GitHub `releases/latest` API) | 2026-09-26 |
| Invoke-rate window | 2026-09-25T11:37:28Z to 2026-09-26T23:37:28Z |
| GPT-6 final-verdict verification receipts | 2026-09-26 to 2026-09-27T03:20:30Z |
| Bundle sanitized and topic edition written | 2026-09-27 |

## Files and evidence classes

| File | Contents | Evidence class |
| --- | --- | --- |
| `cards/<tool>.json` (18) and `cards/index.json` | The assembled cards, sanitized as described below; otherwise unchanged | Mixed. Each block names its class: upstream provenance, repository configuration review, local integration, exact artifact comparison, native counter, upstream estimate, model review |
| `returned-results-subset.json` | The 206 records the cards cite (each card's `records_shown` plus any record id named in its text), out of 711 | Local integration: upstream commands and checks run on the source host, with returned data retained |
| `invoke-by-tool.json` | Per-tool invoke counts by population | Local integration: transcript counts over the dated window |
| `gpt6-reviews.json` | Per-tool review and final verdicts, finding and resolution counts, run models, and the three verification receipts | Model review: judgment over retained sources, not execution |
| `tools/bundle.py`, `tools/condense.py` | The generators for this directory and for the topic edition | Local tooling |

In `returned-results-subset.json`, each record keeps its command, `exit`, status
and a summary of at most 600 characters. The full observation is omitted. It is
identified by its UTF-8 byte count and sha256: over the text for a string
observation, and over compact sorted JSON for an object observation. Attachment
bodies are identified by the sha256 the source recorded. `exit` is `null` where
the observation states no exit code (38 records, mostly MCP calls); `status`
still carries the outcome.

Figures are never summed across evidence classes, lanes or scopes. For example,
RTK's project snapshot is already included in its global snapshot, and exact
`o200k_base` comparisons and tool-reported counters use different units.

## Corrections carried by the topic rows

The cards are kept as assembled. The GPT-6 reviews reported 23 findings. Each
one was checked against its source, and the condensed rows record its status:

- 15 are addressed in the final card text (6) or resolved in the review's
  repair round (9).
- 5 are corrected in the row:
  - qmd, comparison 0 and its fidelity (2 findings): the "answer verified (PASS)" was refuted
    as wrong-document retrieval by `evidence/artifacts/token-e2e-codex-20260926/receipt.json`
    (`corrections_to_296`).
  - repomix, comparison 0: the "47 names" PASS is superseded. Records
    `repomix-08-mcp-grep-full` and `repomix-09-mcp-grep-compress` return 1 and 0
    matches for `status_body`.
  - jcodemunch-mcp: command roots use `$RR`.
  - mcporter: the population label is corrected.
- 2 keep the card's figure with the discrepancy named: ai-memory
  `records_total` (54 vs 48) and qmd `records_total` (31 vs 30).
- 1 is not carried: the stale ai-memory freshness text. The user's 2026-09-26
  hook trust is recorded in `evidence/artifacts/ai-memory-241-codex-capture-20260926/README.md`.

## Sanitization

The bundle reuses the placeholders from the returned-results assembly:

- `$HOME`: the home directory, including `~/` paths.
- `<scratch>`, `$SCRATCH`, `$RR` and `$WT`: the session scratchpad, its `rr`
  evidence root and the fixture worktree.
- `$SESSION_TMP`: the session temp root.
- `[redacted-session-id]` and `[redacted-uuid-N]` (or `[redacted-uuid]`):
  identifiers.
- `<user>`: the local account name.
- `redacted-email`: an e-mail address.

`session_id_sha`, which is derived from a session id, is dropped. Before any
file is written, `bundle.py` scans every output with `scripts/validate.py`'s
`PRIVATE_CONTENT` patterns, plus checks for session temp paths, e-mail
addresses, `"session_id` keys and `~/` paths. A match stops the run instead of
being rewritten.

## Reproduce

The inputs are private assembly outputs. They are identified here by name,
bytes and sha256:

| Input | Bytes | sha256 |
| --- | --- | --- |
| `agentsview.json` | 43291 | `ef29ba61eef7cf8fc1d2cd76a57eca24bf289c91252de9c8b4106febdb8656ba` |
| `ai-memory.json` | 54767 | `a1578299aa6d0e3ea8258f67983bc2e26c5157befdff1d07261b9e432b0ed35b` |
| `ast-grep.json` | 38630 | `eb82d130fa5223f03c354be42dc91d58d5c582ecdf286da30aaa172036be4d4e` |
| `ccusage.json` | 39845 | `b04607216e6dece094f8604973621162705b3ff7c6386371da7062c6b9583fa5` |
| `codebase-memory-mcp.json` | 53468 | `559d0bf7e49a2c889c834f1f0180af9b33d2c84e4b6e5e3a89aa01a226e0fac5` |
| `context-hub.json` | 35523 | `6537a5394e107f4692c1b885949237e7b545a734cf36c4a5382650ad352c88be` |
| `context-mode.json` | 45326 | `74c90b6762def8d08a65a1fc614a99eccab774f11dc52872649d95d414c6da2b` |
| `final-verdict-evidence.json` | 7058 | `152edd399928ecb437e873e3c0c7dfa55afafd118b82d18db58c59c8ded7b369` |
| `g5-g6-verification.json` | 9269 | `445e0f2c521ba8d85996d43d8e4c287c9663f489eb7c6c52ab0397ba12714f2a` |
| `gpt-tokenizer.json` | 43658 | `b1713d3e62681d6aaf018b332fe02bbb449cb5bbfc9232b0633fdc8909b401d2` |
| `headroom.json` | 47916 | `acb1721a7f39ea5e3f89cf1a15a765d25c5cb75455ec52739cad6925deaf5c07` |
| `index.json` | 2952 | `67320a754131ac05d0c88596f82bb3aa0a9480f3e386eac919767c3d912284c5` |
| `invoke_by_tool.json` | 19412 | `50fb0b39470c508c1d9f2d3761328aac45987f7bd1a338666906f22b0f08060e` |
| `jcodemunch-mcp.json` | 46331 | `a734a23d22ef5a4364a38e27a8a10606fceb529d50ae3d0a94c26a9f872f37c6` |
| `markitdown.json` | 38893 | `f923ec4c604273774c1fa0498d5c35e90b7c0fcafcdfa8a23eef994d6ec656db` |
| `mcporter.json` | 41428 | `ee47a5acb6f5a9a1e18f31f356f8be69d07a5193ebbe8f9cf87db48ae6982b51` |
| `qmd.json` | 51804 | `80876917f4ffa2be2c0406fa5743ae3f381a0cce05e7ff4b73c87565ee285f6b` |
| `repomix.json` | 39783 | `bdac44102896949cb67f297926e6097717a157113a561e325ef0223d0eb7864a` |
| `returned-results.json` | 2062479 | `7688ae58c8e13e33178bfab1fa0d959fcfee1a2b54cb3bd20e2e6f263360224f` |
| `rtk.json` | 48257 | `5350af07e98d186c2db62aecd2214104090d8e4d57480af522472376097ca9f0` |
| `serena.json` | 41441 | `6346186f6d695dbcd284ab7b9572009c1ba92af55dbf8da02d83526fc5820b06` |
| `socraticode.json` | 49270 | `27ebd9957acdb12c319e58a27cff80f6ff3ce4cf59bfde8e50481e20a86b4e60` |
| `toon.json` | 41824 | `ab5703fed150da4f3ae9574f8df071e46cd4f3293f4f28fce0240f9907e6576f` |
| `verdict-evidence.json` | 6804 | `0612d365d52c388ba44372ba40a21f16c933aa15b2d979b737784dae2ef2eae9` |

```sh
python3 evidence/artifacts/token-stack-cards-20260927/tools/bundle.py \
  --cards CARDS_DIR --invoke invoke_by_tool.json --returned-results returned-results.json \
  --verification verdict-evidence.json --verification final-verdict-evidence.json \
  --verification g5-g6-verification.json --repo-root . \
  --out evidence/artifacts/token-stack-cards-20260927
python3 evidence/artifacts/token-stack-cards-20260927/tools/condense.py --repo-root .
```

Both commands are deterministic for fixed inputs, and rerunning `condense.py` on
its own output reproduces the same bytes. Pins are not copied into the rows:
`scripts/build_ecosystem.py` joins `manifests/stack.json` when the page is
built. `card.recorded_pin` records the pin a card describes, and a different
stack pin renders a drift note instead of editing the card.
