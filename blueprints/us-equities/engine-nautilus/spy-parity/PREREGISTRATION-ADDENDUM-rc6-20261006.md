---
status: proposed
date: 2026-10-06
review_by: 2027-01-04
---

# rc6 candidate replication: preregistration addendum

This source freeze identifies a new rc6 replication of the unchanged one_zero
method. It does not replace the rc5 preregistration or its results. Every original
file remains intact. No rc6 case has run; native economic equivalence and the
selected destination pin remain undecided.

The 2026-10-06 owner/co-op interpretation permits strict candidate engine and
active-source identity bindings, plus the explicit maker/taker model. It does
not permit changes to data, strategy, oracles, tolerances, economic predicates,
isolation checks or retained failure conditions. 5f may object at the addendum
read; the co-op arranges one independent Opus read before any rc6 case runs.

## Frozen candidate identities

| Source | SHA256 |
| --- | --- |
| blueprints/us-equities/engine-nautilus/spy-parity/run-rc6.py | b8e055359169b06ee350966c0844a7a66a91026f73f7fdfcb217514e51ac3e88 |
| blueprints/us-equities/engine-nautilus/spy-parity/compare-rc6.py | 41e775aabbb06696862de0e5a80f03034dde0908e841b1f53f5784d28cd137c8 |
| blueprints/us-equities/engine-nautilus/spy-parity/mapping-manifest-rc6.json | cd8949921ae1d02f45a5f1e3a30fb3753abc5aaa65fc2c3fa1b7fd0ba40a4cb1 |
| blueprints/us-equities/engine-nautilus/equity-replay/run-rc6.py | 7933183cefab05687ab25c50b19353d3ace85ef5de6d4ae4bee158aa12de28b4 |

The candidate manifest is sealed by the copied comparator's exact SHA256
constant. It preserves all non-identity/non-fee method fields and keeps the old
engine/source claims under rc5_historical_engine_provenance. Old probes remain
historical rc5 observations; they are not reclassified as rc6 results. The fee
model's explicit Decimal zero rates match the original implicit maker/taker
model; the JSON descriptor records what the candidate actually constructs.

The addendum's own hash is carried in the external review map and the runtime
source inventory. Neither the manifest nor comparator hardcodes that hash,
avoiding a reciprocal hash cycle. The original PREREGISTRATION-v2.md hash check
remains active; this addendum states the approved candidate-only differences.

## Every changed source line

The table includes every removed and added line against the pinned originals;
unchanged lines are omitted. A filename change on a byte-identical history copy
is shown separately below. Version, extension, engine hash, source identity and
fee model are binding-site categories, not new evidence classes. The machine
copy is evidence/artifacts/nautilus-rc6-qualification-20261005/candidate-changed-lines-20261006.json.

### run-rc6.py (spy-parity)

Original: blueprints/us-equities/engine-nautilus/spy-parity/run.py

