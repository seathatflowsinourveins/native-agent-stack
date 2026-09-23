# Contributing host evidence

This chapter is for anyone adding a new evidence-backed update from a host
this repository has not run on before: another WSL host, a macOS host,
another agent session, or CI. It uses
[`adoption/host-receipt.schema.json`](../adoption/host-receipt.schema.json)
and [`scripts/host_receipts.py`](../scripts/host_receipts.py). One receipt
records one component x one host x one lifecycle stage; it never uploads
anything, and it never certifies a platform on its own.

## 1. Who this is for

- **Another WSL host.** You have a second Linux/WSL2 x86_64 machine and want
  to confirm the `linux-wsl2-x86_64` platform's components actually work
  there, not just on the catalog's original authoring host.
- **A macOS host.** You have a real Mac workstation and want to move
  `macos-arm64` from `drafted_not_accepted` toward acceptance with real,
  reviewable evidence (a hosted CI smoke run is not this; see below).
- **Another agent session.** You are a fresh Claude or Codex session picking
  up work on a component this catalog has not yet recorded host evidence for.
- **CI.** The `validate` workflow job runs `python3 scripts/host_receipts.py
  validate` on every push and pull request; it checks receipts that already
  exist in the tree, it does not record new ones.

## 2. Evidence classes, and why a hosted CI smoke is not acceptance

Every receipt declares one `evidence_class`:

| Class | Meaning |
| --- | --- |
| `native_proven` | The command actually ran on this host against the real tool/binary, and its output was captured. |
| `local_integration` | The command ran, but against this repository's own fixtures or a synthetic stand-in, not the full real target. |
| `synthetic` | A fixture or generated input stood in for real conditions; useful for testing the protocol itself, not for accepting a platform. |

A **hosted CI smoke run** (a GitHub Actions job executing on a GitHub-hosted
runner) is real execution, but it is not a workstation. It has no persistent
user account, no durable state across runs, no GPU/Metal work, and no client
sign-in. Treat a green hosted job as `native_proven` for exactly the narrow
thing it ran (see
[`docs/tasks/2026-09-22-new-machine-install.md`](tasks/2026-09-22-new-machine-install.md)
for a worked example of this distinction on the `bootstrap-macos` job). It
does not, by itself, move a platform from `drafted_not_accepted` to
`accepted` — that requires a receipt recorded on a real second physical
machine (`host.second_physical_machine: true`), independently reviewed.

## 3. The flow

1. **Bootstrap, then work on current `main`.** Follow
   [`adoption/bootstrap.md`](../adoption/bootstrap.md) for your platform. It
   installs from the pinned release, but record and contribute from a branch
   of current `main` (`git fetch origin && git switch -c <branch> origin/main`):
   the matrix and grand-list generators on `main` can differ from the
   release's, and CI checks the generated files with `main`'s. Rebase onto
   `origin/main` again right before opening the PR and rerun step 5. Do not skip ahead to recording receipts on a host that
   has not completed the ordered adoption steps; a receipt for a tool that
   is not actually installed correctly is worse than no receipt.
2. **Choose components.** Use the component evidence matrix's needs-host list
   at `docs/component-evidence-matrix.md` (built by a separate unit; if it is
   not present yet in your checkout, pick components directly from
   [`manifests/stack.json`](../manifests/stack.json) `components[]` that have
   plain-string `commands` you can actually run) to decide which components
   most need a receipt from your host and platform.
