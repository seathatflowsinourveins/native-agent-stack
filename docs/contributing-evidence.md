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

1. **Bootstrap.** Follow [`adoption/bootstrap.md`](../adoption/bootstrap.md)
   for your platform. Do not skip ahead to recording receipts on a host that
   has not completed the ordered adoption steps; a receipt for a tool that
   is not actually installed correctly is worse than no receipt.
2. **Choose components.** Use the component evidence matrix's needs-host list
   at `docs/component-evidence-matrix.md` (built by a separate unit; if it is
   not present yet in your checkout, pick components directly from
   [`manifests/stack.json`](../manifests/stack.json) `components[]` that have
   plain-string `commands` you can actually run) to decide which components
   most need a receipt from your host and platform.
3. **Record.** Run the recorder from the repository root:

   ```sh
   python3 scripts/host_receipts.py record \
     --host-id <your-host-id-yyyymmdd> \
     --platform-id <linux-wsl2-x86_64|macos-arm64> \
     --component-id <a manifests/stack.json component id> \
     --stage use \
     --evidence-class native_proven \
     --from-stack-commands
   ```

   `--host-id` must match `^[a-z0-9-]+-[0-9]{8}$` (lowercase, digits,
   hyphens, ending in an eight-digit date, for example
   `my-macbook-20261015`). `--from-stack-commands` reuses the component's own
   documented command(s) from `manifests/stack.json`; add explicit `--cmd
   "<shell command>"` flags (repeatable) instead or in addition when you need
   a different check. Pass `--second-physical-machine` only when this really
   is a second physical machine, not a fresh prefix or container on the
   catalog's existing authoring host. The recorder runs your commands with a
   bounded timeout, sanitizes `$HOME` to `~` and your username to `<user>` in
   the captured excerpt, writes the receipt under `evidence/hosts/<host_id>/`,
   and registers it in `manifests/evidence.json`. It never uploads anything
   over the network.
4. **Sanitize and scan.** Re-read the receipt file yourself before opening a
   PR: sanitization is best-effort, not a guarantee. Then run the guarded
   secret scanner over just the files you touched:

   ```sh
   gitleaks dir evidence/hosts/<your-host-id> --no-banner --redact
   ```
5. **Validate.**

   ```sh
   python3 scripts/host_receipts.py validate
   python3 scripts/validate.py
   ```

   The first command checks your new receipts against the schema rules
   (platform/component identity, id/path coherence, pass/exit coherence,
   registration, and private-content scanning). The second is this
   repository's general publication validator; it also re-checks that every
   file you touched is correctly hash-registered.
6. **Open a PR.** Use the [PR template](../.github/pull_request_template.md)'s
   "Host evidence" section. List each receipt's path and evidence class.
7. **Independent review.** Someone other than the recorder — another agent
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
   automatic entry, written once by `record`). This step re-registers the
   file's hash after the review is appended.
8. **Merge.** A maintainer merges once CI's
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
and platform, how many passing receipts exist and how many of those passes
have an independent review — useful input for deciding whether a layer has
enough evidence to bring to one of the processes above, but not a substitute
for running them.

## 5. What never changes through a host receipt alone

- **`catalogs/landscape/*.json` `winners[]`.** Only the recorded verdict
  process above (with its own review and evidence-class rules) changes a
  winner. A single host receipt, however good, is input to that process, not
  a shortcut around it.
- **`adoption/manifest.json` `platform_profiles[].status`.** Moving a
  platform from `drafted_not_accepted` to `accepted` needs the matrix rule
  documented in `docs/component-evidence-matrix.md` (coverage across the
  platform's required components, on a real second physical machine, with
  independent review) — not a single passing receipt, and not a hosted CI
  smoke run (Section 2).

## Local vs. CI

`scripts/host_receipts.py validate` runs identically on your host and in the
`validate` GitHub Actions job (`.github/workflows/validate.yml`); there is no
separate CI-only code path. `record` and `review` are local-only: nothing in
CI records or reviews receipts on your behalf.
