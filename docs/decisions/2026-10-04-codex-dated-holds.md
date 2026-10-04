# Codex dated holds: one pin row, a host-agnostic hold (2026-10-04)

R6, "per-host Codex pins", as the coordinator approved it on 2026-10-04: a dated hold on the existing Codex pin
row, not a pin per host.

## Context

`adoption/pins-linux-x86_64.json` has one `codex` row for every Linux host. #626 (`f77a35eb2`) moved it from
0.159.3 to 0.160.0. Hosts that had not switched stayed on 0.159.3 under a dated landing exception, review item X18,
recorded only in a PR comment. `scripts/adoption_status.py --pinned-versions` then reported their Codex as drift,
with no reason or end date in the repository.

## Decision

1. The `codex` row carries `holds`, an array with one entry: `version` 0.159.3, `until` 2026-11-04, `reason`
   "X18: hosts not yet switched stay on 0.159.3 until retired (#626 landing exception)", the 0.159.3 wrapper
   tarball's `url` and `sha256`, a `checksum_ref`, and a `platform_dependency` for `@openai/codex@0.159.3-linux-x64`
   in the row's own shape. The URL and SHA-256 are the row's values before `f77a35eb2`, introduced by `85543efe5`
   (#580). On 2026-10-04 the tarball downloaded from the npm registry matched them and the registry's SHA-512
   integrity and SHA-1. No earlier record carries the platform package's hashes, so they are first recorded here,
   from the registry. Its SHA-512 and SHA-1 equal the registry's; the SHA-256 and the executable's SHA-256 are
   computed over the same download.
2. The bootstrap is unchanged: it installs only the row's version. A hold is status data, never an install target.
3. With `--pinned-versions`, a probe that exits 0 naming a hold's version (the exact rule) before the hold's `until`,
   compared with today's UTC date, is held, not drift:
   - the component's result gains `hold_version`, `hold_until`, `hold_reason` and `hold_expired: false`;
   - the profile summary lists it under `held`;
   - the text report prints `<id>: <version> held until <date> (<reason>)`;
   - it no longer makes `pinned_versions_match` false.

   On and after `until` it is mismatched again: `hold_expired` is true and the text states
   `hold expired <date> (<reason>); reported as drift`. Any other version is drift as before. A malformed hold is
   skipped, so it can never turn drift into a hold. The default run still execs no probe, and the exit code is
   unchanged. `scripts/currency_due.py` reads only `mismatched` and `unchecked`, so a held component no longer
   counts as a pin behind, and an expired one does.
4. `tools/adoption/apply_codex_lane.py` still refuses any Codex but `CODEX_VERSION`. When the version is a hold's,
   its refusal names the hold and its `until` date.
5. `tests/test_pin_holds.py` checks every pins file's holds:
   - each carries `version`, `until`, `reason`, `url` and `sha256`, plus a `platform_dependency` in the row's shape
     when the row has one;
   - `until` is a real date after today (UTC), at most 90 days away;
   - a hold never names the pinned version itself;
   - a row has at most one hold.

   A hold therefore fails the tests on its date, and is then renewed with a new date and reason or deleted.
6. `manifests/stack.json` carries no install data, so its codex row refers to the hold rather than copying it.
7. No host or distribution name enters the repository: the reason names the condition (hosts not yet switched), the
   landing exception and the review item.

## Alternatives

- **Per-host pin rows.** Rows or files keyed by host would put host names in this portable repository. They would
  also multiply what the bootstrap, the status report and the Codex lane read, and they would outlive the hosts.
- **No repository record.** Keeping the PR comment as the only record leaves the status red for a held host, with
  no recorded reason or date, and nothing ends the exception.
- **Moving the pin back to 0.159.3.** This would undo #626's qualified move for every host, to suit the ones that
  have not switched.

## Precedent

- [`.github/osv-scanner.toml`](../../.github/osv-scanner.toml): an `[[IgnoredVulns]]` entry needs an `id`, a concrete
  `reason` and an `ignoreUntil` at most 90 days ahead, and an expired entry stops applying.
  `tests/test_osv_lockfile_coverage.py` `ignore_entry_problems` enforces this, counting `until <= date.today()` as
  expired. Upstream, OSV-Scanner v2.6.0 documents `ignoreUntil` as an "Optional exception expiry date"
  (`docs/configuration.md` L27-34). Its `shouldIgnoreTimestamp` applies an ignore only while
  `ignoreUntil.After(time.Now())` (`internal/config/config.go` L149-157), so the entry stops on its date.
- [`.grype.yaml`](../../.grype.yaml): a rule needs a reason and `review-by: YYYY-MM-DD`, and the file itself carries
  "Re-review by 2026-12-21".

A hold follows both: it is dated and reasoned, and a test fails once the date comes.

## Evidence class

- `tests/test_pin_holds.py` is structural validation over the repository files, with synthetic mutants.
- `tests/test_adoption_status.py` `DatedHoldTests` and the two lane tests in `tests/test_codex_worker_lane.py` are
  synthetic: a tiny script or the fake `codex` stands in for the client.
- On 2026-10-04 `python3 scripts/adoption_status.py --pinned-versions` printed
  `codex: 0.159.3 held until 2026-11-04 (...)` on a host still running 0.159.3. This is a local integration
  observation, not acceptance. The base revision's script, run on the same pins file, listed codex as mismatched.
- The hold verifies no installation. No held host's installed executable was compared with the recorded platform
  binary, since the probe there resolves to a launcher script. The 0.159.3 queue and Hindsight receipts keep their
  original scope.

## Overturn

- The held hosts retire or switch to the pin: delete the hold and the `manifests/stack.json` reference.
  `tests/test_pin_holds.py` forces that decision, or a dated renewal, by 2026-11-04.
- A second concurrent hold is needed, such as two old versions at once: revisit per-host pin rows.
  `tests/test_pin_holds.py` fails on a second hold and names this record.

## Same change

`adoption/templates/codex.config.template.toml` adds `"gpt-6.1-sol" = 4` under `[tui.model_availability_nux]`
(R6's TUI notice item). At openai/codex `rust-v0.160.0` (`a956835d020762cb2b570053af06f643a11c0ecc`) the table is a
map of model slug to a `u32` show count (`codex-rs/config/src/types.rs` L789-795, L940-942). The TUI shows a model's
availability notice only while that count is below `MODEL_AVAILABILITY_NUX_MAX_SHOW_COUNT = 4`
(`codex-rs/tui/src/app/startup_prompts.rs` L242, L250-266), and adds one per showing through
`set_model_availability_nux_count` (L281-305; `codex-rs/core/src/config/edit.rs` L837-841). A count of 4 therefore
stops the notice. At that tag the bundled catalog's only notice is gpt-6.1-sol's
(`codex-rs/models-manager/models.json` L178, L245-247). `adoption/new-wsl/client-config-map.json` already maps every
`tui.model_availability_nux` key as not wired, so the new piece raises the not-wired count of
`docs/decisions/2026-10-02-new-wsl-client-configuration.md`. That recount follows the record's re-pin in #674.

## Sources

- OSV-Scanner v2.6.0, tag commit `e840a6e8adb14b7777c78e26cfbf6e2abc1d1fc6`:
  <https://github.com/google/osv-scanner/blob/v2.6.0/docs/configuration.md> and
  <https://github.com/google/osv-scanner/blob/v2.6.0/internal/config/config.go>.
- npm registry metadata, read 2026-10-04: <https://registry.npmjs.org/@openai/codex/0.159.3> and
  <https://registry.npmjs.org/@openai/codex/0.159.3-linux-x64>.
- openai/codex `rust-v0.160.0`, tag object `79b1b666f2e8551f8abbbca34957227f67f3f553` peeling to
  `a956835d020762cb2b570053af06f643a11c0ecc`:
  <https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/tui/src/app/startup_prompts.rs> and
  <https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/config/src/types.rs>.
