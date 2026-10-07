# Native invocation read-back

These readers fill the demonstrated attribution and exposure gap between native
client records and the OTel dashboard. They are record readers, not agent runners
or evaluation harnesses. Run against retained private records and write private
receipts outside the checkout. No timer or client configuration is installed here.

Sources: `openai/codex@rust-v0.160.1` (`d27764b82f7118f674371e6d6e76271d9d606edb`),
native `session_meta`, `item_completed`, parent thread and fork-history ordinal
fields; the maintained `tools/skill-usage/skill_usage.py` helpers and installed
Claude Code transcripts, cross-checked by
`examples/claude-native/workflows/child-usage.mjs`. Native schema/help observations
are private receipts. The dashboard follows Grafana v13.2.3 JSON provisioning
and Loki v3.7.8 range aggregation. Synthetic parser checks establish parser
behavior only, never unchanged upstream acceptance or organic tool quality.

`codex_counter.py --help` describes exact since/until boundaries, hcom identity,
private session homes and first-turn exclusions. It counts completed native MCP
and command items once, excludes inherited fork history and separates registered
roles from unregistered SDK sessions. Static skill read sites are attempts, not
successful loads. `role_denominators.py --help` collects only configuration key
names and native schema/listing metadata. A file's configured keys do not establish
effective exposure or a role's grants.

Raw invocations are separate from organic use. A tool call is organic only when
all task/user/queued prompts of its turn, including referenced cooperation blocks,
do not name that tool. The entire first turn after relaunch is excluded. Standing
guidance is separately labeled. Historical referenced blocks and effective
per-role exposure remain unresolved: report **not yet measured**, never organic
zero. Do not add native and telemetry counts, parent and copied history, or cache
subset and provider totals. The dated dashboard inventory applies to one observed
Codex session only.

Focused synthetic checks:

```sh
rtk proxy nice -n 19 python3 -m unittest discover -s tools/invocation-monitoring -p test_codex_counter.py -v
```

The 2026-10-06 90-minute comparison retains differing methods side by side:
registered native commands1,320 versus CC-v1 1,322; context-mode1,306 versus1,309;
turns174 versus223. Whole-scope values differ from registered-only values. These
differences remain partly unattributed; no merged total or counter-readiness claim.