| Side | Line | Category | Exact changed line |
| --- | ---: | --- | --- |
| original | 2 | source identity | <code>&quot;&quot;&quot;Replay the frozen ``one_zero`` SPY case twice on native NautilusTrader 2.0.0rc5.</code> |
| candidate | 2 | source identity | <code>&quot;&quot;&quot;Replay the frozen ``one_zero`` SPY case twice for rc6 candidate replication.</code> |
| original | 46 | source identity | <code>MANIFEST_V2 = &quot;mapping-manifest-v2.json&quot;</code> |
| candidate | 46 | source identity | <code>MANIFEST_V2 = &quot;mapping-manifest-rc6.json&quot;</code> |
| candidate | 47 | source identity | <code>ADDENDUM = &quot;PREREGISTRATION-ADDENDUM-rc6-20261006.md&quot;</code> |
| original | 50 | fee model | <code># add_venue instead of relied on as defaults. fill_model, fee_model and</code> |
| original | 51 | source identity | <code># latency_model stay None, as preregistered.</code> |
| candidate | 51 | fee model | <code># add_venue instead of relied on as defaults. fill_model and latency_model</code> |
| candidate | 52 | source identity | <code># remain None; the rc6 candidate declares rc5&#x27;s implicit maker/taker model</code> |
| candidate | 53 | fee model | <code># explicitly, with the same zero rates.</code> |
| original | 53 | fee model | <code>         &quot;fill_model&quot;: None, &quot;fee_model&quot;: None, &quot;latency_model&quot;: None, &quot;bar_execution&quot;: True,</code> |
| candidate | 55 | source identity | <code>         &quot;fill_model&quot;: None,</code> |
| candidate | 56 | fee model | <code>         &quot;fee_model&quot;: {&quot;class&quot;: &quot;MakerTakerFeeModel&quot;, &quot;maker_rate&quot;: &quot;0&quot;, &quot;taker_rate&quot;: &quot;0&quot;},</code> |
| candidate | 57 | source identity | <code>         &quot;latency_model&quot;: None, &quot;bar_execution&quot;: True,</code> |
| original | 161 | source identity | <code>REVIEWED_HARNESS_FILES = (&quot;convert.py&quot;, &quot;fixture_strategy.py&quot;, &quot;distribution_module.py&quot;, &quot;run.py&quot;,</code> |
| original | 162 | source identity | <code>                          &quot;compare.py&quot;)</code> |
| original | 163 | source identity | <code>REPLAY_HISTORY = &quot;replay-history-v2.json&quot;</code> |
| candidate | 165 | source identity | <code>REVIEWED_HARNESS_FILES = (&quot;convert.py&quot;, &quot;fixture_strategy.py&quot;, &quot;distribution_module.py&quot;, &quot;run-rc6.py&quot;,</code> |
| candidate | 166 | source identity | <code>                          &quot;compare-rc6.py&quot;, MANIFEST_V2, ADDENDUM)</code> |
| candidate | 167 | source identity | <code>REPLAY_HISTORY = &quot;replay-history-rc6.json&quot;</code> |
| original | 165 | source identity | <code>DEVIATION_ACCEPTANCE = &quot;deviation-acceptance-v2.json&quot;</code> |
| candidate | 169 | source identity | <code>DEVIATION_ACCEPTANCE = &quot;deviation-acceptance-rc6.json&quot;</code> |
| candidate | 552 | fee model | <code>    from nautilus_trader.execution import MakerTakerFeeModel</code> |
| original | 577 | fee model | <code>                             fill_model=VENUE[&quot;fill_model&quot;], fee_model=VENUE[&quot;fee_model&quot;],</code> |
| candidate | 582 | source identity | <code>                             fill_model=VENUE[&quot;fill_model&quot;],</code> |
| candidate | 583 | fee model | <code>                             fee_model=MakerTakerFeeModel(maker_rate=Decimal(&quot;0&quot;),</code> |
| candidate | 584 | fee model | <code>                                                        taker_rate=Decimal(&quot;0&quot;)),</code> |
| original | 724 | version | <code>    if installed != &quot;2.0.0rc5&quot;:</code> |
| candidate | 731 | version | <code>    if installed != &quot;2.0.0rc6&quot;:</code> |
| original | 771 | source identity | <code>        &quot;id&quot;: &quot;spy-parity-one-zero-v2&quot;,</code> |
| candidate | 778 | source identity | <code>        &quot;id&quot;: &quot;spy-parity-one-zero-rc6-candidate-20261006&quot;,</code> |
| candidate | 779 | source identity | <code>        &quot;qualification_kind&quot;: &quot;rc6 candidate replication&quot;,</code> |
| original | 797 | source identity | <code>                            &quot;sha256&quot;: digest(SOURCE / &quot;PREREGISTRATION-v2.md&quot;)},</code> |
| candidate | 805 | source identity | <code>                             &quot;sha256&quot;: digest(SOURCE / &quot;PREREGISTRATION-v2.md&quot;)},</code> |
| candidate | 806 | source identity | <code>        &quot;candidate_addendum&quot;: {&quot;path&quot;: ADDENDUM, &quot;sha256&quot;: digest(SOURCE / ADDENDUM)},</code> |
| original | 802 | source identity | <code>                                 &quot;run.py&quot;, &quot;compare.py&quot;, MANIFEST_V1, MANIFEST_V2,</code> |
| original | 803 | source identity | <code>                                 &quot;tolerances.json&quot;)</code> |
| candidate | 811 | source identity | <code>                                  &quot;run-rc6.py&quot;, &quot;compare-rc6.py&quot;, MANIFEST_V1, MANIFEST_V2,</code> |
| candidate | 812 | source identity | <code>                                  &quot;tolerances.json&quot;, ADDENDUM)</code> |