3. **Record.** Run the recorder from the repository root. Who you are decides
   one flag: inside a Claude Code session `$CLAUDE_CODE_SESSION_ID` is the
   identity and `--identity` is refused (exit 2); a Codex session, a human
   shell or CI has no such variable and must pass `--identity` with a random
   per-session token.

   From a Claude Code session:

   ```sh
   python3 scripts/host_receipts.py record \
     --host-id <your-host-id-yyyymmdd> \
     --platform-id <linux-wsl2-x86_64|macos-arm64> \
     --component-id <a manifests/stack.json component id> \
     --stage use \
     --evidence-class native_proven \
     --from-stack-commands
   ```

   From a Codex session, a human shell or CI (generate the token once per
   session and reuse it; a new token per command is a new identity each time):

   ```sh
   identity="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
   python3 scripts/host_receipts.py record \
     --host-id <your-host-id-yyyymmdd> \
     --platform-id <linux-wsl2-x86_64|macos-arm64> \
     --component-id <a manifests/stack.json component id> \
     --stage use \
     --evidence-class native_proven \
     --identity "$identity" \
     --from-stack-commands
   ```

   `--host-id` must match `^[a-z0-9-]+-[0-9]{8}$` (lowercase, digits,
   hyphens, ending in an eight-digit date, for example
   `my-macbook-20261015`). `--component-id` accepts a `manifests/stack.json`
   id or a `catalogs/landscape/*.json` `winners[]`/`alternatives[]`
   `component_id`, including a repository-style id containing `/` (for
   example `affaan-m/ECC`) or a `candidate:*` alternative id containing `:`
   (for example `candidate:cli-cli`); `/` and `:` are each percent-escaped to
   a distinct, reversible filename token (`/` -> `%2F`, `:` -> `%3A`) only in
   the receipt's filename, never in the `id` field itself, so it stays a flat
   file under `evidence/hosts/<host_id>/` instead of crashing on a `:` a
   filesystem path segment cannot contain. `--from-stack-commands` reuses the
   component's own documented command(s) from `manifests/stack.json`; add
   explicit `--cmd "<shell command>"` flags (repeatable) instead or in
   addition when you need a different check. Pass `--second-physical-machine`
   only when this really is a second physical machine, not a fresh prefix or
   container on the catalog's existing authoring host — a receipt recorded
   without this flag can never satisfy the `component_matrix.py` macOS flip
   rule (Section 5). The receipt stores who recorded it only as a
   domain-separated sha256 (`recorded_by.identity_sha256`, plus `--model` when
   given). Inside a Claude Code session the identity is always
   `$CLAUDE_CODE_SESSION_ID` (exported by Claude Code; observed in 2.1.280),
   and `--identity` is refused there, so a session cannot record under one
   name and review under another. A Codex session, a human or CI has no such
   variable and must pass `--identity`; the recorder refuses to write a
   receipt without one rather than giving every such recorder the same
   identity. Use a random token for the session (for example the output of
   `python3 -c 'import secrets; print(secrets.token_hex(16))'`), not a name:
   the hash has a fixed public prefix, not a secret salt, so a guessable name
   can be recovered and every `--identity codex` is the same identity.
   `--identity` is NFKC-normalized and case-folded. A tool launched from a
   Claude Code session inherits its session id and counts as that session.
   The receipt also records the component version it ran in `tool_versions`:
   the landscape winner pin when every layer that selects the component
   agrees on it, else the `manifests/stack.json` version. Pass
   `--component-version` when neither applies or the host ran something else;
   a version without a digit (such as `unpinned`) is refused, and so is one
   that matches none of the component's current winner pins (it would never
   count), unless you pass `--allow-unbound-version`. Multi-part pins such
   as `2.0.0rc5 (tag ...)` must be given as written. A receipt only
   counts toward a winner's status while that version equals the winner's
   current pin in full, so a pin bump retires older receipts until someone
   re-records. The
   recorder runs your commands with a bounded timeout,
   sanitizes `$HOME` to `~` and your username to `<user>` in the captured
   excerpt, writes the receipt under `evidence/hosts/<host_id>/`, and
   registers it in `manifests/evidence.json`. It never uploads anything over
   the network. `--os`/`--architecture` default to the actual host's values
   but can be overridden; nothing in this repository can verify from the
   receipt's JSON alone that a claimed `platform_id`,
   `second_physical_machine` or `os`/`architecture` combination is honest —
   independent review (step 8) is what a reader relies on for that. Reviewer
   and recorder identities are self-declared too: the checks below stop a
   session from reviewing its own receipt by accident or by default, not a
   contributor who deliberately passes a false `--identity`.
4. **Sanitize and scan.** Re-read the receipt file yourself before opening a
   PR: sanitization is best-effort, not a guarantee. Then run the guarded
   secret scanner over just the files you touched:

   ```sh
   gitleaks dir evidence/hosts/<your-host-id> --no-banner --redact
   ```
5. **Refresh the derived evidence matrix, if present.** Every new receipt or
   review can change `docs/component-evidence-matrix.md`'s per-platform
   `host_receipts` counts and `latest` timestamp, so `component_matrix.py
   --check` (run in CI) would otherwise fail on a stale checked-in copy.
   Skip this step only if your checkout does not yet have
   `scripts/component_matrix.py`.

   ```sh
   python3 scripts/component_matrix.py --write
   python3 scripts/new_host_grand_list.py --write
   ```

   The second command refreshes the new-host grand list, which joins the matrix; its `--check` also
   runs in CI.

   `--write` recomputes and writes both
   `catalogs/landscape/component-evidence-matrix.json` and
   `docs/component-evidence-matrix.md`, and re-registers both files' hashes
   in `manifests/evidence.json` for you (it calls the same
   `scripts/host_receipts.py` `register_file` helper that `record` and
   `review` use), so you do not need a separate rehashing step. Commit both
   changed files alongside your receipt.
