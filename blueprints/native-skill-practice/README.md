# Native skills and advisory source review

This opt-in practice combines the upstream TypeSafe skill, existing Promptfoo
HTTP/echo providers and native Codex/Claude evidence-review roles. It selects
useful semantic assistance without replacing native accounts, worker models,
deterministic rules or execution. The [selection record](../../docs/native-skill-practice-20260921.md)
and [manifest](../../catalogs/landscape/native-practice.json) distinguish source
review, installation, returned native results and remaining limits.

## Install only the selected skills

[`adoption/skills/manifest.json`](../../adoption/skills/manifest.json) is the single source of
truth for which skills are installed, at which upstream revision, and at which listing state
(`kept`/`trial`, `claude_listing`, `codex_enabled`); its
[2026-09-25 trial record](../../docs/decisions/2026-09-25-skills-trial-and-usage.md) is the
decision record. Two scripts read that manifest instead of a hand-run upstream installer:

```sh
SKILLS=<tools-root>/skills-1.7.0/bin/skills
npm install --global --prefix <tools-root>/skills-1.7.0 skills@1.7.0    # the manifest's cli.install (pinned, isolated)
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS" --dry-run   # prints what would change, changes nothing
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS"             # installs every manifest entry at its pinned ref
python3 tools/adoption/install_skills.py --print-codex-config              # [[skills.config]] lines for ~/.codex/config.toml
python3 scripts/skills_status.py --skills-bin "$SKILLS"                    # per-skill ref, lock, links, listing state, Codex config, on-disk tree (informational)
claude -p "/skill-doctor" --output-format json                             # native per-skill use count, 0 API tokens
```

