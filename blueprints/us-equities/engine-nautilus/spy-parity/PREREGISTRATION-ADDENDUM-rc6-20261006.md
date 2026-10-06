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
unchanged lines are omitted. Historical source-identity rows appended to the candidate history
are included separately below. Version, extension, engine hash, source identity and
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

replay-history-rc6.json preserves the complete original replay prefix and the
original file SHA ca08721fe7f197151cb2f061794a2064809b8a88e9b865d1c62c2279a4af740c.
Two recovered J2 rc5 attempts are appended before this freeze, from the
published launcher receipt at native-agent-stack@5271c87dbf8ebbc745afe3b9ee22c4d8528c4770:
blueprints/us-equities/engine-nautilus/evidence/j2-sim-rc5-20261005/spy-one_zero-launcher-equivalent-20261006T044147Z.json.
Both actual replays exited 0 and comparisons exited 1; their full failing verdicts
remain unqualified. Review-before-run flags come from the actual retained
review hash/schema/source/time/findings checks, verified against the reported
verdict hashes, not from execution counts or a later review. Their source maps
remain rc5 maps, so neither is mistaken for an earlier run of this new rc6
harness. The original history remains unchanged.

After a real rc6 attempt, append its actual identity/result only to the candidate
file before any retry. Never erase a failed attempt or change the historical
prefix. The unchanged comparator still checks append-only history and prior
replay identity.

### Every appended historical source-identity line