### compare-rc6.py (spy-parity)

Original: blueprints/us-equities/engine-nautilus/spy-parity/compare.py

| Side | Line | Category | Exact changed line |
| --- | ---: | --- | --- |
| original | 74 | source identity | <code>SEALED_V2_MANIFEST_SHA256 = &quot;1b821d7ba42ea6121002a26a5082df08ed7a79f9a50b2edc9959503e1088ac67&quot;</code> |
| candidate | 74 | source identity | <code>SEALED_V2_MANIFEST_SHA256 = &quot;cd8949921ae1d02f45a5f1e3a30fb3753abc5aaa65fc2c3fa1b7fd0ba40a4cb1&quot;</code> |
| original | 77 | source identity | <code>REVIEWED_HARNESS_FILES = (&quot;convert.py&quot;, &quot;fixture_strategy.py&quot;, &quot;distribution_module.py&quot;, &quot;run.py&quot;,</code> |
| original | 78 | source identity | <code>                          &quot;compare.py&quot;)</code> |
| candidate | 77 | source identity | <code>REVIEWED_HARNESS_FILES = (&quot;convert.py&quot;, &quot;fixture_strategy.py&quot;, &quot;distribution_module.py&quot;, &quot;run-rc6.py&quot;,</code> |
| candidate | 78 | source identity | <code>                          &quot;compare-rc6.py&quot;, &quot;mapping-manifest-rc6.json&quot;,</code> |
| candidate | 79 | source identity | <code>                          &quot;PREREGISTRATION-ADDENDUM-rc6-20261006.md&quot;)</code> |
| original | 90 | source identity | <code>REPLAY_HISTORY = &quot;replay-history-v2.json&quot;</code> |
| candidate | 91 | source identity | <code>REPLAY_HISTORY = &quot;replay-history-rc6.json&quot;</code> |
| original | 93 | source identity | <code>DEVIATION_ACCEPTANCE = &quot;deviation-acceptance-v2.json&quot;</code> |
| candidate | 94 | source identity | <code>DEVIATION_ACCEPTANCE = &quot;deviation-acceptance-rc6.json&quot;</code> |
| original | 99 | source identity | <code>V2_SOURCES =(&quot;convert.py&quot;, &quot;fixture_strategy.py&quot;, &quot;distribution_module.py&quot;, &quot;run.py&quot;,</code> |
| original | 100 | source identity | <code>              &quot;compare.py&quot;, &quot;mapping-manifest.json&quot;, &quot;mapping-manifest-v2.json&quot;, &quot;tolerances.json&quot;)</code> |
| candidate | 100 | source identity | <code>V2_SOURCES =(&quot;convert.py&quot;, &quot;fixture_strategy.py&quot;, &quot;distribution_module.py&quot;, &quot;run-rc6.py&quot;,</code> |
| candidate | 101 | source identity | <code>              &quot;compare-rc6.py&quot;, &quot;mapping-manifest.json&quot;, &quot;mapping-manifest-rc6.json&quot;, &quot;tolerances.json&quot;,</code> |
| candidate | 102 | source identity | <code>              &quot;PREREGISTRATION-ADDENDUM-rc6-20261006.md&quot;)</code> |
| candidate | 1164 | source identity | <code>    verdict[&quot;qualification_kind&quot;] = &quot;rc6 candidate replication&quot;</code> |

### mapping-manifest-rc6.json (spy-parity)

Original: blueprints/us-equities/engine-nautilus/spy-parity/mapping-manifest-v2.json