`install_skills.py` does not install the CLI itself: it requires the pinned `skills` CLI (the
manifest's `cli.version`, installed into an isolated npm prefix by `cli.install`, never a global
or bare `npx` install), refuses with that install command when `--skills-bin` is missing or
reports another version, and runs every
invocation with `DISABLE_TELEMETRY=1` so neither the telemetry event nor the add-time audit call
fires. It installs each skill at the manifest's exact 40-hex `ref`, for both Claude and Codex in
one command (`skills add <tree URL> --skill <name> -g -y -a claude-code codex`), and checks the
manifest's `tree_sha`/`skill_md_sha256` against the installed copy rather than trusting the
installer's own exit code. Do not additionally install the TypeSafe marketplace plugin for the
same skill, and do not run the bare upstream `skills` CLI by hand against manifest entries: that
installs outside the pinned prefix and without the telemetry guard. Preserve existing skills,
native sign-in and configuration. The recorded source commits and file hashes in the manifest
identify the reviewed versions; a later installer result requires a fresh source comparison.
Installer risk badges (skills.sh's Gen Agent Trust Hub, Socket, Snyk) are not native acceptance
or a security certification.

### Historical: the pre-manifest three-skill install (superseded 2026-09-25)

Before the manifest and its two scripts existed, the three then-selected skills were installed
by hand with the bare upstream installer, with no pinned CLI version and no telemetry guard:

```sh
npx skills add typesafe-ai/skills --skill typesafe-ai --agent codex claude-code --global
npx skills add openai/skills --skill gh-fix-ci security-best-practices --agent codex claude-code --global
```

For a project-owned copy instead of a global one, that installer took `--copy` in place of
`--global`. These three skills are unchanged `kept` winners in the current manifest, so a host
that already ran these two commands does not need to re-run them; a new host uses
`install_skills.py` instead, which also covers the manifest's other 23 skills.

Use the [Claude role](../../examples/claude-native/agents/semantic-evidence-reviewer.md)
or [Codex role](../../examples/codex-native/agents/semantic-evidence-reviewer.toml)
only for a semantic evidence task. Place the selected definition in the project's
native agents directory. Both inherit model/effort. Claude declares the TypeSafe
skill and has a direct-read fallback for headless invocation. Codex explicitly
loads the skill and uses native read-only source access with an explicit directory.
No service credential belongs in a worker prompt or role definition.

The coordinator supplies authorized TypeSafe results, with source references and
the deterministic availability decision. The worker recovers source evidence,
checks entity/time/scope and can correct the advice. Existing no-tools report
workers may consume already qualified inputs; installing a skill does not enable
new tools in that lane. The exact-only scout remains separate.

## Reproduce the bounded diagnostic

The provider/gate/response adapters and six contract tests were reused unchanged
from the earlier agent-lab TypeSafe pilot. `cases.json` preserves that 16-case
fixture for its contract checks; it is not rerun as this task's fresh inference.
`catalog-cases.json` is a separate eight-case diagnostic built from actual retained
catalog excerpts and the pinned upstream skill. An independent reviewer labeled
it before inference; two ambiguous claims were clarified before labels were frozen
at SHA-256 `7cc28c50afb9842de3d8dc923e80159bf99d0f0e9acd643684a99b61b3ad3a40`.
No expected label is sent to TypeSafe. C6's future-availability fields are explicitly
illustrative gate inputs, not historical acquisition evidence.

The retained Promptfoo run compacted the JSON-valued C1/C2 source strings before
rendering the provider prompt. Their parsed JSON is equal to the frozen source;
the bytes differ. The result separates frozen-excerpt hashes, actual rendered
source hashes and the earlier summary's trimmed-excerpt hashes. The other six
source strings are unchanged. This provenance correction does not alter labels,
responses or the original private report.

Use the selected Promptfoo 0.123.1 and a supported Node runtime. From this folder:

```sh
node --test test-contract.cjs
REQUEST_TIMEOUT_MS=15000 python3 ../../tools/credentials/credential_run.py typesafe -- \
  timeout 180s promptfoo eval -c promptfooconfig.yaml \
  --no-cache --max-concurrency 1 --repeat 1 --no-share --no-write --no-table \
  --output /private/path/to/results.json
```

Disable Promptfoo telemetry/update checks on a new PC, as the adopted native
launcher does. The [key runner](../../docs/secret-storage.md#using-a-key) reads
the `typesafe` inventory entry's `0600` file and adds `TYPESAFE_API_KEY` to this
one promptfoo process only, so no key file goes on the command line; the
2026-09-21 run passed the key with `--env-file` instead. The upstream provider
has zero retries; the request and whole-process deadlines are separate. Review
raw results privately before publishing a sanitized receipt.

The [fresh result](typesafe-result.json) records TypeSafe `jev-1.13.0` at **7/8**
frozen labels versus **3/8** for weak literal containment. It made eight uncached
requests with zero service errors, 4,846 input and 375 output tokens. Median
observed provider latency was 171.5 ms. Promptfoo exit 100 preserves the one
TypeSafe and five comparator assertion failures; it is not a clean evaluation pass.
C4 returned `contradicted` where the frozen label was `insufficient`. Do not change
the labels after seeing the model output. Native source review must retain that
disagreement and its possible interpretation rather than promote the universal
claim. C6 remains rejected by the availability gate despite semantic support.

The [worker packet](worker-packet.json) omits oracle labels and carries the original
source excerpts and advisory probabilities. Native worker results are assisted
source verification, not an independent matched model benchmark. No general
accuracy, latency, token savings, trading value or universal SOTA claim follows
from these small selected tests. Current native results and failed attempts are
recorded in the selection record and its linked receipt.

## Jev rules (2026-10-03)

These rules adopt Jev, TypeSafe's typed-judgment model, for no feature. They come
from section 3.1 of the design report "Jev and TypeSafe: typed judgments for the
foundation and north-star R&D" (2026-10-03, revision r1, sha256 `6fdd8bc2…`),
which is kept outside the repository. Jev sets no final status anywhere: the
report's section 7 rejects that until two preregistered, held-out,
human-labelled replications pass (P1, then P1b with the P1 threshold frozen).

- **A1 Version pin and drift canary.** Name `jev-1.13.0` in every client, config
  and receipt, never the moving `jev-latest` or `jev-preview` alias that the
  Python SDK and deepeval default to, and log the response `model` field.
  `response.cjs` and `validate()` in `tools/sota-convergence/gap_crosswalk.py`
  refuse any other model, and `test-contract.cjs` tests that refusal. TypeSafe
  states no retirement window, so a pinned version can stop answering without
  notice, and frozen research columns cannot be regenerated after that. Every
  run therefore starts with a canary: 10 frozen cases are re-scored and compared
  with their stored answers, and the run records how many answers changed,
  because two third-party evaluations saw answers move under the same version
  ID. The 10 cases and their stored answers are not frozen yet, so no run can
  start before they are.
- **A2 Custody.** Send only public or research-grade text whose terms allow
  third-party processing. Never send broker or account state, positions, orders,
  credentials, private receipts, host paths, licensed news, the SEC contact
  string or unpublished hypotheses. Assume every byte sent persists: TypeSafe's
  Master Customer Agreement (updated 2026-09-23, §4.1 and §4.3) lets it derive
  Telemetry from inputs in perpetuity and use that without restriction. Before
  any call, run the stack's pinned gitleaks 8.30.1
  (`catalogs/sota-convergence/manifest-20260929.json`, secrets layer) and a
  deterministic host-path and identity rule over the exact bytes, then a literal
  search for the host's home path and user name, and freeze those bytes so that
  every arm and the labeller see the same bytes. Each preregistration reports
  the share of cases the rule changed. The rule removes paths and identities
  only, never model or tool names, which claims name; the packet scrubber of
  `tools/token-e2e/judge.py` replaces tool names and stays a judge-blinding tool.
  Record each call's request ID, usage and attempt count, keep SDK logging below
  debug in receipt runs, and treat zero data retention as unavailable until an
  enterprise contract is recorded.
- **A3 Jaggedness controls.** TypeSafe's jaggedness page for jev-1.13 lists nine
  failure modes, and each has a control. Questions and criteria are checked
  against the labelling rule, and against each other, before freeze. Questions
  are single-hop, and code cuts the state to what the decision needs. Every
  frozen Jev case set carries permuted option orders with a stable-answer
  requirement, and adversarial state in the vendor's three forms: an injected
  instruction, a misleading framing, and text that argues for its own
  classification. Counts, arithmetic and date comparison stay in code.
  Extraction stays with code or a generative model; Jev only picks among options
  that code lists. Jev never closes a claim whose support depends on a number or
  a date: code sends every claim that contains a digit to Opus.
- **A4 Reviewer schema at the call site.** The reviewer roles return the object
  that [`semantic-evidence-reviewer.schema.json`](semantic-evidence-reviewer.schema.json)
  describes: per case `case_id`, `final_disposition` (supported, contradicted or
  insufficient) and `retained_provider_disposition`, with source references, a
  correction and limits. Agent frontmatter has no schema field, so the caller
  supplies the schema. Inside a multi-stage workflow, dispatch the role through
  `agent({agentType, schema})`, which validates the return and fails the call
  after five invalid attempts ([workflows](https://code.claude.com/docs/en/workflows)).
  A single review is one Agent-tool call, not a workflow, and the coordinator
  validates its return against the same schema. A Codex caller passes the schema
  with `codex exec --output-schema`. Validation checks the shape, not whether a
  disposition is right.
- **A7 Crosswalk routing.** `tools/sota-convergence/gap_crosswalk.py` records a
  pair that no reviewer saw as `screened_out`: it has no final status and counts
  toward no gap status. A gap that has candidate pairs but no reviewed pair gets
  the gap status `screened_out`, so it is not read as `open`, which means that no
  reviewed pair addresses the gap or that no receipt names its layer. A pair
  whose gap text contains a digit always goes to review (A3). Every crosswalk
  built after 2026-10-03 takes this rule and records it in `method.routing`. The
  crosswalk's two readers, `scripts/component_matrix.py` and
  `tools/sota-convergence/gap_wave_ledger.py`, read only the retained 92bb279
  crosswalk and do not handle `screened_out` yet, so they need that change
  before they read a crosswalk built under this rule. The retained crosswalk
  keeps the 2026-09-23 rule, so `build --check` still reproduces it: its 725
  unreviewed pairs read `not_addressed`, which is a screen output, not a review
  decision. Recording them as `screened_out` (A7 alone) takes no model call. It
  needs a rule id without the digit route, and a re-record of the crosswalk, its
  page and the gap-wave ledgers that embed its sha256; 135 of its gaps would then
  read `screened_out`. Applying the digit route (A3) to it as well adds Opus
  reviews of the 369 unreviewed pairs whose gap text contains a digit.