| Side | Line | Category | Exact changed line |
| --- | ---: | --- | --- |
| candidate | 145 | source identity | <code>    },</code> |
| candidate | 146 | source identity | <code>    {</code> |
| candidate | 147 | source identity | <code>      &quot;id&quot;: &quot;j2-rc5-runtime-env-20261006&quot;,</code> |
| candidate | 148 | source identity | <code>      &quot;observed_utc&quot;: [</code> |
| candidate | 149 | source identity | <code>        &quot;2026-10-06T04:40:32Z&quot;</code> |
| candidate | 150 | source identity | <code>      ],</code> |
| candidate | 151 | source identity | <code>      &quot;engine_version&quot;: &quot;2.0.0rc5&quot;,</code> |
| candidate | 152 | source identity | <code>      &quot;harness&quot;: &quot;Original ecfa11276 rc5 source; J2 retained attempt, not an rc6 candidate execution.&quot;,</code> |
| candidate | 153 | source identity | <code>      &quot;isolation&quot;: &quot;Launcher-equivalent vector; .venv/.python/repository/data read-only; cleared environment; one owned output. Initial acceptance environment included extra names, rejected by the comparator.&quot;,</code> |
| candidate | 154 | source identity | <code>      &quot;outcome&quot;: &quot;Replay exit0; comparator exit1; full verdictFAIL retained. {\&quot;PASS\&quot;: 134, \&quot;FAIL\&quot;: 2}; failure fields no_prior_replay_ran_the_reviewed_harness,environment_beyond_cleared_set. No qualification inferred from execution checks.&quot;,</code> |
| candidate | 155 | source identity | <code>      &quot;receipt_sha256&quot;: [</code> |
| candidate | 156 | source identity | <code>        &quot;ee29bf214b3831aac1206624cd575ab4bfd20a24e4c1470ee953b0e2e241c695&quot;</code> |
| candidate | 157 | source identity | <code>      ],</code> |
| candidate | 158 | source identity | <code>      &quot;verdict_sha256&quot;: &quot;a1569e1c68f87c3767930e6c00be193633f2a0d9d193289704ca2942ecd6d6f2&quot;,</code> |
| candidate | 159 | source identity | <code>      &quot;harness_local_source_sha256&quot;: {</code> |
| candidate | 160 | source identity | <code>        &quot;compare.py&quot;: &quot;c70386f869e45bcdc54602100991235a450d2a5854445d98ffe45b849454a5ec&quot;,</code> |
| candidate | 161 | source identity | <code>        &quot;convert.py&quot;: &quot;08cba0a2aac938e9306935f91c2889b181dfc880b532b5943e0ccda395592c65&quot;,</code> |
| candidate | 162 | source identity | <code>        &quot;distribution_module.py&quot;: &quot;eefee070b0dbe6ad3a1e68755ca959b5fff081fad61af8b84902a438996b126b&quot;,</code> |
| candidate | 163 | source identity | <code>        &quot;fixture_strategy.py&quot;: &quot;59649ac50f26c8b6090dc976e4ec0b3b7e2121cc214674f6c122fbbca9b143f1&quot;,</code> |
| candidate | 164 | source identity | <code>        &quot;mapping-manifest-v2.json&quot;: &quot;1b821d7ba42ea6121002a26a5082df08ed7a79f9a50b2edc9959503e1088ac67&quot;,</code> |
| candidate | 165 | source identity | <code>        &quot;mapping-manifest.json&quot;: &quot;43f510494a970d235f27e5676120ee749b45eb6b060cf74f0b768374b8177909&quot;,</code> |
| candidate | 166 | source identity | <code>        &quot;run.py&quot;: &quot;c3917c2f6446ffb1bcfe411cc2339ffc1f804a87904ed3a1f1a67e51817ad2f2&quot;,</code> |
| candidate | 167 | source identity | <code>        &quot;tolerances.json&quot;: &quot;c8bc72317fb4de83f2b0b7e71888828c7dd15a5a7eb2f60b68f87d54e751c15a&quot;</code> |
| candidate | 168 | source identity | <code>      },</code> |
| candidate | 169 | source identity | <code>      &quot;reviewed_before_run&quot;: true,</code> |
| candidate | 170 | source identity | <code>      &quot;review_coverage_proof&quot;: {</code> |
| candidate | 171 | source identity | <code>        &quot;source_locator&quot;: &quot;seathatflowsinourveins/native-agent-stack@5271c87dbf8ebbc745afe3b9ee22c4d8528c4770:blueprints/us-equities/engine-nautilus/evidence/j2-sim-rc5-20261005/spy-one_zero-launcher-equivalent-20261006T044147Z.json#/attempts/runtime-env&quot;,</code> |
| candidate | 172 | source identity | <code>        &quot;source_sha256&quot;: &quot;f909ea5a9c4ede9260f2938218db87d523359ed67c994521dac46ab47f981417&quot;,</code> |
| candidate | 173 | source identity | <code>        &quot;returned_verdict_sha256&quot;: &quot;a1569e1c68f87c3767930e6c00be193633f2a0d9d193289704ca2942ecd6d6f2&quot;,</code> |
| candidate | 174 | source identity | <code>        &quot;checks&quot;: [</code> |
| candidate | 175 | source identity | <code>          {</code> |
| candidate | 176 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 177 | source identity | <code>            &quot;field&quot;: &quot;record_sha256_at_comparison&quot;,</code> |
| candidate | 178 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 179 | source identity | <code>          },</code> |
| candidate | 180 | source identity | <code>          {</code> |
| candidate | 181 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 182 | source identity | <code>            &quot;field&quot;: &quot;schema&quot;,</code> |
| candidate | 183 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 184 | source identity | <code>          },</code> |
| candidate | 185 | source identity | <code>          {</code> |
| candidate | 186 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 187 | source identity | <code>            &quot;field&quot;: &quot;reviewed_files_are_the_files_that_ran&quot;,</code> |
| candidate | 188 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 189 | source identity | <code>          },</code> |
| candidate | 190 | source identity | <code>          {</code> |
| candidate | 191 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 192 | source identity | <code>            &quot;field&quot;: &quot;completed_before_run_started&quot;,</code> |
| candidate | 193 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 194 | source identity | <code>          },</code> |
| candidate | 195 | source identity | <code>          {</code> |
| candidate | 196 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 197 | source identity | <code>            &quot;field&quot;: &quot;unresolved_findings&quot;,</code> |
| candidate | 198 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 199 | source identity | <code>          }</code> |
| candidate | 200 | source identity | <code>        ]</code> |
| candidate | 201 | source identity | <code>      },</code> |
| candidate | 202 | source identity | <code>      &quot;returned_failing_checks&quot;: [</code> |
| candidate | 203 | source identity | <code>        {</code> |
| candidate | 204 | source identity | <code>          &quot;blocked_by&quot;: null,</code> |
| candidate | 205 | source identity | <code>          &quot;delta&quot;: &quot;-&quot;,</code> |
| candidate | 206 | source identity | <code>          &quot;expected&quot;: &quot;[]&quot;,</code> |
| candidate | 207 | source identity | <code>          &quot;field&quot;: &quot;no_prior_replay_ran_the_reviewed_harness&quot;,</code> |
| candidate | 208 | source identity | <code>          &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 209 | source identity | <code>          &quot;key&quot;: &quot;precondition_review.no_prior_replay_ran_the_reviewed_harness#35&quot;,</code> |
| candidate | 210 | source identity | <code>          &quot;observed&quot;: &quot;[&#x27;bwrap-cc4503f-host-nativestack-5975wx-20260925&#x27;, &#x27;bwrap-cc4503f-qualifying&#x27;]&quot;,</code> |
| candidate | 211 | source identity | <code>          &quot;ordinal&quot;: 35,</code> |
| candidate | 212 | source identity | <code>          &quot;status&quot;: &quot;FAIL&quot;,</code> |
| candidate | 213 | source identity | <code>          &quot;tolerance&quot;: &quot;exact&quot;</code> |
| candidate | 214 | source identity | <code>        },</code> |
| candidate | 215 | source identity | <code>        {</code> |
| candidate | 216 | source identity | <code>          &quot;blocked_by&quot;: null,</code> |
| candidate | 217 | source identity | <code>          &quot;delta&quot;: &quot;-&quot;,</code> |
| candidate | 218 | source identity | <code>          &quot;expected&quot;: &quot;[]&quot;,</code> |
| candidate | 219 | source identity | <code>          &quot;field&quot;: &quot;environment_beyond_cleared_set&quot;,</code> |
| candidate | 220 | source identity | <code>          &quot;id&quot;: &quot;precondition_engine&quot;,</code> |
| candidate | 221 | source identity | <code>          &quot;key&quot;: &quot;precondition_engine.environment_beyond_cleared_set#53&quot;,</code> |
| candidate | 222 | source identity | <code>          &quot;observed&quot;: &quot;[&#x27;GIT_OPTIONAL_LOCKS&#x27;, &#x27;HOME&#x27;, &#x27;MPLBACKEND&#x27;, &#x27;UV_OFFLINE&#x27;, &#x27;XDG_CACHE_HOME&#x27;]&quot;,</code> |
| candidate | 223 | source identity | <code>          &quot;ordinal&quot;: 53,</code> |
| candidate | 224 | source identity | <code>          &quot;status&quot;: &quot;FAIL&quot;,</code> |
| candidate | 225 | source identity | <code>          &quot;tolerance&quot;: &quot;exact&quot;</code> |
| candidate | 226 | source identity | <code>        }</code> |
| candidate | 227 | source identity | <code>      ],</code> |
| candidate | 228 | source identity | <code>      &quot;status&quot;: &quot;retained rc5 reproduction; unqualified full verdict; not an rc6 run&quot;</code> |
| candidate | 229 | source identity | <code>    },</code> |
| candidate | 230 | source identity | <code>    {</code> |
| candidate | 231 | source identity | <code>      &quot;id&quot;: &quot;j2-rc5-documented-env-20261006&quot;,</code> |
| candidate | 232 | source identity | <code>      &quot;observed_utc&quot;: [</code> |
| candidate | 233 | source identity | <code>        &quot;2026-10-06T04:41:27Z&quot;</code> |
| candidate | 234 | source identity | <code>      ],</code> |
| candidate | 235 | source identity | <code>      &quot;engine_version&quot;: &quot;2.0.0rc5&quot;,</code> |
| candidate | 236 | source identity | <code>      &quot;harness&quot;: &quot;Original ecfa11276 rc5 source; J2 retained attempt, not an rc6 candidate execution.&quot;,</code> |
| candidate | 237 | source identity | <code>      &quot;isolation&quot;: &quot;Launcher-equivalent vector; .venv/.python/repository/data read-only; cleared environment; one owned output. Final environment uses the five documented values.&quot;,</code> |
| candidate | 238 | source identity | <code>      &quot;outcome&quot;: &quot;Replay exit0; comparator exit1; full verdictFAIL retained. {\&quot;PASS\&quot;: 135, \&quot;FAIL\&quot;: 1}; failure fields no_prior_replay_ran_the_reviewed_harness. No qualification inferred from execution checks.&quot;,</code> |
| candidate | 239 | source identity | <code>      &quot;receipt_sha256&quot;: [</code> |
| candidate | 240 | source identity | <code>        &quot;bebba33c0a1dd6eabc6570ca00c0acd3517fcf4397ae6f0874e24f325537871d&quot;</code> |
| candidate | 241 | source identity | <code>      ],</code> |
| candidate | 242 | source identity | <code>      &quot;verdict_sha256&quot;: &quot;5c788e43f6bcaf2596f586a597e615338406f3b8483045f32c25796ff903d44e&quot;,</code> |
| candidate | 243 | source identity | <code>      &quot;harness_local_source_sha256&quot;: {</code> |
| candidate | 244 | source identity | <code>        &quot;compare.py&quot;: &quot;c70386f869e45bcdc54602100991235a450d2a5854445d98ffe45b849454a5ec&quot;,</code> |
| candidate | 245 | source identity | <code>        &quot;convert.py&quot;: &quot;08cba0a2aac938e9306935f91c2889b181dfc880b532b5943e0ccda395592c65&quot;,</code> |
| candidate | 246 | source identity | <code>        &quot;distribution_module.py&quot;: &quot;eefee070b0dbe6ad3a1e68755ca959b5fff081fad61af8b84902a438996b126b&quot;,</code> |
| candidate | 247 | source identity | <code>        &quot;fixture_strategy.py&quot;: &quot;59649ac50f26c8b6090dc976e4ec0b3b7e2121cc214674f6c122fbbca9b143f1&quot;,</code> |
| candidate | 248 | source identity | <code>        &quot;mapping-manifest-v2.json&quot;: &quot;1b821d7ba42ea6121002a26a5082df08ed7a79f9a50b2edc9959503e1088ac67&quot;,</code> |
| candidate | 249 | source identity | <code>        &quot;mapping-manifest.json&quot;: &quot;43f510494a970d235f27e5676120ee749b45eb6b060cf74f0b768374b8177909&quot;,</code> |
| candidate | 250 | source identity | <code>        &quot;run.py&quot;: &quot;c3917c2f6446ffb1bcfe411cc2339ffc1f804a87904ed3a1f1a67e51817ad2f2&quot;,</code> |
| candidate | 251 | source identity | <code>        &quot;tolerances.json&quot;: &quot;c8bc72317fb4de83f2b0b7e71888828c7dd15a5a7eb2f60b68f87d54e751c15a&quot;</code> |
| candidate | 252 | source identity | <code>      },</code> |
| candidate | 253 | source identity | <code>      &quot;reviewed_before_run&quot;: true,</code> |
| candidate | 254 | source identity | <code>      &quot;review_coverage_proof&quot;: {</code> |
| candidate | 255 | source identity | <code>        &quot;source_locator&quot;: &quot;seathatflowsinourveins/native-agent-stack@5271c87dbf8ebbc745afe3b9ee22c4d8528c4770:blueprints/us-equities/engine-nautilus/evidence/j2-sim-rc5-20261005/spy-one_zero-launcher-equivalent-20261006T044147Z.json#/attempts/documented-env&quot;,</code> |
| candidate | 256 | source identity | <code>        &quot;source_sha256&quot;: &quot;f909ea5a9c4ede9260f2938218db87d523359ed67c994521dac46ab47f981417&quot;,</code> |
| candidate | 257 | source identity | <code>        &quot;returned_verdict_sha256&quot;: &quot;5c788e43f6bcaf2596f586a597e615338406f3b8483045f32c25796ff903d44e&quot;,</code> |
| candidate | 258 | source identity | <code>        &quot;checks&quot;: [</code> |
| candidate | 259 | source identity | <code>          {</code> |
| candidate | 260 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 261 | source identity | <code>            &quot;field&quot;: &quot;record_sha256_at_comparison&quot;,</code> |
| candidate | 262 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 263 | source identity | <code>          },</code> |
| candidate | 264 | source identity | <code>          {</code> |
| candidate | 265 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 266 | source identity | <code>            &quot;field&quot;: &quot;schema&quot;,</code> |
| candidate | 267 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 268 | source identity | <code>          },</code> |
| candidate | 269 | source identity | <code>          {</code> |
| candidate | 270 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 271 | source identity | <code>            &quot;field&quot;: &quot;reviewed_files_are_the_files_that_ran&quot;,</code> |
| candidate | 272 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 273 | source identity | <code>          },</code> |
| candidate | 274 | source identity | <code>          {</code> |
| candidate | 275 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 276 | source identity | <code>            &quot;field&quot;: &quot;completed_before_run_started&quot;,</code> |
| candidate | 277 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 278 | source identity | <code>          },</code> |
| candidate | 279 | source identity | <code>          {</code> |
| candidate | 280 | source identity | <code>            &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 281 | source identity | <code>            &quot;field&quot;: &quot;unresolved_findings&quot;,</code> |
| candidate | 282 | source identity | <code>            &quot;status&quot;: &quot;PASS&quot;</code> |
| candidate | 283 | source identity | <code>          }</code> |
| candidate | 284 | source identity | <code>        ]</code> |
| candidate | 285 | source identity | <code>      },</code> |
| candidate | 286 | source identity | <code>      &quot;returned_failing_checks&quot;: [</code> |
| candidate | 287 | source identity | <code>        {</code> |
| candidate | 288 | source identity | <code>          &quot;blocked_by&quot;: null,</code> |
| candidate | 289 | source identity | <code>          &quot;delta&quot;: &quot;-&quot;,</code> |
| candidate | 290 | source identity | <code>          &quot;expected&quot;: &quot;[]&quot;,</code> |
| candidate | 291 | source identity | <code>          &quot;field&quot;: &quot;no_prior_replay_ran_the_reviewed_harness&quot;,</code> |
| candidate | 292 | source identity | <code>          &quot;id&quot;: &quot;precondition_review&quot;,</code> |
| candidate | 293 | source identity | <code>          &quot;key&quot;: &quot;precondition_review.no_prior_replay_ran_the_reviewed_harness#35&quot;,</code> |
| candidate | 294 | source identity | <code>          &quot;observed&quot;: &quot;[&#x27;bwrap-cc4503f-host-nativestack-5975wx-20260925&#x27;, &#x27;bwrap-cc4503f-qualifying&#x27;]&quot;,</code> |
| candidate | 295 | source identity | <code>          &quot;ordinal&quot;: 35,</code> |
| candidate | 296 | source identity | <code>          &quot;status&quot;: &quot;FAIL&quot;,</code> |
| candidate | 297 | source identity | <code>          &quot;tolerance&quot;: &quot;exact&quot;</code> |
| candidate | 298 | source identity | <code>        }</code> |
| candidate | 299 | source identity | <code>      ],</code> |
| candidate | 300 | source identity | <code>      &quot;status&quot;: &quot;retained rc5 reproduction; unqualified full verdict; not an rc6 run&quot;</code> |

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
J2 now supplies staged SPY inputs and the approved launcher-equivalent route
with .venv and .python read-only. Verify the same five hashes and reuse its final
five-value cleared environment with the isolated rc6 runtime; the initial J2
extra-environment failure stays retained. AAPL remains input-blocked.
No new mount or data-provider operation is silently introduced here.

Run only SPY one_zero in the existing isolated rc6 runtime, at nice 19 outside
10:35-13:45Z on 2026-10-06 and 19:50Z on 2026-10-06 through 00:10Z on
2026-10-07. No user-manager restart is permitted in those windows; pause between
steps and never kill a running case. Preserve all returned exit codes,
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

Paper-window source: co-op correction2026-10-06T05:04:26Z from5f via command-center item task-ns2604-coop-20261006T050351Z.
