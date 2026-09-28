# OmniRoute routing convergence: receipts (2026-09-28)

These files back the convergence record
[`blueprints/convergence-practice/omniroute-routing-20260928/experiment.json`](../../../blueprints/convergence-practice/omniroute-routing-20260928/experiment.json).
The subject is how GPT-6 Codex lanes reach a pool of six ChatGPT subscription accounts through OmniRoute on the
NativeStack WSL2 workstation (`nativestack-5975wx-20260925`):
- 20128, the shared gateway, runs build `dd6e9607e` (release/v3.8.51 `a58000c7` with PRs #14904 and #13788; see
  [the account-pool receipts](../omniroute-gateway-20260927/README.md));
- 20129, the full-compression lane, is chained to 20128 through the `sharedgw` provider node.

Account identities are withheld. No file here names an account, connection, provider node id or email. The byte copy
`ab-requirements.md` keeps, as written, the local labels of two peer Claude sessions and one Codex home directory
name. These are not account, credential or path data. `decisions.json` leaves peer session names out only because it
is a decision extract.

## Files

| File | Kind | From (private name) | What it holds |
| --- | --- | --- | --- |
| `adjudication.json` | derived | the record workflow's journal | All 51 adjudicated items (P1-P23, ADD-P1P7, ADD-LIVE, R1-R8, E1-E9, U1-U4, M1-M5) in three groups, with counts. Compact JSON. |
| `adjudication-rule.json` | authored copy | the record workflow's script | The adjudication stage's item schema, prompt, groups and shared inputs. |
| `decisions.json` | authored extract | `TRACKER.md` | Decisions with UTC times, failed or withdrawn conditions, interruptions and the named open unknowns. `TRACKER.md` itself is not published. |
| `route-landscape-catalog.json` | substituted copy | `route-landscape-catalog.json` | Claude route-landscape's catalog P1-P22, risk register, exclusions, unknowns and the 2026-09-28 addendum, including the withdrawn 8.4% finding. |
| `route-job1.prompt.txt`, `route-job1.schema.json` | copies | `route-gpt6/job1.prompt.txt`, `job1.schema.json` | The frozen question and output schema of GPT-6 JOB 1 (independent answer). |
| `route-job2.prompt.txt` | substituted copy | `route-gpt6/job2.prompt.txt` | The refutation prompt of GPT-6 JOB 2, which embeds the catalog without the withdrawn entry. |
| `route-job2.schema.json` | copy | `route-gpt6/job2.schema.json` | JOB 2's output schema. |
| `route-job1.last.json`, `route-job2.last.json` | copies | `route-gpt6/gpt6/route-job{1,2}/last.json` | The two GPT-6 answers. They cite only public URLs. |
| `route-gpt6-runs.json` | derived | `route-job{1,2}.result.json`, each job's `events.jsonl`, `exit` file and `commands.log` | Model, effort, Codex version, times, exit, usage, event counts, input and output hashes, the schema check and the masked command log. |
| `route-mapper-final.json` | copy | `route-mapper-final.json` | Claude route-mapper's inventory of OmniRoute routing mechanisms, aggregate 24 h metrics for 20128 and 20129, the P1-P23 mapping and open items. |
| `route-mapper-resume-parts.md` | split copy, first part | `route-mapper-resume-parts.md`, its first 6,503 bytes | The version the adjudication read: route-mapper's check 1 (expiry-first scope), check 2 (quota window), part 1 (interim cutoff capture) and part 3 (upstream fix search). |
| `route-mapper-part1-final.md` | split copy, rest | the same file, bytes 6,504 onward | route-mapper's final part 1 report, appended after the adjudication: no cutoff through 03:29Z, off-pin by a per-turn method and by load, and 20129 after the limiter change. |
| `route-landscape-occupancy-research.md` | substituted copy | `route-landscape-occupancy-research.md` | The cited minimal occupancy fix and the user's decision. |
| `maintenance-gh-20260928.tsv` | copy | `maintenance-gh-20260928.tsv` | Default-branch last-commit dates of 18 upstreams from `gh api`, run 2026-09-28T02:01:49Z. |
| `ab-requirements.md` | copy | `ab-requirements.md` | The #431 A/B requirements note that the adjudication cites for the null effort columns. |
| `limiter-apply-20129.json` | derived | `limiter/apply.json` | The 20129 limiter change reduced to the requestQueue before and after, the limiter enabled flag before and after, and the UTC time. |
| `scripts/stage_receipts.py.txt` | script | | The script that wrote every copied, substituted, split and derived file above. It pins each one's SHA-256 and writes none that differs. |

The adjudication, the record and `decisions.json` cite the private names. Read each as the receipt named in the table.
`limiter/apply.json` is `limiter-apply-20129.json`, `TRACKER.md` is `decisions.json`, `route-job{1,2}.result.json` and
`commands.log` are `route-gpt6-runs.json`, and the last.json paths are `route-job{1,2}.last.json`.

## How the files were staged

The builder ran, from the repository root on 2026-09-28:

```sh
SCRATCH=<session scratch directory> WF_JOURNAL=<journal.jsonl of the record workflow> \
  uv run --no-project --with jsonschema python \
  evidence/artifacts/omniroute-routing-20260928/scripts/stage_receipts.py.txt
```

The builder ran it last after every other file here was written. That run exited 0, every output matched its pin, and
its scan found nothing in the 20 files then in this directory, the script and the three authored files included.

- **Copies** are byte-identical. Their SHA-256 values match the runner and tracker records where those exist:
  `route-job1.last.json` `e81ce40f…`, `route-job2.last.json` `27a46c9b…`, `route-job1.prompt.txt` `49863b44…`, and the
  two schemas `df09899c…` and `769a19bc…`.
- **Substitutions** change bytes, so the source hash is kept here. Undo the substitution to recover the source.

  | Receipt | Source SHA-256 | Substitution | Count |
  | --- | --- | --- | --- |
  | `route-job2.prompt.txt` | `3911644529f4aaea8e5a8461cf742c82e2b0bc1dfa0685430c9c64291c707124` | `internal/home/<file>` → `internal/home/{<file>}` | 1 |
  | `route-landscape-catalog.json` | `b2c1f2d50941e143ed94572349a6e374501c6f5744408d3bece10fa30f692cb0` | `internal/home/<file>` → `internal/home/{<file>}` | 1 |
  | `route-landscape-occupancy-research.md` | `7ecfd22215faabb34baf4b989983a665563838957fea73ff3b1937b265592ef3` | `scratchpad/` → `$SCRATCH/` | 2 |

  The braces exist only because `internal/home/` is CLIProxyAPI's Home-mode package: `scripts/validate.py` reads
  `/home/<name>` as a personal home path. `adjudication.json` carries the same brace form (4 substitutions) and says
  so in its own `sanitization` field. The JOB 2 prompt that GPT-6 actually received has the source hash above, which
  equals the runner's recorded `prompt_sha256`.
- **The split.** route-mapper's final part 1 report was appended to `route-mapper-resume-parts.md` after the
  adjudication stages ended at 02:32:12Z; the file's modification time is 03:30:26Z. The source is now 8,233 bytes with
  SHA-256 `6ab400e25ae53f58f91b6ab10f2012a9a968363abf892e08e91e63e07812c7cb`. Its first 6,503 bytes hash to
  `0a205329ceebeaa9cdfaa801348916fc8e565a8f57af6a07d7f70aa66f3fb437`, the version the builder first staged. The three
  adjudicators' transcripts contain that version's text and none of the appended report. The remaining 1,730 bytes are
  `route-mapper-part1-final.md` (`901a7eb5…`). Concatenating the two parts restores the source.
- **Derived files** keep whitelisted fields only. `route-gpt6-runs.json` drops the answer text (it is in the last.json
  copies) and keeps only counts and the `turn.completed` usage from the event streams. `limiter-apply-20129.json`
  drops the connection and provider ids, the connection name and the rate-limit cache statistics; the script checked
  that no other resilience setting changed.
- **Masks.** `~` is the home directory and `$SCRATCH` the session scratch directory.
- **Recovered adjudication.** The builder's task text carried the adjudication cut at 150,000 characters, inside E9.
  `adjudication.json` comes from the complete result records in the workflow's private journal.

The script scans every file in this directory with `scripts/validate.py`'s private-content patterns, an email pattern,
the literal home, scratch and journal paths and the two opaque ids of the private limiter record. It reports labels and
counts, never a matched value. The builder also ran `python3 scripts/validate.py --scan-file` on every file, after the
authored files were added. A grep of every new file for session, workflow and task handles found none. The only peer
names it found are the labels in `ab-requirements.md` described above.

## Checks recorded here

- Both GPT-6 answers validate against their frozen schemas: 0 errors each with jsonschema 4.26.0
  (`Draft202012Validator`). Each answer equals the runner's `output_text`, and each job's single `turn.completed`
  usage equals the runner's usage (`route-gpt6-runs.json`).
- Usage is Codex's own count. Cached input and cache-write input are inside `input_tokens`, and reasoning is inside
  `output_tokens`. The record splits input into disjoint categories and never adds reasoning to output again.

## Limits

- Everything from route-mapper and route-landscape is a relayed teammate result: sqlite read in `mode=ro`, `GET`
  endpoints, app.log and source at pinned revisions. Neither teammate could write files, so the coordinator wrote their
  reports. The metrics cover one 24 h window ending about 2026-09-28T00:13Z on 20128, plus 10 probe turns on 20129.
- The adjudication read the interim part 1. The final part 1 report (`route-mapper-part1-final.md`) arrived after it and
  was not adjudicated. That report gives 8.0% off-pin by a per-turn method, against 10.31% by the per-conversation
  method the adjudication used, and it shows the rate rising with load.
- The R02 read-back outputs are private (mode 0600). `decisions.json` records only their exit statuses and causes from
  the coordinator's log.
- Claude worker usage is unknown and is not estimated anywhere here.
