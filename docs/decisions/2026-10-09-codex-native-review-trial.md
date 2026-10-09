# Codex native review and the Claude companion bridge

The verdict is **retain-bridge**. Codex's native reviewer completed a real
pull-request delta directly, and the pinned Claude companion completed the
same delta through Codex's native app-server reviewer. This establishes a
usable direct path for a Codex caller. It does not establish that removing the
Claude integration preserves its dispatch, session lifecycle or other commands.
No client configuration or adoption default changes follow from this trial.

## Sources and scope

- [openai/codex rust-v0.162.0](https://github.com/openai/codex/tree/c1382380de69521303b416720a52f42d51af6248),
  commit `c1382380de69521303b416720a52f42d51af6248`:
  `codex-rs/exec/src/cli.rs`, `codex-rs/core/src/tasks/review.rs:105–141`,
  and the [release](https://github.com/openai/codex/releases/tag/rust-v0.162.0).
  The reviewer clones configuration, supplies the review rubric, disables web
  search and collaboration features, and uses `review_model` or the current
  model. This capability is present at the pin; the release notes do not claim
  that 0.162.0 introduced it.
- [openai/codex-plugin-cc v1.0.6](https://github.com/openai/codex-plugin-cc/tree/db52e28f4d9ded852ab3942cea316258ae4ef346),
  commit `db52e28f4d9ded852ab3942cea316258ae4ef346`:
  `plugins/codex/commands/review.md`, `scripts/lib/codex.mjs:1002–1054`
  beneath that plugin, and `scripts/lib/app-server.mjs:189–195`.
  The companion already calls `review/start` on an ephemeral, read-only native
  Codex thread. It is an integration with that reviewer, rather than a second
  independently implemented review engine.
- [Official OpenAI CLI reference](https://developers.openai.com/codex/cli/reference/#codex-review)
  documents the base, commit and uncommitted targets. The inspected 0.162.0
  executable also exposes `codex exec review`, JSON events and ephemeral runs.

The sweep was a discovery lead. Its named `FINAL.md` was rehashed as
`77e17817d8ecc8e53329ac32303ece8dc4e86eaf67cba1e3ae36196aa328a109`
on October 9; the earlier handoff digest is superseded. The tested behavior
and pinned upstream source determine this decision.

## Real pull-request trial

The corpus is [PR882](https://github.com/seathatflowsinourveins/native-agent-stack/pull/882),
base `a484989a43f70ff2575b6fb054cf00c9834e7679`, head
`f4965224b569325a8ab41c2a97b8d71157d630c6`. Its five-file delta contains the
ambiguous-hostname refusal, five regression cases, and documentation/evidence
updates. The assigned trial checkout was temporarily detached at this head;
the original branch was restored afterward. The source PR was not changed.

Both reviewer invocations used the extracted 0.162.0 executable, the same
keyless OmniRoute provider and `cx/gpt-6.1-sol`, Max effort, standard service
tier (`default`). A lane-owned process configuration and plugin-data prefix
isolated the trial from the owner's authentication and client configuration.
The four inspected installed companion entrypoint/library files match the
v1.0.6 source checkout byte for byte.

| Invocation | Returned result | Elapsed seconds | Largest sampled process-tree PSS |
| --- | --- | ---: | ---: |
| Native `codex exec review --base <base>` | Exit 0; no actionable regressions | 146.443 | 198,901 KiB |
| Vendor companion `review --wait --scope branch --base <base> --model cx/gpt-6.1-sol --json` | Outer exit 0 and nested Codex status 0; no actionable regression | 116.082 | 223,104 KiB |
| Fresh general session, natural-language review intent | Exit 0; no actionable regressions; no invocation of the dedicated review command | 190.783 | 123,396 KiB |

These are host observations, not a performance ranking. The initial native
invocation made wider ancestor and installed-dependency reads. Before the
bridge and fresh-session runs, the isolated configuration received explicit
checkout-only instructions. Workloads and inspection scope therefore differ.
The native path's final response reports that it did not rerun the suite; the
bridge reports five checks using an in-memory retention substitute. These
model reports do not replace the separately executed behavior tests below.
The native JSON event stream reports zero token usage; that is an uninformative
transport report, not evidence of zero provider consumption or cost.

PSS was sampled once per second from each root and its descendants using
`/proc/<pid>/smaps_rollup`. The largest sampled sums are not continuous peaks
or general memory guarantees. Review agreement is not an independent oracle:
both entrypoints reach the same upstream reviewer and configured model.

The fresh session received the base and a read-only review request without a
command, plugin or tool name. It inspected the delta and performed local
in-memory checks, but did not invoke `codex review`, `codex exec review` or an
app-server `review/start` operation. A general agent responding to review
intent is therefore proven; automatic routing to the dedicated native
reviewer is not. This adoption-stage gap remains open.

## Quality, installation and inverse

The pinned Codex release run
[37812662295](https://github.com/openai/codex/actions/runs/37812662295)
completed successfully. The tag-commit check listing returned 55 checks,
53 successful and two skipped; these are release/build checks, not proof
that a local Rust unit-test suite ran. The maintained default branch had a
new October 9 commit at the research read. No local Rust build is claimed.

The companion's default branch still resolves to the v1.0.6 commit, dated
July 8. Its recorded CI file uses version consistency, TypeScript build and
the Node test suite. The retrieved tag-commit runs were Copilot review runs,
not proof that that suite ran in CI. Its maintenance signal alone does not
establish a broken review integration.

The unchanged vendor `npm run check-version` passed. An initial `npm test`
returned 90 passes and one failure because the trial's `CLAUDE_PLUGIN_DATA`
override conflicts with `tests/state.test.mjs:14`, whose default-directory
case assumes the variable is unset. The vendor suite was rerun with
`env -u CLAUDE_PLUGIN_DATA nice -n 10 ionice -c2 -n7 timeout 600 npm test`:
**91 tests passed, zero failures or skips**. No vendor source or expectation
was modified. `claude plugin validate <pinned plugin directory>` also passed.

The source PR's `tests.test_research_dispatch_exact_queries` ran separately
under `timeout 600`: 32 cases, 30 passed and two skipped. The two dependency
checks are unqualified in that Python environment. Model-generated
in-memory substitutes remain separate observations.

The retained official full-package archive was extracted into the lane-owned
trial prefix using the vendor's standalone distribution. Its SHA256 is
`4f573944c1d2059109d75a2f4d0cc9c03697288224a5e407717a9de98fc010c5`;
the executable SHA256 is
`50ed828f357c655a3c82054d346cab8434f24901f14ec19b8267571bdd008b38`.
Both were verified, and the native version check returned `codex-cli 0.162.0`.
This reuses the retained release artifact; the prior rollout and canaries
were not repeated. The ordinary PATH wrapper still selects 0.161.0, so this
trial used the pinned executable explicitly and did not change that wrapper.

The installation inverse removed only the trial's extracted runtime and
process-local configuration. Absence was checked. The companion's dedicated
broker was terminated through its upstream SIGTERM shutdown handler; its
process and socket were verified absent. The earlier versioned installation,
installed plugin and owner's client configuration remain available.

## Disposition and overturn condition

The trial supports using the native command for a Codex-local review. It
does not support a blanket bridge replacement or ADOPT-NOW: automatic
dedicated-review routing remains unproven, and no Claude frontend, stop gate,
rescue/task, session transfer or concurrent-session parity run was performed.
The comparison did not exercise authentication, a live extraction transport
or CI review posting. The dedicated companion broker and its shutdown were
exercised; concurrent-session broker ownership remains unqualified.

Reopen replacement when a vendor-supported Claude-to-native route preserves
the required bridge surface on the same pinned delta and a fresh unnamed
request reaches the dedicated reviewer. Use equivalent scope/instructions,
retain upstream test results, and measure session PSS. Configuration removal
remains a separately reviewed owner/command-center decision.

Credential-store findings and a schematic owner-only setting proposal are in
[the research note](../codex-credential-store-research-20261009.md).
The [receipt](../../evidence/artifacts/codex-review-trial-20261009/receipt.json)
binds the retained native outputs; [owner proposals](../../evidence/artifacts/codex-review-trial-20261009/owner-proposals.md)
are unapplied. This trial PR remains draft for both designated reads, CI,
the pre-cue tool and an explicit command-center cue.
