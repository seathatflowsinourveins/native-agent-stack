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
strata the packet hides. The case pack, the label packet and the rendered-input file are therefore
written to a private directory outside the repository; the repository holds their sha256 (the draw
record and the draft freeze manifest), which is what section 5.0 asks to publish before the first
call. Every file regenerates byte for byte from the frame commit and the seed. Placing quoted text
under `blueprints/` also tripped the AgentsView pin registry on 2026-10-03, which classifies every
tracked file outside dated prefixes that quotes its pinned version.

## Files

| File | Role |
|---|---|
| `p1_frame.py` | frame extractor: claims that cite a span, excerpts cut by code at the cited revision |
| `p1_casepack.py` | seeded draws, strata, blind label packet, adversarial slots and prompts, top-up, re-label list, native repeats, promptfoo test rows, rendered-input hashes, the public draw record |
| `p1_scoring.py` | scoring with scikit-learn and scipy: rules (a)-(e), bootstrap, McNemar, Wilson, Brier, ECE, stop rules |
| `p1_freeze.py` | freeze-manifest builder: sha256 of every frozen input, and the final consistency checks |
| `promptfooconfig.yaml`, `prompts/` | promptfoo 0.123.1 skeleton for arms J (three option orders), O, S, G and L |
| `render-check.yaml` | no-model render check (echo provider) |
| `l_nli_provider.py` | arm L Python provider skeleton; refuses to run until a checkpoint is frozen |
| `requirements-scoring.in`, `.lock` | numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, hash-locked with uv 0.12.17 |
| `draft/promptfoo-tests.jsonl` | generated test rows the configs read; never committed (they carry case text) |

Public draft record, in `evidence/artifacts/jev-p1-20261003/`: `draw-record.draft.json` (frame
commit, frame digest, counts, rules, drawn candidate ids, adversarial form and author per slot,
the re-label count and hash, strata counts, and the sha256 of the private files; no case id) and
`freeze-manifest.draft.json` (sha256 of every input that exists, the eight roles still missing, and
the render-check count). Private draft, outside the repository: `case-pack.draft.json`,
`label-packet.draft.json` and `rendered-inputs.draft.json`.

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
after they were cited (each candidate's `drift` field). Pinned upstream files are fetched once from
`raw.githubusercontent.com` at the pinned commit (31 fetched, 2 private-repository files excluded);
claims and excerpts that match `scripts/validate.py` private-content patterns or promptfoo template
syntax are excluded.

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
computed from public data before the pack is published.

## Label packet

The label packet shows each case's opaque id, claim and excerpt only, in seeded order, with the label
classes and criteria of `../promptfooconfig.yaml`, the claim-type attribute (literal, paraphrase,
indirection), the universal-claim rule and the numbers-and-dates rule. The draft lists the 105
complete cases and only a count of the 15 pending ones; a labelling page must refuse a draft, and the
labeller should not see one, because the 15 cases absent from it would be the adversarial ones.

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
The section 5.0 stop rules (service errors above 5% with resends counted, a moved model, more than 2
of 10 canary flips, any Jev result that is not `live`) and the usage, latency, error, attempt and
request-id summary per arm are reported with every score.

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
python3 -m unittest tests.test_jev_p1_casepack
JEV_P1_REQUIRE_SCORING_DEPS=1 "$VENV/bin/python" -m unittest tests.test_jev_p1_scoring
```

The CI validate job installs no scikit-learn, so `tests/test_jev_p1_scoring.py` skips there (a skip
is untested, not passed); it runs with the flag above in the hash-locked venv. A CI step like the
promotion-gate venv in `.github/workflows/validate.yml` would make it a required run.

On 2026-10-03 `promptfoo validate config` accepted both configs offline, two negative controls (an
unknown Codex option, a misspelled top-level key) failed it, and the echo render check reproduced
all 210 rendered prompts of the 105 complete cases byte for byte, run without network
(`unshare -rn`). promptfoo records `prompt.raw` in a re-serialized form, so the check compares the
echo output, which is what a provider receives.

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
5. Confirm the frozen texts: the universal-claim rule, the numbers-and-dates rule (their second
   sentences state what the criteria imply), the claim-type definitions, and the adversarial target
   ("supported") and placement.
6. The instruction-against-criteria check (failure mode 7): "a faithful paraphrase" supports, while
   numbers and dates must not be converted.
7. Arm L: choose and hash the checkpoint; its premise is truncated past 512 tokens (recorded per
   call); rule (d) for L needs repeated L calls or stays open.
8. Interval method (percentile) and the J-3 latency estimate (the slowest of the three order calls,
   the wall time if they run concurrently) are frozen choices to confirm.
