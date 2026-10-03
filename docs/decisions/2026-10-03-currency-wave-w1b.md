# Foundation currency wave W1b — 2026-10-03

## Outcome and north-star action

Integrate the two W1-r2 moves authorized by the W1b build contract: Grafana
13.2.2 → 13.2.3 and agent-browser 0.38.1 → 0.38.2. This keeps the foundation's
observation and browser recipes current for US-equities research and historical
simulation. This unit changes portable repository pins and evidence; host
activation and a new machine's acceptance remain separate operations.

The owned worktree starts at `dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e` on
`foundation/currency-w1b-20261003`. The coordinator owns committing and pushing.
The configuration owner's new-WSL files, definitive manifest and client map, all
trading blueprint paths, and sealed historical records stay with their owners.

## Selected upstream sources and qualification

| Component | Selected source | Verified artifact SHA-256 | Recorded qualification |
| --- | --- | --- | --- |
| Grafana 13.2.3 | [grafana/grafana v13.2.3](https://github.com/grafana/grafana/releases/tag/v13.2.3), public tag commit `6193dc03311b631b9727b560d24369e683dc396e` | `6107ad27016296aac38e0d7ffa8753ab540b5541ad27e94790f771289d733235` | [Qualification receipt](../../evidence/receipts/grafana-1323-qualification-20261003.json) |
| agent-browser 0.38.2 | [vercel-labs/agent-browser v0.38.2](https://github.com/vercel-labs/agent-browser/releases/tag/v0.38.2), commit `39a74c70d7759d5a6de7a22c04570bb626bbd081` | `2bb1d6e4660b2a109c912c8bb552f727125dbcd681c6d1eefc1af573b4546c49` | [Offline readiness receipt](../../evidence/receipts/agent-browser-0382-qualification-20261003.json) |

Grafana's release notes list fixes for
[CVE-2026-13719](https://grafana.com/security/security-advisories/cve-2026-13719),
[CVE-2026-13720](https://grafana.com/security/security-advisories/cve-2026-13720) and
[CVE-2026-81841](https://grafana.com/security/security-advisories/cve-2026-81841).
W1-r2 records all three as medium severity. The public tag commit and packaged
build commit differ: `grafana server --version` reports
`90ffed056f0884267356c12a0eeb72a022af53f1`, branch `release-13.2.3#patched`.
Both identities are retained. Integrity relies on the publisher's HTTPS
checksum page and sidecar; W1-r2 found no detached signature or attestation in
the named sources. The supported route remains
`observability/backends/pins.json` consumed by `observability/backends/install.py`.
There is no Grafana row in `adoption/pins-linux-x86_64.json`; adding a competing
installation route would not satisfy this component's existing recipe.

W1-r2 ran Grafana's repository installer in a scratch prefix, then locally
authored synthetic checks in a private network namespace. Retained native
outputs show version 13.2.3, a provisioned 26-panel dashboard, anonymous writes
rejected with HTTP 403, 36/36 Prometheus/Loki query targets, and a 13.2.2 database
reopened by 13.2.3 with 719 migration-log rows before and after. These are
integration observations, not Grafana's unchanged upstream test suite or a
restart onto the host's real database. Browser rendering, production cardinality
and Grafana-managed alerting remain untested.

Reachability for all three CVEs is assessed only against repository provisioning.
The templates provision no Grafana-managed alert rules or Editor accounts and
configure proxy-access datasources without stored credentials; they establish
neither the absence of UI-created state nor the host's exposure. The supported
upgrade preserves the database (`observability/backends/configure.py:113-119`).
Existing users and Editor memberships, alert rules, shared dashboards and sharing
tokens, and additional datasource/credential configuration were not inspected.
Checking that preserved live database remains an open host item in the
[corrected qualification record](../../evidence/artifacts/currency-wave-w1b-20261003/grafana/qualification-record.json).

agent-browser's npm tarball integrity matches registry SHA-512 and SHA-1;
W1-r2 records a verified registry signature and attestation, and seven bundled
native binaries matching release asset digests. Its install exited 0 and
reported `agent-browser 0.38.2`. Offline help, skills and config checks passed
against the 0.38.1 control; skills outputs were identical. The
[release comparison](https://github.com/vercel-labs/agent-browser/compare/v0.38.1...v0.38.2)
and the recorded independent review cover the documented recipe's use path.
The live fixture workflow, browser download and WSL2 Chrome launch were not run.
The contract explicitly accepts a version check and offline command here.
The receipt is classified as `compatibility_attempt`, matching
`scripts/validate.py`'s receipt kinds. Its 0.38.2 evidence covers installation,
version and offline readiness; the retained browser lifecycle evidence predates
this pin and supplies no new 0.38.2 browser acceptance.

W1b independently repeated both components' version commands, agent-browser's
offline `skills list`, both artifact hashes, the live Grafana sidecar and npm
dist metadata. Eight fresh `gh api` calls use the existing snapshot's method:
repository metadata, latest stable release, selected commit and release-tag
commit for each component. All eight exit 0, both latest releases match the
selected versions, and both source resolutions match the pins. Prior snapshot
checks remain as dated observations; untouched rows and the original summary
retain their earlier observation scope. The new observations are in
[integration-commands.json](../../evidence/artifacts/currency-wave-w1b-20261003/integration-commands.json)
and each component's `github-metadata.json`.

## Holds and superseded qualification gaps

The original `W1-moves.json` held five pins for separate requalification:
Grafana, agent-browser, headroom, Dagu and RTK. W1-r2 supersedes the original
qualification gaps for those five, moving the first two and retaining the
following three. The complete W1-r2 review reasons and the original W1 excerpts
are preserved in
[review-decisions.json](../../evidence/artifacts/currency-wave-w1b-20261003/review-decisions.json).
Each original W1 hold string was truncated at 600 characters. The retained
sanitized copies are shorter where role markers replaced host paths, and the
Dagu copy omits its incomplete trailing host-path fragment. These excerpts are
not represented as complete judge records.

| Component | Retained / candidate | Reason and next decision-changing condition |
| --- | --- | --- |
| headroom | 0.37.0 / 0.39.1 | Requalification passes integrity, installation and exact retrieval, but still reports an omitted ERROR that is among the kept rows. The relevant [v0.39.1 log compressor](https://github.com/headroomlabs-ai/headroom/blob/v0.39.1/headroom/transforms/log_compressor.py#L461-L487) is unchanged; the established omission-count gate is unmet. Recheck a release containing the [#3828 fix](https://github.com/headroomlabs-ai/headroom/pull/3828), using omitted-line counts, required facts and exact retrieval, or a measured log-input answer-quality comparison. Cooldown is not the blocker. |
| Dagu | 2.16.6 / 2.18.1 | Under `auth: none`, the cross-run artifacts route remains readable: the candidate returns a listing where 2.16.6 returned 404. The [v2.18.1 API](https://github.com/dagucloud/dagu/blob/v2.18.1/api/v1/api.yaml) and recorded config schema provide no disabling permission. The trading lane owns the cutover, authentication and SIGKILL-recovery justification. The DAG-index migration also needs a coordinated service change. |
| RTK | 0.50.0 / 0.51.0 | The [0.51.0 changes](https://github.com/rtk-ai/rtk/releases/tag/v0.51.0) add `--shell`, which the repository's secret-path guard does not parse, and fold `grep -l` / `rg -l` filenames, invalidating path consumers and frozen exactness checks. The review rejects the earlier comment-only repair and soft-check characterization: `scripts/native_token_ci.py` raises on failed checks. A move needs tested guard parsing and hook checksum updates, a native pipe-rewrite probe and an exclusion/recipe decision, refrozen checks and corrected exception documentation. |
| beads | 1.3.0 / 1.3.1 | The contract retains the hold for the `bd close` blocked-state recheck regression. Current upstream [#7030](https://github.com/gastownhall/beads/issues/7030) is open and describes the release branch omitting #6876. A regression-bearing release is outside the clean-release cooldown waiver. The original seven-day window ends 2026-10-07T23:37:36Z; elapsed time alone does not qualify this defect. |
| agentsview | 0.43.0 / 0.44.0 | The contract retains the behavior/recipe-rewire hold. [v0.44.0 release notes](https://github.com/kenn-io/agentsview/releases/tag/v0.44.0) describe automated classification for every `codex exec`, injected-context parsing changes and rejection of unknown `[vector]` keys. Qualify the selected archive/project/session/filter population and rewire its recipe before moving the pin. |

DuckDB and skfolio remain the trading lane's independent requalification work;
this unit makes no selection or edits for them. MCP Inspector is explicitly
marked ignored and outside this wave in the W1b contract, so its pin and receipt
are not changed.

## Cooldown, alternatives and overturn condition

The user ended the seven-day cooldown for clean releases on 2026-10-03. The
waiver permits a stable published release with verified integrity, installation,
native smoke and no unmatched regression affecting the documented use; it does
not waive qualification. agent-browser was published 2026-10-01T21:44:28Z and
Grafana 2026-09-29T09:02:18Z. Grafana is also a security release. The independent
W1-r2 judgments accepted both within their recorded scope.

The alternatives were retaining the old pins or widening this unit into live
host/browser acceptance and the other candidates' recipe changes. The contract
selects the two already-qualified moves and bounded evidence integration.
Reopen a move for a publisher digest mismatch, a new applicable advisory, or a
reproducible regression on the documented recipe. A maintained replacement must
pass that same recipe and its explicit scope before replacing the selection.
Version recency, reviewer agreement and install success alone do not settle a
broader merit comparison.

## Verification corrections and completeness critic

This bounded integration uses the installed search-first skill's known-source
path and existing native recipes; it introduces no runner or installation
abstraction. Scoped ai-memory search with `limit=2` returned no exact component
or cooldown result. A broadened search and exact page read recovered the older
workstation refresh decision, then the current repository records and upstream
sources settled the new scope. The installed CLI search help exposes no
`pin_first` option; this observation is limited to that installed CLI help.

Corrections retained with verification paths:

- The Grafana pin-site lead marked `docs/stack.md` live, but its own heading
  explicitly dates it to September 19, 2026. The independent `git grep` scan and
  header read classify the whole file as historical, so both old rows retain
  their original bytes. Other dated catalogs, receipts and sweep manifests also
  keep their original bytes. Configuration-owner pin sites are handed back to
  that owner.
- The first native npm metadata read failed with EROFS because its default
  cache is outside this worker's writable roots. The supported `--cache` option
  moved that command's cache into the integration temp directory; the retry
  exited 0. Both returned outputs remain recorded.
- The web `open` operation returned HTTP 400 for an unsupported operation.
  Native `gh api` and publisher HTTPS checksum reads supplied the primary
  sources; no web-page success is claimed.
- The old Beads repository locator redirects: the current issue response names
  `gastownhall/beads`, and this record uses its canonical issue URL.
- An assumed `tools/adoption/install_pin.py` locator did not exist (the native
  `rg` read exited 2). Task-filtered `rg --files` resolved the actual installer
  to `adoption/bootstrap-linux.sh`; its `install_npm` at lines 397–419 downloads
  and verifies the pinned archive, installs it with npm and links `bin/*`.
  npm SHA-512 integrity remains in the pin's established `install_note` shape.

R645 corrects three evidence overstatements: offline agent-browser readiness
had been labelled `native_cli_e2e`; selected Grafana 13.2.3 had been shown beside
a host restart claim belonging to 13.2.2; and missing repository provisioning
had been treated as absence of live Grafana rules, Editors and shared state.
The correction paths are the validator's `RECEIPT_KINDS`, the retained command
outputs, and the unchanged database/provisioning paths in `configure.py` and its
templates. The acceptance artifact retains the fresh release and GHSA API
responses used to verify the pinned upstream sources. R645's scoped ai-memory
CLI searches (limit 2, narrow then component-only) returned no relevant result.

The installed Gitleaks launcher could not create its lock on the read-only
host runtime directory; setting `XDG_RUNTIME_DIR` did not change its fixed
`/run/user` path, as inspection of `adoption/tools/gitleaks-guarded` confirmed.
The staged scan therefore uses the installed upstream 8.30.1 binary directly,
the repository pre-commit command, and a temporary Git index/object directory.
Both failed help attempts and the native command's returned output are retained
in the acceptance artifact. The original index remains untouched.

The first R645 test run used a temporary directory inside the checkout and hit
the sweep harness's existing outside-repository guard
(`tools/sota-convergence/landscape-sweep/sweep_common.py:78-92`). The failed
outputs are retained. Moving `TMPDIR` to this session's writable builds
workspace, outside every Git repository, made the existing focused test and
the full required five-module command pass. No harness or test was changed.
The first final publication check also rejected untracked R645 scratch logs
and temporary Git objects inside the checkout. All R645 scratch state was then
moved to the owned builds workspace; the failed validator output is retained
before the corrected final run. The publication checker itself is unchanged.

The completeness critic checked live pin sites against both facts packets and
an independent `git grep`, the supported installer routes, source commits and
artifact integrity, dated/current distinctions, receipt indexing and generated
report ownership. No other candidate class is admitted by this contract. The
next lifecycle sweep should cover agent-browser's live use/cleanup on the target
host and Grafana browser rendering/production queries/real-database restart;
RTK parsing/pipeline exactness, headroom log required-facts/counts and agentsview
archive migration stay with their held units. Dagu authentication and recovery
stay with the trading owner. R645 corrects the anonymous-access sentence in
`observability/backends/README.md` to match the repository's anonymous Viewer
and disabled sign-up configuration.

Required repository acceptance is retained in
[acceptance.json](../../evidence/artifacts/currency-wave-w1b-20261003/acceptance.json),
including R645's commands, exit codes, returned outputs and final validation.
The R645 repair inventory is recorded there as well. Changed registered evidence is refreshed with
`scripts/host_receipts.py`'s `register_file`; both report generators use their
native `--write` mode, and `scripts/build_ecosystem.py` remains check-only.

R645's completeness critic checked receipt kinds and their stack/audit/index
mirrors, all five retained stdout files and their producing commands, the
selected/deployed Grafana distinction, every CVE reachability statement, and
publication hash registration. It found no additional repair within this
contract. The next host lifecycle sweep must inspect the preserved Grafana
database before assessing exposure and must qualify 0.38.2 browser use and
cleanup. Repository validation and the staged secret scan do not close those
host items. The coordinator retains the hot-file commit ordering, PR labels,
trading acknowledgement and full-suite CI checks.
