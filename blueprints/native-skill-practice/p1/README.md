# P1 case pack and draft freeze packet (claim-to-source verification)

P1 is the first preregistration of the Jev and TypeSafe design report r1 (section 5.1): can
`jev-1.13.0` close "supported" claims ahead of Opus without letting non-supported claims through?
This folder holds its deterministic tooling. Nothing here has called a model or sent a case to any
service, nothing is labelled, and nothing is frozen. The report's sections 5.0 and 5.1 are the
specification; this README names where each rule is implemented.

**Location.** Split by kind. The tooling sits here, beside the harness it extends: the J arm
reuses `../response.cjs` and `../gate.cjs`, P1 follows this folder's case-building precedent
(`../README.md:78-81`), and the repository keeps runnable plans and preregistration code in
`blueprints/` (for example `blueprints/retrieval-quality-v2/PREREGISTRATION.md`). The dated,
content-free draft record sits in `evidence/artifacts/jev-p1-20261003/`, hash-listed like every file
there (`scripts/validate.py:316-317`); the frozen pack, labels, receipts and results will go to
`evidence/artifacts/jev-p1-<freeze date>/`. The frame excludes both paths from itself.

**No case text is published before the labels exist.** The user is the only labeller (section 5.0),
and the case pack maps every case to its subset, stratum and provenance, while the adversarial
authoring prompts name the 15 base pairs. A pull request carrying either would show the labeller the
strata the packet hides. The frame file, the case pack, the label packet and the rendered-input file
are therefore written to a private directory outside the repository; the repository holds their
sha256 (the draw record and the draft freeze manifest), which is what section 5.0 asks to publish
before the first call. The frame file is kept beside the pack, so its digest and statistics can be
recomputed; the pack, the packet and the rendered inputs regenerate byte for byte from it and the
seed. On 2026-10-03 a rebuild at the frame commit from the same upstream cache, with no network,
reproduced the frame file byte for byte. Placing quoted text under
`blueprints/` also tripped the AgentsView pin registry on 2026-10-03, which classifies every tracked
file outside dated prefixes that quotes its pinned version.

## Files

| File | Role |
|---|---|
| `p1_frame.py` | frame extractor: claims that cite a span, excerpts cut by code at the cited revision |
| `p1_casepack.py` | seeded draws, strata, blind label packet, adversarial slots and prompts, the A2 gate (`a2-input`, `a2`), top-up, re-label list, native repeats, promptfoo test rows, rendered-input hashes (prompts and J request bodies), the public draw record |
| `p1_scoring.py` | scoring with scikit-learn and scipy: rules (a)-(e), bootstrap, McNemar, Wilson, Brier, ECE, stop rules |
| `p1_freeze.py` | freeze-manifest builder: sha256 of every frozen input, and the final consistency checks |
| `promptfooconfig.yaml`, `prompts/` | promptfoo 0.123.1 skeleton for arms J (three option orders), O, S, G and L |
| `response-model.cjs` | arm J's response transform: `../response.cjs` unchanged, plus the response's model field in its error |
| `render-check.yaml`, `render_echo_server.py` | no-model render check: the echo provider for the prompts, loopback copies of the J providers for the request bodies |
| `l_nli_provider.py` | arm L Python provider skeleton; refuses to run until a checkpoint is frozen |
| `requirements-scoring.in`, `.lock` | numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, hash-locked with uv 0.12.17 |
| `draft/promptfoo-tests.jsonl` | generated test rows the configs read; never committed (they carry case text) |

Public draft record, in `evidence/artifacts/jev-p1-20261003/`: `draw-record.draft.json` (frame
commit, frame digest, counts, rules, drawn candidate ids, adversarial form and author per slot,
the re-label count and hash, strata counts, A2 passes (none yet), and the sha256 of the private
frame, case pack and label packet; no case id) and `freeze-manifest.draft.json` (sha256 of every
input that exists, the eight roles still missing, and the render-check count). Private draft,
outside the repository: `frame.json`, `case-pack.draft.json`, `label-packet.draft.json` and
`rendered-inputs.draft.json`.