6. **Validate.**

   ```sh
   python3 scripts/host_receipts.py validate
   python3 scripts/validate.py
   python3 scripts/component_matrix.py --check
   ```

   The first command checks your new receipts against the schema rules
   (platform/component identity, id/path coherence, pass/exit coherence,
   registration, reviewer independence, dates no later than 15 minutes past
   the validating machine's clock, and private-content scanning). The second is this
   repository's general publication validator; it also re-checks that every
   file you touched is correctly hash-registered. The third confirms step 5's
   `--write` is current and enforces the macOS-acceptance flip rule (Section
   5 below).
7. **Open a PR.** Rebase onto `origin/main` and rerun step 5 first. Use the [PR template](../.github/pull_request_template.md)'s
   "Host evidence" section. List each receipt's path and evidence class.
8. **Independent review.** Someone other than the recorder — another agent
   session, the Codex review lane, or a human — reviews the receipt (reads
   the commands and output excerpt, and if practical reproduces at least one
   command) and appends a review:

   ```sh
   python3 scripts/host_receipts.py review \
     --receipt evidence/hosts/<host_id>/<receipt-id>.json \
     --kind independent_session \
     --ref "<how to find/reproduce this review>" \
     --verdict agree
   ```

   `--kind` is one of `independent_session`, `codex_lane`, or `human` for a
   real independent reviewer (`self` is reserved for the recorder's own
   automatic entry, written once by `record`). The reviewer's identity comes
   from `$CLAUDE_CODE_SESSION_ID` or `--identity`, exactly as for `record`,
   and is stored hashed as `reviewer.identity_sha256`. `review` refuses a
   non-`self` review whose identity equals the receipt's `recorded_by`, and a
   receipt with no `recorded_by` (recorded before 2026-09-23) cannot take an
   independent review until it is re-recorded. `validate` rejects the same
   cases in CI, and a review dated before the observation. Only each
   reviewer's latest verdict counts, and any standing `disagree` or
   `needs_changes` vetoes the receipt however many others agree; a reviewer
   withdraws a dissent by appending a newer review. A dissent that fails
   those checks (no reviewer, the recorder's own identity, or dated before
   the observation) still vetoes and cannot be withdrawn. Only the identity
   that dissented can withdraw it; a Claude session's dissent can be
   withdrawn only by that same session, and no other review, a maintainer's
   `human` review included, overrides it. Once that session is gone, the
   supported path is to address the dissent and record a fresh receipt,
   which starts with no reviews. A subagent or tool launched from the
   recording session inherits its session id and is refused as the recorder.
   An independent review therefore runs in a separate session, a Codex
   session or a person's shell. A process that has no
   `$CLAUDE_CODE_SESSION_ID` passes `--identity` (for example
   `env -u CLAUDE_CODE_SESSION_ID python3 scripts/host_receipts.py review
   ... --identity <token>`). That identity is self-declared, so use it only
   for a reviewer that really is separate. `review` refuses to run when this
   host's clock is behind the receipt's `observed_at_utc`, because the review
   would be dated before the observation. This step re-registers
   the file's hash after the review is appended; rerun step 5's
   `component_matrix.py --write` afterward, since a new review can change the
   matrix's receipt counts and derived status.
9. **Merge.** A maintainer merges once CI's
   `python3 scripts/host_receipts.py validate` step is green and at least one
   independent review is present or explicitly requested in the PR (the
   checklist item covers "requested" for cases where review has to happen
   after merge, for example because only one contributor currently has
   access to that platform).

## 4. How landscape verdicts and gaps get updated later

Host receipts are raw per-host evidence. They feed, but do not replace, three
separate downstream processes that a later unit or maintainer runs, not this
recorder:

- **`tools/sota-convergence/record_verdicts.py`** turns reviewed evidence
  (including host receipts once enough of them exist for a layer) into a
  dated `catalogs/landscape/*.json` `winners[]` entry, through its own lane
  process — a host receipt alone is not a verdict.
- **`tools/sota-convergence/gap_crosswalk.py`** regenerates the crosswalk
  between open gaps and recorded evidence; rerun it after adding receipts
  that close or narrow a gap so the crosswalk reflects the new evidence
  rather than going stale.
- **The catalog-freshness report** (`docs/github-automation.md`'s
  `catalog-freshness.yml` lane, built on
  `tools/sota-convergence/github_freshness.py`) is a separate, report-only,
  scheduled job that compares pinned versions against upstream; it does not
  read `evidence/hosts/` and a host receipt does not feed it.

Use `python3 scripts/host_receipts.py summary --json` to see, per component
and platform, how many passing and failing receipts exist, how many have an
independent review or a standing dissent, and how old the latest one is
(`--max-age-days`, default 180, flags old ones; age is reported only here,
never in the generated matrix, so `component_matrix.py --check` stays
deterministic) — useful input for deciding whether a layer has
enough evidence to bring to one of the processes above, but not a substitute
for running them.

## 5. What never changes through a host receipt alone

- **`catalogs/landscape/*.json` `winners[].platform_status`.** A winner's
  per-platform `platform_status` field is written by the recorded verdict
  process above, not by this recorder. Both the verdict recorder and the
  validators derive it through one function,
  [`scripts/platform_status.py`](../scripts/platform_status.py): the
  validators, and the verdict recorder
  (`tools/sota-convergence/record_verdicts.py`) for every platform of a new
  wave. A Mac's merged receipts raise what a row may declare, and the row's
  next re-record writes it. `scripts/landscape.py` and
  `scripts/component_matrix.py --check` (both run in CI) reject a declared
  `macos-arm64` status that claims more than the receipts support; a weaker,
  not-yet-re-recorded status is allowed.

  A *qualifying* receipt, on either platform, is one for that `component_id`
  that is `result: pass`, `evidence_class: native_proven`, stage `use` or
  `install`, bound to the winner's current pin, independently reviewed (step
  8) with no standing dissent, declares `host.second_physical_machine: true`,
  and has `host.os`/`host.architecture` consistent with
  `adoption/manifest.json`'s `platform_profiles[]` entry for that platform id.
  A `native_proven` fail at `use` or `install` that is the latest receipt for
  its host and stage is *blocking*, whatever its review, until that host
  records a later pass. The two platforms then differ:

  - **`macos-arm64`.** `accepted` needs a qualifying receipt and no blocking
    fail; there is no other route. `conditional` needs a pin-bound,
    non-`synthetic` pass from a declared second physical machine with no
    standing dissent; `not_established` means pin-bound receipts exist but
    none is such a pass; otherwise `untested`. A receipt recorded and reviewed
    entirely on a single host, with `second_physical_machine` left at its
    default `false`, cannot make a macOS winner `accepted`.
  - **`linux-wsl2-x86_64`.** `accepted` needs a qualifying receipt, or a
    winner whose own `evidence_class` is `native_proven` or
    `measured_comparison` and whose `evidence_refs` cite at least one
    `evidence/` file registered in `manifests/evidence.json` (not a sealed
    layer-verdict packet, lane return or adjudication), and in both cases no
    blocking fail. The second route needs no host receipt and no second
    physical machine, so a single WSL host's receipt is not what makes a
    Linux winner `accepted`; it can only add a passing receipt (towards
    `conditional`) or a blocking fail. Otherwise `conditional` or
    `not_established`, as that module's docstring lists.

  CI currently enforces the derived ceiling on every platform for rows a new
  wave records, but only on `macos-arm64` for the older grandfathered rows:
  `ENFORCED_PLATFORMS` in [`scripts/landscape.py`](../scripts/landscape.py)
  and the comment above it say Linux joins that set when the grandfathered
  rows are re-recorded.
- **`adoption/manifest.json` `platform_profiles[].status`.** This is a
  separate field, owned by another unit, and moving a platform from
  `drafted_not_accepted` to `accepted` is presently a maintainer judgment
  call informed by the matrix above (component coverage, a real second
  physical machine, independent review) rather than a rule any script in
  this repository enforces or gates automatically — do not assume opening a
  PR that satisfies the `component_matrix.py` flip rule alone will flip this
  field, and do not edit it yourself as part of a host-evidence PR.

## Local vs. CI

`scripts/host_receipts.py validate` runs identically on your host and in the
`validate` GitHub Actions job (`.github/workflows/validate.yml`); there is no
separate CI-only code path. `record` and `review` are local-only: nothing in
CI records or reviews receipts on your behalf.