| Side | Line | Category | Exact changed line |
| --- | ---: | --- | --- |
| original | 3 | source identity | <code>  &quot;id&quot;: &quot;spy-parity-one-zero-mappings-v2&quot;,</code> |
| candidate | 3 | source identity | <code>  &quot;id&quot;: &quot;spy-parity-one-zero-mappings-v2-rc6-20261006&quot;,</code> |
| original | 5 | source identity | <code>  &quot;drafted_utc_date&quot;: &quot;2026-09-22&quot;,</code> |
| candidate | 5 | source identity | <code>  &quot;drafted_utc_date&quot;: &quot;2026-10-06&quot;,</code> |
| original | 9 | source identity | <code>  &quot;run_status_note&quot;: &quot;No v2 replay, no v2 comparison and no v2 verdict exists. Nothing in this file was produced by running the parity harness. The only engine executions behind it are the synthetic engine-semantics probes under probes/v2/, and the one_zero predictions below are arithmetic on the frozen, hash-pinned LEAN inputs.&quot;,</code> |
| candidate | 9 | source identity | <code>  &quot;run_status_note&quot;: &quot;This rc6 candidate is frozen before its first execution. No rc6 case or comparison has run. Original rc5 probes, source citations, review/deviation records and replay history retain their historical scopes; current native execution and independent review remain separate requirements.&quot;,</code> |
| candidate | 23 | source identity | <code>    &quot;package&quot;: &quot;nautilus_trader&quot;,</code> |
| candidate | 24 | version | <code>    &quot;version&quot;: &quot;2.0.0rc6&quot;,</code> |
| candidate | 25 | engine hash | <code>    &quot;upstream_commit_pin&quot;: &quot;7b766f8825b2539c5b2ac1375e9d97b41c509edb&quot;,</code> |
| candidate | 26 | source identity | <code>    &quot;environment&quot;: &quot;~/.cache/ns2604-j4-rc6-home/projects/us-equities-runtime/.venv&quot;,</code> |
| candidate | 27 | source identity | <code>    &quot;interpreter&quot;: &quot;~/.cache/ns2604-j4-rc6-home/projects/us-equities-runtime/.venv/bin/python&quot;,</code> |
| candidate | 28 | source identity | <code>    &quot;extension_sha256&quot;: {</code> |
| candidate | 29 | extension | <code>      &quot;_libnautilus.cpython-312-x86_64-linux-gnu.so&quot;: &quot;da5fd063a9f0df9f1e6d0b8dfcdfcc9d9691fe6f8d4eeb89562c96c508805178&quot;</code> |
| candidate | 30 | source identity | <code>    },</code> |
| candidate | 31 | source identity | <code>    &quot;runtime_receipt&quot;: &quot;evidence/receipts/nautilus-rc6-runtime-2604-20261006.json&quot;,</code> |
| candidate | 32 | source identity | <code>    &quot;source_citations&quot;: {</code> |
| candidate | 33 | source identity | <code>      &quot;explicit_fee_model&quot;: &quot;nautechsystems/nautilus_trader@7b766f8825b2539c5b2ac1375e9d97b41c509edb:docs/getting_started/quickstart.py:131,221-224&quot;,</code> |
| candidate | 34 | source identity | <code>      &quot;model_api&quot;: &quot;nautechsystems/nautilus_trader@7b766f8825b2539c5b2ac1375e9d97b41c509edb:python/nautilus_trader/execution/__init__.pyi:190-197&quot;</code> |
| candidate | 35 | source identity | <code>    },</code> |
| candidate | 36 | source identity | <code>    &quot;source_scope&quot;: &quot;Current rc6 identity and API; the original rc5 engine/probe citations remain historical under rc5_historical_engine_provenance.&quot;</code> |
| candidate | 37 | source identity | <code>  },</code> |
| candidate | 38 | source identity | <code>  &quot;rc5_historical_engine_provenance&quot;: {</code> |
| original | 81 | fee model | <code>    &quot;fee_model&quot;: null,</code> |
| candidate | 97 | fee model | <code>    &quot;fee_model&quot;: {</code> |
| candidate | 98 | fee model | <code>      &quot;class&quot;: &quot;MakerTakerFeeModel&quot;,</code> |
| candidate | 99 | fee model | <code>      &quot;maker_rate&quot;: &quot;0&quot;,</code> |
| candidate | 100 | fee model | <code>      &quot;taker_rate&quot;: &quot;0&quot;</code> |
| candidate | 101 | source identity | <code>    },</code> |

### run-rc6.py (equity-replay)

Original: blueprints/us-equities/engine-nautilus/equity-replay/run.py

| Side | Line | Category | Exact changed line |
| --- | ---: | --- | --- |
| original | 198 | version | <code>    if importlib.metadata.version(&quot;nautilus_trader&quot;) != &quot;2.0.0rc5&quot;:</code> |
| candidate | 198 | version | <code>    if importlib.metadata.version(&quot;nautilus_trader&quot;) != &quot;2.0.0rc6&quot;:</code> |

## History, independent review and owner records

replay-history-rc6.json starts as a byte-identical copy of replay-history-v2.json:
ca08721fe7f197151cb2f061794a2064809b8a88e9b865d1c62c2279a4af740c.
Keep its inherited failed/unreviewed rc5 rows. After an actual rc6 attempt,
append that attempt, its actual runner/comparator identities and returned result
only to the candidate file before any retry. Never alter the original history.
The unchanged comparator still checks append-only history and prior replay
identity; a failed attempt cannot disappear on the next run.

The external review uses the existing spy-parity-v2-harness-review/1 schema.
It must provide reviewer, actual completed_utc, reviewed_commit,
reviewed_local_source_sha256 and unresolved_findings integer 0, and be inside
this checkout. The seven reviewed immutable files are convert.py,
fixture_strategy.py, distribution_module.py, run-rc6.py, compare-rc6.py,
mapping-manifest-rc6.json and this addendum. The runtime and copied comparator
hash the files that actually ran. A current review cannot reuse the old
review-record-v2-cc4503f.json source identities.

Inherited unreviewed history still triggers the existing gate-owner deviation
predicate. A genuine new deviation-acceptance-rc6.json must be supplied by 5f,
using the unchanged schema/fields and this candidate's reviewed source map.
The runner never creates that approval. Its absence or a copied old approval
remains a failing precondition; it is not converted into acceptance. The
original deviation acceptance remains historical and byte-identical.

## Frozen references

- blueprints/us-equities/engine-nautilus/spy-parity/run.py: c3917c2f6446ffb1bcfe411cc2339ffc1f804a87904ed3a1f1a67e51817ad2f2
- blueprints/us-equities/engine-nautilus/spy-parity/compare.py: c70386f869e45bcdc54602100991235a450d2a5854445d98ffe45b849454a5ec
- blueprints/us-equities/engine-nautilus/spy-parity/mapping-manifest-v2.json: 1b821d7ba42ea6121002a26a5082df08ed7a79f9a50b2edc9959503e1088ac67
- blueprints/us-equities/engine-nautilus/spy-parity/mapping-manifest.json: 43f510494a970d235f27e5676120ee749b45eb6b060cf74f0b768374b8177909
- blueprints/us-equities/engine-nautilus/spy-parity/PREREGISTRATION-v2.md: 4393a1b7d896b2f49c4091c18701bd08cfc72a8d313f0ad2a628e91db26d6f0c
- blueprints/us-equities/engine-nautilus/spy-parity/tolerances.json: c8bc72317fb4de83f2b0b7e71888828c7dd15a5a7eb2f60b68f87d54e751c15a
- blueprints/us-equities/engine-nautilus/spy-parity/convert.py: 08cba0a2aac938e9306935f91c2889b181dfc880b532b5943e0ccda395592c65
- blueprints/us-equities/engine-nautilus/spy-parity/fixture_strategy.py: 59649ac50f26c8b6090dc976e4ec0b3b7e2121cc214674f6c122fbbca9b143f1
- blueprints/us-equities/engine-nautilus/spy-parity/distribution_module.py: eefee070b0dbe6ad3a1e68755ca959b5fff081fad61af8b84902a438996b126b
- blueprints/us-equities/engine-nautilus/spy-parity/replay-history-v2.json: ca08721fe7f197151cb2f061794a2064809b8a88e9b865d1c62c2279a4af740c
- blueprints/us-equities/engine-nautilus/spy-parity/deviation-acceptance-v2.json: b279cf6a81489591e722a97f4e1f085041f358153a9f3553f61e559122dbeb89
- blueprints/us-equities/engine-nautilus/spy-parity/review-record-v2-cc4503f.json: 7fdf6d104f7e75b07718b33873fd2d32f06113e3cc42a14adfa934aeb0fb01f6
- blueprints/us-equities/historical-simulation/plan.json: 60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632
- blueprints/us-equities/historical-simulation/receipt.json: 06ec065647abd91a0ca2b13da25dd75c3ccd159a3244a241a3207c58b36f95d9
- blueprints/us-equities/engine-nautilus/equity-replay/run.py: e036aa9354a478fe270258d3d2f2cb42a5c9c072d688b21313e0a89e715d796e
- blueprints/us-equities/engine-nautilus/equity-replay/plan.json: 1e3cefdab959c9ce15e6d9d07ff6135b5720f8792bed06b2e02510dd880dd805
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json: deb72b1d9a54f6e1d56783ea72ee55bb176bd5862c6a6f49cc1c86e6de4c4294

The retained SPY reference is +304 at 323.58, -304 at 291.69, distributions 428.64,
end cash 90734.08 and fees 0. All economic predicates remain unchanged. Any native
mismatch is retained as failure; no oracle, tolerance or strategy retuning is
part of this candidate. The five retained input hashes are unchanged in the
candidate manifest. AAPL's FixedFeeModel and both case oracles remain unchanged;
AAPL stays blocked and will not run in this job.

## Validation and execution conditions

The copied comparator's economic and admission functions are byte-identical;
only CLI output identity and declared binding constants change. Local synthetic
controls reuse tests/test_spy_parity.py and cover candidate binding, old review/
approval rejection, ABI mismatch and unchanged price/fee/cash failures. These
fixtures establish no native economic parity. The first fee negative used an
unused key; it was corrected to the original comparator's authoritative fee
field, with no comparator or tolerance change. That failed fixture run stays
in private logs, separately from the passing rerun.

Before execution, retain the passing independent exact-head read, the actual
checkout-contained review record and 5f's source-bound deviation disposition.
The owner must also stage the five frozen inputs and approve the managed-Python
isolated mount route; J2's narrow .venv mount omits its managed .python base.
No new mount or data-provider operation is silently introduced here.

Run only SPY one_zero in the existing isolated rc6 runtime, at nice 19 outside
10:35-11:30Z and 19:50-20:30Z on 2026-10-06. Preserve all returned exit codes,
execution/precondition failures and timestamps. Native receipt, machine verdict
and publication receipt must say rc6 candidate replication, use new output
names and bind actual candidate files. The old preregistered rc5 results stay
intact. 5f owns C1-C4/risk-cap checks and the runtime-target pin decision.

## Sources

- native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:
  blueprints/us-equities/engine-nautilus/spy-parity/run.py:46-48,161-166,240-273,297-343,724-725,782-804;
  compare.py:74-100,263-344,692-855,1101-1118. These supply the unchanged
  source/hash/review/history/isolation predicates and economic comparator.
- nautechsystems/nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e:
  crates/execution/src/models/fee.rs:183-186 gives the rc5 default.
- nautechsystems/nautilus_trader@7b766f8825b2539c5b2ac1375e9d97b41c509edb:
  docs/getting_started/quickstart.py:131,221-224 and
  python/nautilus_trader/execution/__init__.pyi:190-197 give the native rc6 import/rates.
- Trading-owner ruling relayed 2026-10-06T03:49:15Z and J4PROCEED2026-10-06T04:36:06Z
  authorize the identity-binding interpretation; they are distinct from the
  pending independent read, native case evidence and destination decision.
- evidence/receipts/nautilus-rc6-candidate-addendum-20261006.json records classes,
  source identities and open conditions without upgrading historical evidence.