## Frame and draws (draft at frame commit `ecea28654a83`)

Frame rules are frozen in `p1_frame.FRAME_RULES` and copied into the draw record. In short: claim
sentences in `evidence/receipts/`, `evidence/artifacts/*/README.md`, `docs/decisions/` and retained
review packets (`evidence/artifacts/**` JSON or Markdown named review, critique, verif*, finding or
packet) that hold exactly one citation of a repository `file:line`, a pinned upstream blob URL with a
line anchor, an own-repository `name@commit:path:line`, or an RFC 6901 receipt field. The excerpt is
the cited lines with 3 lines of context on each side, the GNU diff unified default (`diff --help`,
diffutils 3.10). It is cut at the revision the citation cited: its own pin, else the commit that
introduced the citation text to the citing document (`git log -S`). Cutting at the frame commit
would have tested line drift: in 184 of 424 comparable natural candidates the cited lines changed
after they were cited (each candidate's `drift` field in the private `frame.json`). Pinned upstream
files are fetched once from `raw.githubusercontent.com` at the pinned commit (31 fetched, 2
private-repository files excluded); only an HTTP 404 is cached as missing, and any other fetch
failure stops the build. Both cached 404s were fetched again at 2026-10-03T21:26:31Z and still
returned 404. Claims and excerpts that match the private-content patterns of `scripts/validate.py`
at the frame commit (read from that blob like every other frame input, never from the working tree;
only the `PRIVATE_CONTENT` assignment is evaluated) or promptfoo template syntax are excluded.

The enriched pool takes `claim` records that a retained review refuted or corrected (`refuted`,
`verifier_verdict` partly or refuted, `verdict` refuted, `result` contradicted, a `correction` or
`problem` text) and the cited sentences of candidates whose `adversarial_verification` holds a
refuting vote. The review verdict is provenance only; the user's label decides every class.

| Count | Draft value |
|---|---|
| frame size (natural frame) | 458 candidates from 433 documents |
| enriched pool | 70 |
| adversarial base candidates after the earlier draws | 398 |
| drawn | natural 60, enriched 45, adversarial 15 slots |
| top-up reserve | 25 of the 30 the rule allows |
| sha256 of the drawn ids | `5c6bb78ef80c00e148d863f0559ab617f829659fd624ea2f6d2256a6d3eadaec` |
| frame digest | `75b6dfe49910cb86976ecdc260eb58c5933202d48a87f892c7b7c28e54b38fe7` |

Draws rank candidate ids by `sha256("20261003|<purpose>|<id>")`, so they depend only on the seed and
the ids: natural first, then enriched (claims already drawn excluded), then the adversarial base
pairs. The top-up reserve is the enriched ranking after the first 45; a batch is the current deficit
below 60 non-supported labels, at most 30 in total. Adversarial slots get five per vendor form
(injected instruction, misleading framing, text arguing for its own classification), then Opus 8 and
Sol 7, balanced 3-3-2 across forms, all by seed; code places each insertion after the cited span.
The presentation order and the 18 re-label positions (15%) are keyed on the insertions as well, so
the completed packet's ids and re-label set share nothing with the draft's, and neither can be
computed from public data before the pack is published. Because those keys hash the whole insertion
object, `build` refuses an insertion file whose keys are not exactly the 15 slot ids. A top-up batch
adds its re-label share from its own new cases, and `topup` refuses a frame whose digest differs from
the pack's `frame_sha256` or whose reserved claim and excerpt bytes differ from the hashes the reserve
recorded at the draw.

## Label packet and the A2 gate

The label packet shows each case's opaque id, claim and excerpt only, in seeded order, with the label
classes and criteria of `../promptfooconfig.yaml`, the claim-type attribute (literal, paraphrase,
indirection), the universal-claim rule and the numbers-and-dates rule. The two rules are section
5.1's sentences as written. The draft lists the 105 complete cases and only a count of the 15 pending
ones; a labelling page must refuse a draft, and the labeller should not see one, because the 15 cases
absent from it would be the adversarial ones.

A pack with every insertion written is `awaiting_a2`, and its packet stays a draft. Section 3.1's A2
custody pass runs over the exact bytes first: `p1_casepack.py a2-input` writes each case's claim and
excerpt (the only case-dependent bytes in the packet and in every rendered input) with the sha256 an
A2 result must name; gitleaks 8.30.1 scans that file, and the host-path and identity rule and the
home-directory and user-name canary run over each claim and excerpt. `p1_casepack.py a2` then takes
the result (`jev-p1-a2-result/1`: `input_sha256`, a `passed` flag for each of the three checks, and
the post-A2 claim or excerpt of every case the rule changed). It refuses a result over other bytes, a
failed check, or a change to a case an earlier pass froze; it applies the changed texts (a changed
claim's universal and numeric-or-date strata are computed again from the post-A2 claim), records the
pass (input, output and result sha256, and the share of cases changed) and only then marks the pack
`ready_for_labels` and the packet `ready`. A top-up batch sends the pack back to `awaiting_a2`.
`p1_freeze.py --final` refuses a pack whose bytes are not the output of its last A2 pass; A2 custody
files that are not, in pass order, the original results of the recorded passes (canonical
`result_sha256`, the pass's input bytes and every check passed; a missing, extra, duplicate or
mismatched original is refused, and so are a custody file that is not a JSON A2 result object and a
pass whose `input_sha256` or `result_sha256` is missing, null or not 64 lowercase hex characters,
each under its own reason before any pair is compared); a label packet that is not
`label_packet(pack)` in full (cases, rules, criteria, claim types and instructions); a label or
re-label record outside the packet's `label_record` contract (exactly `case_id`, `label`,
`claim_type` and `labelled_at` as a UTC timestamp); and test rows that are not the bytes `tests`
writes from the pack, the labels' native repeats and three local repeats.

## Scoring

`p1_scoring.py` implements section 5.1 as written: adopt C only if (a)-(e) all hold, reject J on two
or more false closes or order flips above 10%, otherwise inconclusive; arm L qualifies under (a)-(d)
with L in place of J, and a rule not measured for L stays open, never a pass. Upstream methods:
`scipy.stats.bootstrap` (paired, 10,000 resamples, `rng=default_rng(20261003)`, percentile, two-sided
95%) with the best native arm chosen inside each resample; exact McNemar as
`scipy.stats.binomtest(b, b+c, 0.5)`; Wilson bounds from `binomtest(...).proportion_ci(method="wilson")`;
balanced accuracy, confusion matrices, Cohen's kappa and multiclass Brier from `sklearn.metrics`;
15-bin top-label ECE per Guo et al. 2017 (arXiv:1706.04599; `gpleiss/temperature_scaling@ce1154ec`,
`temperature_scaling.py:105-127`), checked bin by bin against `sklearn.calibration.calibration_curve`.

Order flips are counted over all cases and repeat disagreement over all (case, order) pairs, the
frozen denominators. A case or pair that lost an answer to a failed call is incomplete, and the rate
is reported as bounds (incomplete units counted as agreeing, then as disagreeing): rule (d) must hold
at the high bound and the reject rule fires at the low bound, so a failed call never helps either
verdict; with nothing incomplete both bounds equal the frozen rate (open decision 9). For arm L the
order-flip part of (d) does not apply, and repeat disagreement is measured over the three frozen L
calls per case (`tests --local-repeats 3`), over all cases; a run that holds fewer than three for every
case leaves (d) open, never measured on fewer repeats, and L cannot qualify (open decision 7).

Scoring reads the frozen test rows (`--tests`, the rows the freeze checked) as the call schedule:
every call must be an (arm, case, order, repeat) key those rows produce under the config's arm-group
filters (1,080 J keys, 180 per native arm and 360 L keys for 120 cases), or scoring refuses the calls;
a scheduled key without a call (a truncated output or a crashed run) leaves the run without a verdict.

The section 5.0 stop rules (service errors above 5% with resends counted, a moved model, more than 2
of 10 canary flips, any Jev result that is not `live`) and the usage, latency, error, attempt and
request-id summary per arm are reported with every score. "5% of calls" is computed in both readings,
and the run stops when either is above 5%: per scheduled call, section 5.1's unit, where a call that
failed or needed a resend counts once; and per request, where every resend is itself a call, so a call
with k recorded attempts is k requests of which k-1 were resent. A call without an attempt count is
never taken as one attempt, and a scheduled call without a result has an unknown outcome: each share
is reported as bounds, the stop fires on the low bound (what was recorded), and the report counts the
calls whose resends are unknown (open decision 12). A failed call whose response never reached the
contract check has an unknown model, which is not a move; a refused response's model is read from the
error `response-model.cjs` writes; an answered Jev call without the pinned model stops the run as
`jev_model_unverified`. Attempt counts come from provider metadata and are unknown where it records
none (no arm records them today; J's `maxRetries: 0` sends one request per call). The A1 canary count
is required (`--canary-flips`, 0 to 10). A stopped run, a missing scheduled call or a missing canary
count gives `inconclusive` with reason `stopped`, `incomplete_call_matrix` or `canary_missing` (all
that apply in `reasons`), the rule values stay in `partial`, and arm L does not qualify.

## Reproduce (no model call)

```sh
uv venv --python "$PYTHON" "$VENV"
uv pip sync --python "$VENV/bin/python" --require-hashes blueprints/native-skill-practice/p1/requirements-scoring.lock
python3 blueprints/native-skill-practice/p1/p1_frame.py --commit <frame commit> \
  --cache-dir <private cache> --out <private>/frame.json            # full clone: it reads history
python3 blueprints/native-skill-practice/p1/p1_casepack.py build --frame <private>/frame.json \
  --out-dir <private> --public-record evidence/artifacts/jev-p1-20261003/draw-record.draft.json
python3 blueprints/native-skill-practice/p1/p1_casepack.py tests --pack <private>/case-pack.draft.json \
  --rows blueprints/native-skill-practice/p1/draft/promptfoo-tests.jsonl \
  --rendered <private>/rendered-inputs.draft.json
unshare -rn sh -c 'ip link set lo up; python3 blueprints/native-skill-practice/p1/render_echo_server.py & \
  sleep 1; cd blueprints/native-skill-practice/p1 && promptfoo eval -c render-check.yaml \
  --filter-metadata arm_group=render --no-cache --no-share --no-write --no-table \
  --output <private>/render.json; kill $!'
python3 blueprints/native-skill-practice/p1/p1_freeze.py --spec <private>/freeze-spec.json \
  --render-echo <private>/render.json --out evidence/artifacts/jev-p1-20261003/freeze-manifest.draft.json
python3 -m unittest tests.test_jev_p1_casepack
JEV_P1_REQUIRE_SCORING_DEPS=1 "$VENV/bin/python" -m unittest tests.test_jev_p1_scoring
```

The CI validate job installs no scikit-learn, so `tests/test_jev_p1_scoring.py` skips there (a skip
is untested, not passed); it runs with the flag above in the hash-locked venv. A CI step like the
promotion-gate venv in `.github/workflows/validate.yml` would make it a required run.

**Rendered inputs.** The echo output is the prompt O, S and G receive (L receives the jev-state prompt
but reads the source and claim vars). Arm J receives neither prompt as text: promptfoo 0.123.1's HTTP
provider parses the JSON-valued state back into an object and sends JSON.stringify of the whole body
(`dist/src/providers-*.js` `processJsonBody`, `determineRequestBody` and the fetch body), the body
shape of the retained 09-21 harness. The rendered-input file therefore holds five records per case:
`native-question`, `jev-state`, and the request body of `J-o0`, `J-o1` and `J-o2`, computed by
`p1_casepack.jev_request_body`. `render-check.yaml` sends every case through loopback copies of the
three J providers (the same body blocks, which a test compares; no Authorization header) whose echo
server returns the request body unchanged. promptfoo records `prompt.raw` in a re-serialized form,
so the check never compares it.

On 2026-10-03, run without network (`unshare -rn`, loopback only): `promptfoo validate config`
accepted both configs, and a misspelled Codex option (`cli_configs`) failed it; the render check
reproduced all 525 rendered inputs of the 105 complete cases byte for byte (210 prompts from the echo
provider and 315 J request bodies from the loopback copies; the J bodies differ from the jev-state
prompt bytes). A J copy using `response-model.cjs` against the loopback echo showed the error text
`Unexpected TypeSafe model or answer contract [response model: "jev-latest"]`, which
`calls_from_promptfoo` reads back as a moved model.

**Arm S launch context.** `codex mcp list -c 'mcp_servers={}'` (codex-cli 0.159.3) still listed every
configured server, so an override cannot empty the host's MCP servers; an empty `CODEX_HOME` listed
none. The S provider therefore sets `CODEX_HOME` and `HOME` through `cli_env` to directories the
runner makes, and switches features off through `cli_config` (`codex features list` with those
overrides showed each off except `unified_exec`, which stayed on). The smoke check must show the
resulting state.

## Open decisions before labelling, freeze and calls

1. Rule (a) at exactly 60 non-supported: the two-sided 95% Wilson upper bound for 0 of 60 is 0.0602,
   so "at most 0.060" holds only at three decimals (0 of 61 gives 0.0592). The code compares at
   three decimals (`WILSON_DECIMALS`); a test shows both readings.
2. The enriched pool holds 70 pairs, so the top-up reserve is 25, not 30.
3. 38 of 60 natural claims, 19 of 45 enriched and 10 of 15 adversarial contain a digit, which the
   routing rule sends to Opus. Rule (b) (closure at least 25% of all cases) then needs C to close at
   least 30 of the 53 digit-free cases, and only 5 adversarial cases can test a J false close.
   Restricting adversarial base pairs to digit-free claims would be a draw-rule change before freeze.
4. Code edits claim text in two frozen ways: it removes the citation, and where the citation was the
   sentence's subject it writes "The source" in its place (3 natural and 3 enriched drawn claims).
   Confirm that a claim edited this way still counts as a real pair, or exclude such sentences.
5. Confirm the frozen texts: the universal-claim rule and the numbers-and-dates rule (section 5.1's
   sentences as written, with no added sentence), the claim-type definitions, and the adversarial
   target ("supported") and placement.
6. The instruction-against-criteria check (failure mode 7) covers the question text and both label
   rules: "a faithful paraphrase" supports, while numbers and dates must not be converted. It must
   settle the value written differently from the claim (for example a fraction against its
   percentage): the number rule says it does not match, and the criteria make it contradicted only
   when the excerpt "explicitly establishes a fact incompatible with the claim". Whether such a case
   is contradicted or insufficient is left open by the frozen texts; the check decides it.
7. Arm L: choose and hash the checkpoint; its premise is truncated past 512 tokens (recorded per
   call). Default to confirm: the order-flip part of (d) is not applicable to L (one premise-hypothesis
   pair, no option order), and (d) is L's repeat disagreement over three repeated calls per case, over
   all cases, at most 3%. With fewer than three repeats (d) stays open and L cannot qualify.
8. Interval method (percentile) and the J-3 latency estimate (the slowest of the three order calls,
   the wall time if they run concurrently) are frozen choices to confirm. The J run is serialized
   (`--max-concurrency 1`), so each call's latency is uncontended; section 5.1 defines the decision
   latency as "the wall time of three concurrent calls", the deployed configuration, not their sum.
9. Missing-data rule, a default to confirm: the order-flip and repeat-disagreement denominators stay
   at all cases and all pairs; incomplete units bound the rate, (d) is judged at the high bound and the
   reject rule at the low bound (section "Scoring").
10. Section 5.3 hashes M1's deepeval configuration, judge, prompts and classifier categories in P1's
    freeze commit. `p1_freeze.py` has no role for it: the coordinator decides whether P1's manifest
    carries one or a separate unit supplies it before that commit.
11. Arm S's route: with only the native auth.json in its `CODEX_HOME`, S signs in natively and its
    served model is not in the OmniRoute call log (section 5.0 then records "unknown"); routing S
    through OmniRoute needs the provider block in that home, frozen with it. Check `unified_exec` and
    any exec tool in the smoke check.
12. Resend evidence. Section 5.0 counts resends, but no arm records an attempt count today: J sends
    one request per call by configuration (`maxRetries: 0`), and the native SDK providers may retry
    inside their clients without reporting it. Scoring therefore checks resends only where a call
    records its attempts, gives both stop shares as bounds, and stops on the recorded evidence. Whether
    a run whose resends are unknown for some calls may still issue a verdict, or the harness must
    record attempts per call first, is a decision before freeze.

## Gated steps, in order

Each step needs the one before it. Steps marked (model) are model calls and wait for the user's go;
none has run.

1. Settle open decisions 2-4 (frame and draw) before the insertions, 5-6 (label rules) before labels,
   and the rest before the freeze.
2. (model) Insertions: Opus writes 8 and Sol 7 from the frozen authoring prompts, each in a fresh
   session whose inputs are listed (section 5.0, output custody); code places them.
3. Final pack: `p1_casepack.py build --insertions <private>/insertions.json` gives `awaiting_a2` and
   reorders every case and the re-label positions.
4. A2 over those final bytes: `a2-input`, then gitleaks 8.30.1, the host-path and identity rule and
   the home-directory and user-name canary, recording the share of cases changed; `p1_casepack.py a2`
   freezes the post-A2 bytes (`ready_for_labels`).
5. Labels: the user labels all 120 blind on the ready packet.
6. Re-labels: the 18 seeded cases, at least 24 hours after the first labels and before any arm call.
7. Top-up, only if fewer than 60 labels are non-supported: `topup`, A2 on the extended pack (step 4),
   the user labels the batch and re-labels its share at least 24 hours later; at most 25 pairs.
8. `native-repeats` (30 cases), and arm L's checkpoint chosen and hashed (local, nothing sent).
9. `tests --native-repeats ... --local-repeats 3`, then the render check (echo and loopback J bodies,
   no network) matching every rendered input.
10. (model) Smoke checks: one non-P1 case per native provider (O, S, G), showing the subscription
    sign-in, tools off, the schema validated, the effort applied, the served model and the launch
    context (for S, the minimal `CODEX_HOME`); their init events are hashed.
11. Inputs from other units: the A1 canary set (10 frozen cases and their stored answers) and, if the
    coordinator so decides, M1's deepeval configuration (open decision 10).
12. Freeze: `p1_freeze.py --final`, committed, pushed and merged to main, so every sha256 is reachable
    from main before the first call. The user's section 6.2 decisions (the TypeSafe key's delivery and
    the spend) come before step 13.
13. (model) The A1 canary first: stop if more than 2 of 10 cases flip.
14. (model) Arm calls (J 1,080; O, S and G 180 each; L local), then `p1_scoring.py --tests <frozen
    rows> --canary-flips <A1 count>`.
