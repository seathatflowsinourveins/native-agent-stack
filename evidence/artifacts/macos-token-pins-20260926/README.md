# macOS token-efficiency pins: digest re-verification (2026-09-26)

`adoption/pins-macos-arm64.json` gained eight pins after `v2026.09.26`: `rtk`, `qmd`,
`repomix`, `toon`, `ccusage`, `headroom`, `markitdown` and `serena`, completing the
`token-efficiency` profile on macOS. This directory retains the check of each pin
against its official upstream artifact, run on 2026-09-26 on the WSL2 workstation
`nativestack-5975wx-20260925` from the branch that adds the pins, the check of which
file rtk 0.50.0 reads its config from on a Mac, which `adoption/bootstrap-macos.sh`'s rtk
reminder and the macOS instructions depend on, a red/green run of the tests that pin that
path, and wrong-input controls showing that those last two harnesses fail closed. After the
GPT-6 verification of this change it also retains, from the same workstation, a fail-closed copy
of the digest harness with its rerun (run 5) and a control of it, and a control of the rtk
exclusion instruction on the pinned binary ([below](#gpt-6-verification-findings)). The network
was used read-only, nothing was installed, and no Mac ran anything.

## Evidence class

All of it is `local_integration`: harnesses written for this change, not upstream tests,
not installation receipts, and silent about running these tools on macOS.

- `verify_pins.py` reads the publishers' own digests (the rtk release's `checksums.txt`
  and GitHub API asset digest, npm `dist.integrity` and `dist.shasum`, the PyPI JSON API's
  `digests.sha256`, the GitHub commits API) and compares them with hashes of artifacts it
  downloaded fresh from the same upstream URLs. It is kept byte-identical for runs 3 and 4 and
  the negative control; `verify_pins_fail_closed.py` is the copy to run now: it makes the same
  checks, exits 2 before any download when the `packaging` module is missing, and fails where
  `verify_pins.py` let a check silently not run ([below](#gpt-6-verification-findings)).
- `rtk_config_path_check.sh` prints upstream source at the rtk v0.50.0 tag commit and the
  `dirs` crates that commit's `Cargo.lock` pins, and runs the upstream linux-x86_64 release
  binary with a scratch `HOME`. It fails closed. It stops with exit 1, before using what it
  fetched, unless the tag resolves to the pinned commit, the fetched tree is that commit,
  `Cargo.lock` holds exactly one entry for each `dirs` crate at the expected version, both
  crates match those entries' checksums (checked before either is extracted) and the release
  archive matches `adoption/pins-linux-x86_64.json`. It then checks each binary run's exit
  status and output, and ends in `PASS` only when all 16 checks hold (exit 1 otherwise). The
  macOS answer rests on the printed source and on rtk's own README and configuration guide:
  the Linux binary cannot show where the macOS binary looks.
- `pin_fields.py` compares two copies of a pins file field by field.
- `reminder_path_red_green.py` runs this repository's own tests of the macOS rtk reminder's
  config path (`RtkConfigPathTests` and `PortedFunctionsUnderRealBash32Tests` in
  `tests/test_adoption_bootstrap_macos.py`, with a real bash 3.2.57) in three trees: this
  change before the path fix, a copy of the fixed tree with only the reminder's path line
  reverted, and the fixed tree. It fails closed. It refuses a `--bash32` that is not GNU bash
  3.2 (exit 2), and it passes (exit 0) only when every tree ran all 12 tests of the two
  classes with none skipped or erroring, the fixed tree passed and every other tree failed on
  a test failure.
- `fail_closed_controls.py` hands each of those two harnesses a wrong input and passes only
  when the harness refuses it ([below](#fail-closed-harnesses)).
- `packaging_control.py` runs both digest harnesses with a Python that cannot import
  `packaging`, and `rtk_hooks_table_control.py` applies the old and the corrected rtk exclusion
  instruction to four config files and lets the pinned rtk read each result; both fail closed
  ([below](#gpt-6-verification-findings)).

## Files

| File | Run | Result |
| --- | --- | --- |
| [`digest-check-run5.txt`](digest-check-run5.txt) | run 5, 12:19Z, [`verify_pins_fail_closed.py`](verify_pins_fail_closed.py) with Python 3.13.15 and `packaging` 26.3 (both in its header), against this change's final macOS pins file (sha256 `0e054b52…`) and the Linux pins file of its base (sha256 `a274e888…`) | exit 0: 63 checks, 0 mismatches |
| [`packaging-control.txt`](packaging-control.txt) | 12:28Z, [`packaging_control.py`](packaging_control.py) with this host's default Python 3.13.15, which cannot import `packaging`, against the same two pins files | `PASS`: `verify_pins.py` skipped the `requires_python` check and still reported `PASS` (60 checks, exit 0); `verify_pins_fail_closed.py` exited 2 with nothing checked or downloaded |
| [`rtk-hooks-table-control.txt`](rtk-hooks-table-control.txt) | 12:19Z, [`rtk_hooks_table_control.py`](rtk_hooks_table_control.py) with a scratch copy of the pinned linux-x86_64 rtk 0.50.0 binary | `PASS: all 23 checks held` (below) |
| [`instruction-test-red-green.txt`](instruction-test-red-green.txt) | 12:23Z, `RtkExclusionInstructionTests` of `tests/test_adoption_bootstrap.py` on this change before and after the instruction fix | 4 failures before, all 3 tests passing after (below) |
| [`digest-check.txt`](digest-check.txt) | run 4, 04:50Z, the `verify_pins.py` in this directory, against the macOS pins file as it stood then (sha256 `2387dab6…`) and the Linux pins file at this branch's base `9c1669c7` (sha256 `59bdb4cf…`); both are in its header | exit 0: 61 checks, 0 mismatches |
| [`digest-check-negative-control.txt`](digest-check-negative-control.txt) | negative control, 04:51Z, the same `verify_pins.py` against a wrong-answer copy of that macOS pins file written by [`negative_control.py`](negative_control.py) (below) | exit 1: 16 mismatches, then serena's commit refused |
| [`digest-check-run3.txt`](digest-check-run3.txt) | run 3, 04:26Z, the same `verify_pins.py`, before the last wording edit to the macOS pins file's `source` and rtk `install_note` | exit 0: 61 checks, 0 mismatches |
| [`digest-check-run2.txt`](digest-check-run2.txt) | run 2, 04:10Z, the same checks before the header lines were added and before a wording edit to serena's `install_note` | exit 0: 61 checks, 0 mismatches |
| [`digest-check-run1.txt`](digest-check-run1.txt) | run 1, 04:03Z, [`verify_pins-run1.py`](verify_pins-run1.py) | exit 1: two headroom mismatches (below) |
| [`digest-check-attempt0.txt`](digest-check-attempt0.txt) | attempt 0, 04:02Z | harness crash after rtk and qmd matched (below) |
| [`pin-fields-since-run4.txt`](pin-fields-since-run4.txt) | 09:49Z, [`pin_fields.py`](pin_fields.py): what changed in each pins file after run 4 checked it, plus a control | no field `verify_pins.py` reads changed; the control's eight altered fields are flagged (exit 1) |
| [`rtk-config-path.txt`](rtk-config-path.txt) | 10:58Z, [`rtk_config_path_check.sh`](rtk_config_path_check.sh) | `PASS: all 16 checks held`: rtk 0.50.0 reads `~/Library/Application Support/rtk/config.toml` on macOS (below) |
| [`rtk-config-path-run1.txt`](rtk-config-path-run1.txt) | 06:48Z, [`rtk_config_path_check-run1.sh`](rtk_config_path_check-run1.sh), the version that did not fail closed ([below](#fail-closed-harnesses)) | the same source, `MATCH` for both crates and the same binary results, without check lines |
| [`reminder-path-red-green.txt`](reminder-path-red-green.txt) | 11:08Z, [`reminder_path_red_green.py`](reminder_path_red_green.py): the reminder path tests of `tests/test_adoption_bootstrap_macos.py` in three trees | `PASS`: 14 failures before the fix, 13 with only the path line reverted, all 12 tests passing in the fixed tree, none skipped or erroring in any tree (below) |
| [`reminder-path-red-green-run1.txt`](reminder-path-red-green-run1.txt) | 09:52Z, [`reminder_path_red_green-run1.py`](reminder_path_red_green-run1.py), the version that did not fail closed ([below](#fail-closed-harnesses)) | `PASS` with the same three results |
| [`fail-closed-controls.txt`](fail-closed-controls.txt) | 11:08Z, [`fail_closed_controls.py`](fail_closed_controls.py) against `rtk_config_path_check.sh` and `reminder_path_red_green.py` | `PASS`: all three controls held ([below](#fail-closed-harnesses)) |
| [`fail-closed-controls-before.txt`](fail-closed-controls-before.txt) | 10:59Z, the same controls against the two `-run1` harnesses | `FAIL`: none of the three held |

Run 4's output equals run 3's except for the timestamp and the macOS pins file's sha256.
Every pinned version, url and commit is printed in both, and every pinned sha256 is compared
with the same freshly computed digest, so none of those changed between the two runs; only
the pins file's prose did (it no longer calls the macOS rtk reminder a verbatim copy of the
Linux one).

## Since run 4

Both pins files changed after run 4, in fields `verify_pins.py` does not read, so run 4's
result stood for the files this change first committed and for main's Linux file at the time.
[`pin-fields-since-run4.txt`](pin-fields-since-run4.txt) shows it:

- The macOS file, from the copy run 4 checked to the copy this change first committed (sha256
  `8767c367…`): only `source` and rtk's `install_note` changed. Both now name the file rtk
  reads on a Mac (below), and `source` no longer contradicts itself about which npm pins are
  byte-identical to their Linux ones.
- The Linux file, from the base `9c1669c7` to origin/main `b5c6313b`: only rtk's
  `install_note` changed (#314, `5c1961e4`).
- A control: the same comparison between the run-4 copy and `negative_control.py`'s
  wrong-answer copy of it flags the seven altered sha256 values and serena's commit and
  exits 1. That wrong-answer copy has the sha256 (`aabcf6db…`) that
  `digest-check-negative-control.txt` records, so the negative control was made from the
  file run 4 checked.

The macOS file changed once more after that, in rtk's `install_note` only (its exclusion
instruction, [below](#gpt-6-verification-findings)), and run 5 checked the final copies
directly: this change's macOS file (sha256 `0e054b52…`) and the Linux file of its base
`20b52a5b` (sha256 `a274e888…`). Run 5 equals run 4 except for the timestamp, the header's
Python and `packaging` line, the two pins files' sha256 and the two added presence checks.

Re-run `verify_pins_fail_closed.py` when a pin's version, kind, url, sha256, commit or package,
an npm pin's `checksum_ref` or markitdown's `install_note` changes; `pin_fields.py` exits 1 then.

## Reproduce

From the repository root:

```sh
<python with packaging> evidence/artifacts/macos-token-pins-20260926/verify_pins_fail_closed.py \
  adoption/pins-macos-arm64.json adoption/pins-linux-x86_64.json <empty scratch directory>
python3 evidence/artifacts/macos-token-pins-20260926/negative_control.py \
  adoption/pins-macos-arm64.json <scratch>/negctl   # then the harness above on <scratch>/negctl/pins-macos-arm64.json
<python without packaging> evidence/artifacts/macos-token-pins-20260926/packaging_control.py <empty scratch directory>
python3 evidence/artifacts/macos-token-pins-20260926/rtk_hooks_table_control.py \
  --rtk <the pinned rtk 0.50.0 linux-x86_64 binary> <empty scratch directory>
bash evidence/artifacts/macos-token-pins-20260926/rtk_config_path_check.sh <empty scratch directory>
python3 evidence/artifacts/macos-token-pins-20260926/pin_fields.py <label>=<old.json> <label>=<new.json>
python3 evidence/artifacts/macos-token-pins-20260926/reminder_path_red_green.py \
  --bash32 <bash 3.2 binary> [--before <a tree of this change before the path fix>]
python3 evidence/artifacts/macos-token-pins-20260926/fail_closed_controls.py \
  --bash32 <bash 3.2 binary> <empty scratch directory>
python3 evidence/artifacts/macos-token-pins-20260926/fail_closed_controls.py --bash32 <bash 3.2 binary> \
  --rtk-check evidence/artifacts/macos-token-pins-20260926/rtk_config_path_check-run1.sh \
  --red-green evidence/artifacts/macos-token-pins-20260926/reminder_path_red_green-run1.py \
  <another empty scratch directory>
```

`verify_pins_fail_closed.py` needs `gh` (for `gh api`), `npm`, `git`, network access and the
`packaging` module; without `packaging` it exits 2 before any download, and its header records
the Python and `packaging` versions (run 5: a scratch venv of this host's Python 3.13.15 with
`packaging` 26.3). `verify_pins.py` evaluated headroom's `requires_python` only when `packaging`
was importable, and this host's default `python3` cannot import it
([`packaging-control.txt`](packaging-control.txt)). Every retained run of it that reached
headroom (runs 1 to 4 and the negative control) has the `requires_python admits 3.13` check
line, so `packaging` was importable in each; none of those outputs records the Python or
`packaging` version. `packaging_control.py` needs what `verify_pins.py` needs and a Python that
cannot import `packaging`. `rtk_hooks_table_control.py` needs the pinned rtk 0.50.0
linux-x86_64 binary (the one `rtk_config_path_check.sh` extracts; run here with a scratch copy of
this host's installed copy, whose sha256 it checks) and no network. `rtk_config_path_check.sh`
needs `git`, `curl`, `tar`, `sha256sum`, `awk`, `python3` and network access.
`reminder_path_red_green.py` needs a bash 3.2 binary (`/bin/bash` on a stock Mac; this host
used a local build of bash 3.2.57) and no network; its output records the Python and bash
versions. `fail_closed_controls.py` needs what both of those need plus `gzip`, and its crate
control uses the network the rtk check uses.

## What each check covers

- `rtk` 0.50.0: `rtk-aarch64-apple-darwin.tar.gz` equals its `checksums.txt` line and the
  release's API asset digest; the archive holds one bare `rtk` executable, so
  `install_single_binary_tarball` applies.
- `qmd`, `repomix`, `toon`, `ccusage`: each registry tarball's sha512 and sha1 equal
  `dist.integrity` and `dist.shasum`, its sha256 equals both the macOS and the Linux pin
  (the same platform-independent tarball), and the registry's `optionalDependencies`
  are listed: `sqlite-vec-darwin-arm64` for qmd, `@ccusage/ccusage-darwin-arm64` for
  ccusage, none for repomix and toon. npm resolves those two platform packages at install
  time; they are not pinned or verified here.
- `headroom` 0.37.0: the `macosx_11_0_arm64` wheel equals its PyPI digest and size. PyPI
  also lists an x86_64 macOS wheel and a maturin (Rust) sdist, but no universal2 or
  `py3-none-any` wheel, so the pinned wheel is the only one an Apple Silicon Python can
  install without building the sdist (uv prefers a compatible wheel to a source build). Its
  `requires_python` (`>=3.10`) admits 3.13; from run 5 on, a missing sdist or a
  `requires_python` that cannot be evaluated is a mismatch.
- `markitdown` 0.1.8: the sdist equals its PyPI digest and the Linux pin; the
  `py3-none-any` wheel uv installs equals its PyPI digest and the sha256 the pin's note
  quotes (from run 5 on, a missing wheel is a mismatch).
- `serena` 2.0.0.dev0: the GitHub commits API returns commit
  `c6fbd1c5932df2494ffa0020af5a9fbe80b82143`, a depth-1 `git fetch` of it by hash into a
  scratch bare repository succeeds and `git cat-file -e` accepts it, its `pyproject.toml`
  declares `serena-agent` 2.0.0.dev0, and PyPI answers 404 for that version.

When these runs were made, neither bootstrap checked the headroom or markitdown sha256 at
install time; uv resolved both from PyPI and the pins recorded the hashes as cross-checks.
`adoption/bootstrap-macos.sh` changed after `v2026.09.26`: following the Linux #334 change,
this branch ported `install_uv_tool` verbatim, so both bootstraps now download headroom's pinned wheel (here the
`macosx_11_0_arm64` one), verify its sha256 before uv runs (`shasum -a 256` on macOS) and
install that file; markitdown's sdist sha256 stays a cross-check. That port is covered by
`tests/test_adoption_bootstrap_macos.py` with a `uv` shim under bash 3.2, not by these runs.

The reference implementation is `adoption/bootstrap-linux.sh` at `38221784` (PR #334).
Its installer body is preserved; both scripts now share byte-identical `fetch()` and
`verify_sha256()` helpers. The latter prefers the native macOS checker, with GNU
`sha256sum` as the Linux fallback. The command contract comes from
[Perl's shasum reference](https://perldoc.perl.org/5.40.5/shasum); the local wheel plus
extras uses [uv's package-source syntax](https://docs.astral.sh/uv/pip/packages/).
The installed `search-first`, `find-skills`, `diagnosing-bugs` and
`verification-before-completion` instructions were reviewed; the existing Linux
implementation and checksum tools cover this bounded port without a new dependency.
The original installer-only parity test passed before this follow-up. Extending it to
the download/checksum helpers failed on the differing `fetch()` bodies and missing
`verify_sha256()`, establishing a regression control for the shared-helper requirement.

The follow-up local integration run used the supplied CI Python, lint environment and
real Bash 3.2.57 binary on Linux. The command was `python -m unittest
tests.test_adoption_bootstrap tests.test_adoption_bootstrap_macos
tests.test_adoption_docs_consistency`, with `BASH32_BINARY` set to that binary and the
lint environment prepended to `PATH`. It returned exit 0 with no skips:

```text
Ran 267 tests in 59.187s

OK
```

Both bootstrap scripts also passed separate `bash -n` checks and a joint `shellcheck`
run (exit 0, empty output); the macOS script additionally passed Bash 3.2.57's `-n`.
The shared version-report parity test passed separately. Direct byte comparisons
confirmed both installers and both helpers match across platforms, and
`install_uv_tool` still matches the Linux body at `38221784`. These are local
integration and structural checks, not a native macOS installation or upstream
acceptance run; the checksum-selection fixture delegates its GNU-command shim to
real `shasum` and does not claim native GNU coverage for that fixture.

## rtk's config file on macOS

The first version of this change told Mac users, and made the macOS reminder check,
`${XDG_CONFIG_HOME:-$HOME/.config}/rtk/config.toml`, the Linux path. rtk 0.50.0 never reads
that file on a Mac. [`rtk-config-path.txt`](rtk-config-path.txt) retains why:

- `git ls-remote` gives tag `v0.50.0` = `1d87b8e719ce0a50c223cd93ca64dd16921f9aec`, the
  commit `recipes/README.md` cites. There `get_config_path()` is
  `dirs::config_dir()/rtk/config.toml` (`src/core/config.rs:495-498`), `Config::load()`
  reads only that path (`:315-324`), and no environment variable rtk reads, by literal name
  or through a named constant, selects that path.
- Its `Cargo.lock` pins `dirs` 5.0.1 and `dirs-sys` 0.4.1; both crates downloaded from
  crates.io match the lock file's checksums. `dirs` serves macOS from `src/mac.rs`, whose
  `config_dir()` is `$HOME/Library/Application Support` (`mac.rs:7,10`, with `$HOME` from
  a non-empty `HOME`, else the passwd entry) and never reads `XDG_CONFIG_HOME`; only
  `src/lin.rs` does, and only for an absolute path.
- rtk's own `README.md:453` and `docs/guide/getting-started/configuration.md:14-15` give
  the macOS path as `~/Library/Application Support/rtk/config.toml`.
- The pinned Linux binary shows the rest on Linux's own path: `rtk config` prints the file
  it reads on its first line (and `XDG_CONFIG_HOME` moves it there); with the recipe's
  four-entry block the hook leaves `git show HEAD:x | tail -n 5` alone (`No rewrite for`,
  exit 1); with the block twice, or with a `[tracking]` table that lacks `history_days`,
  `rtk config` fails (exit 1, a TOML parse error or `missing field`) while the hook
  silently rewrites the command with its defaults (exit 0). `rtk config` wrote no file.

Each fact the harness enforces (the tag, the fetched commit, the two lock entries, the crate
and release digests, every binary result and the file listing) is a `[check: ...]` line
there, and the file ends with a `result` section, `PASS: all 16 checks held`. Otherwise it
differs from [`rtk-config-path-run1.txt`](rtk-config-path-run1.txt), the 06:48Z run of the
harness before it failed closed, only in its timestamp, the peeled-tag pattern added to
`git ls-remote`, and the `sha256sum --check` command and exit lines printed before the
release check.

The script's reminder, the rtk pin's `install_note`, the macOS page, `adoption/bootstrap.md`
and the recipe now name `~/Library/Application Support/rtk/config.toml` for macOS. The page
tells a Mac user to confirm with `rtk config` and the recipe's `rtk hook check` commands,
and the note names `rtk config`. `tests/test_adoption_bootstrap_macos.py`'s `MAC_RTK_CONFIG`
holds the path, and `RTK_CONFIG_PATH_REVIEWED_VERSIONS` fails the suite when the rtk pin
moves to a version whose source nobody has re-read.

[`reminder-path-red-green.txt`](reminder-path-red-green.txt) is `reminder_path_red_green.py`
run on the final tree. The same test file (its sha256 is in the header) judged three trees:

- **before**: this change as the independent review found it, before the path fix, with only
  the test file replaced. 14 failures, each on the path: the reminder stayed silent for the
  recipe's block at the Linux or `XDG_CONFIG_HOME` path, named the Linux path in its
  message, or the docs lacked the macOS path.
- **mutant**: a copy of the fixed tree with only the reminder's `local config=` line put
  back to the Linux path. 13 failures: every reminder behaviour test fails, while the docs
  test passes because the docs are fixed. Anyone can rebuild this tree from the committed
  files, unlike the first one, which was never committed.
- **fixed**: the final tree. All 12 tests pass.

Every tree ran all 12 tests with none skipped or erroring, under GNU bash 3.2.57, and the
harness exits 0 only in that combination. Paths are sanitized there and lines over 400
characters are cut, as the harness's docstring says. The 09:52Z run of the harness before it
failed closed, [`reminder-path-red-green-run1.txt`](reminder-path-red-green-run1.txt),
reports the same three results. After these runs the GPT-6 fixes
([below](#gpt-6-verification-findings)) reworded the exclusion instruction in the macOS page, the
recipe, `adoption/bootstrap.md` step 4a and the rtk pin's `install_note`, texts the docs test
reads; `adoption/bootstrap-macos.sh` and `tests/test_adoption_bootstrap_macos.py` did not
change, and each of those texts still names the macOS path.

## Negative control

The passing runs count only because the same harness fails on wrong answers.
`negative_control.py` copies the macOS pins file with every hashed new pin's sha256
replaced by the sha256 of the text `negative-control:<id>` and serena's commit replaced by
a well-formed commit that is not the pinned one (its last hex digit advanced by one);
nothing else changes. `verify_pins.py` against that copy, with the same upstream
downloads, reported all 16 hash comparisons that involve those pins as `MISMATCH` (rtk's
computed sha256, `checksums.txt` line and API digest; each npm tarball's computed sha256
and Linux-pin equality; headroom's PyPI digest and computed sha256; markitdown's PyPI
digest, computed sha256 and Linux-pin equality), while every comparison that does not
involve a pinned value still matched. At serena it stopped: `gh api` answered
`No commit found for SHA` (HTTP 422) for the altered commit, so the harness exited 1
before its summary line. In that file the scratch directory is shown as `<scratch>` and
the checkout path in the stderr traceback as `<checkout>`; everything else is verbatim.

## Fail-closed harnesses

The cross-family review of this change found that two of these harnesses could pass without
their checks holding:

- `rtk_config_path_check.sh` printed `MISMATCH` when a crate's sha256 differed from
  `Cargo.lock`, then extracted the crate, read it and exited 0.
- `reminder_path_red_green.py` judged each tree by unittest's exit status alone. Given a bash
  that is not 3.2 on a host whose `/bin/bash` and `PATH` bash are not 3.2 either (this one's
  are 5.2.21), the tests skip all seven `PortedFunctionsUnderRealBash32Tests` and drop
  `RtkConfigPathTests`' bash 3.2 cases, and the harness still reported `PASS`.

Both now fail closed, as [Evidence class](#evidence-class) describes. The versions that
produced the 06:48Z and 09:52Z outputs are kept byte-identical as
`rtk_config_path_check-run1.sh` and `reminder_path_red_green-run1.py`.
`fail_closed_controls.py` hands each harness a wrong input; a control holds only when the
harness refuses it:

- **crate**: a `curl` first on `PATH` re-compresses each crate fetched from static.crates.io
  with two empty tar blocks appended, so it holds the same files under another sha256. It
  holds when the harness prints both crates as `MISMATCH` against Cargo.lock checksums equal
  to the unaltered crates' sha256 (from the shim's log), exits nonzero and extracts neither.
- **bash5**: `--bash32` names the host's bash, 5.2.21. It holds when the harness exits nonzero
  and does not report `PASS`.
- **skip**: a real bash 3.2.57, from a copy of this tree whose test file has one added line,
  `@unittest.skip(...)` on `PortedFunctionsUnderRealBash32Tests`. It holds when the harness
  exits nonzero and does not report `PASS`.

[`fail-closed-controls-before.txt`](fail-closed-controls-before.txt) runs the controls
against the two `-run1` harnesses: none holds (`# result: FAIL`). The rtk check extracted
both altered crates, read them and exited 0; apart from its timestamp and the two crate
lines, its output there equals `rtk-config-path-run1.txt`. The red/green harness reported
`PASS` both with bash 5.2.21 and with the added skip, its fixed tree `OK (skipped=7)` each
time. [`fail-closed-controls.txt`](fail-closed-controls.txt) runs them against the harnesses
as committed: all three hold (`# result: PASS`). The rtk check stopped at its crate check
with neither crate extracted (exit 1). The red/green harness refused bash 5.2.21 (exit 2)
and, with the added skip, judged both trees `FAILED: 7 skipped` (exit 1).

The earlier outputs still stand: [`rtk-config-path-run1.txt`](rtk-config-path-run1.txt)
prints `MATCH` for both crates, and
[`reminder-path-red-green-run1.txt`](reminder-path-red-green-run1.txt) names bash 3.2.57 in
its header and reports `Ran 12 tests` in every tree, with no test skipped or erroring. So the
conditions the earlier harnesses did not enforce held in those runs; the reruns enforce them.

## GPT-6 verification findings

The GPT-6 verification of this change found two more defects. Both are fixed here, and
neither changes a pinned value.

**`verify_pins.py` could pass without its Python-compatibility check.** When `packaging` was
not importable it logged `(packaging not importable; requires_python not evaluated)` and went
on, so it could report `PASS` without checking that headroom 0.37.0 supports the Python 3.13
the bootstrap installs it with. This host's default `python3` (3.13.15) cannot import
`packaging`, and under it `verify_pins.py` made 60 of its 61 checks and reported `PASS` with
exit 0 ([`packaging-control.txt`](packaging-control.txt), "before"). `verify_pins.py` stays
byte-identical, because runs 3 and 4 and the negative control ran it and that control's
traceback cites its line numbers. [`verify_pins_fail_closed.py`](verify_pins_fail_closed.py)
is a copy that imports `packaging` before it reads its arguments and exits 2, with nothing
checked or downloaded, when it cannot. It also records a mismatch wherever the old harness let
a check silently not run: a `requires_python` that `packaging` cannot parse, a missing headroom
sdist and a missing markitdown `py3-none-any` wheel. Its header records the Python and
`packaging` versions. Under the same Python it exited 2 with its message on stderr, printed
nothing and left its fetch directory empty ("after"). `packaging_control.py` exits 0 only when
both halves hold (`# result: PASS: the control held both ways`) and refuses an interpreter that
can import `packaging`. Run 5 ([`digest-check-run5.txt`](digest-check-run5.txt)), with
`packaging` 26.3, checked the final pins files: 63 checks, 0 mismatches, `requires_python =
>=3.10` admitting 3.13.

**The exclusion instruction could produce a second `[hooks]` table.**
[The macOS page](../../../adoption/platforms/macos-arm64.md) told a reader to replace any
existing `exclude_commands` line in rtk's config with the recipe's block, whose first line is the
`[hooks]` header, so a file that already had a `[hooks]` table got a second one. The recipe,
`adoption/bootstrap.md` step 4a and the macOS rtk pin's `install_note` said to replace a
"line", which also leaves the rest of a multi-line value, like the recipe's own, behind. All
four now say: inside the existing `[hooks]` table, replace the key's whole value, from
`exclude_commands =` through its closing `]` (or add the key when the table lacks it), and add
the `[hooks]` header only when the file has no `[hooks]` table. The four-entry value is
unchanged. `RtkExclusionInstructionTests` in `tests/test_adoption_bootstrap.py` holds that
wording in the paragraph before every copy of the recipe's block in a Markdown page outside
`evidence/`, in step 4a and in the note. [`instruction-test-red-green.txt`](instruction-test-red-green.txt)
runs it on this change as the verification found it (4 failures, one per instruction) and on
the fixed tree (all 3 tests pass).

[`rtk-hooks-table-control.txt`](rtk-hooks-table-control.txt) shows the difference on the pinned
binary: a scratch copy of this host's installed rtk 0.50.0, whose sha256 equals the binary
`rtk_config_path_check.sh` extracted from the pinned archive. From the 2026-09-25 two-entry key,
a multi-line key beside `suppress_hook_warning = true` after a `[tracking]` table, and a
`[hooks]` table without the key, the old instruction gave a file on which `rtk config` exits 1
(``duplicate key `hooks` in document root``) while the hook rewrites
`git show HEAD:x | tail -n 5` with its defaults. From those three and a file with no `[hooks]`
table, the new instruction gave a file that rtk loads with the four entries and the starting
file's other settings, and the hook left the probe alone (`No rewrite for`, exit 1).
`PASS: all 23 checks held`, and rtk wrote no file but the config. The harness applies each
instruction as its own text edit and refuses (exit 2) a binary that is not the pinned one.

Not changed: the one-line reminder that `adoption/bootstrap-linux.sh` and
`adoption/bootstrap-macos.sh` print after installing rtk still says to replace any existing
exclude_commands line with `[hooks] exclude_commands = [...]` and names the recipe, which now
carries the corrected instruction. Both test modules pin that text byte for byte, and
`reminder-path-red-green.txt` records the sha256 of the macOS one.

## Failed attempts

- **Attempt 0** stopped with `KeyError: 'dist'` at repomix, after every rtk and qmd check
  matched. `npm view <spec> dist optionalDependencies --json` returns the bare `dist`
  object when a package has no `optionalDependencies`, so the harness now reads the whole
  version document (`npm view <spec> --json`). Its stdout is kept verbatim; in the
  stderr traceback the scratch path is replaced by `<scratch>`. The harness version that
  crashed was edited in place and not kept.
- **Run 1** failed two headroom checks that encoded claims from the first draft of the
  pin notes: "the only macOS wheel is the pinned arm64 one" (PyPI also has
  `macosx_10_12_x86_64`, which an arm64 interpreter cannot install, so the check was
  mis-scoped) and "no platform-independent artifact (sdist or py3-none-any wheel)" (PyPI
  has a maturin sdist, so the draft's claim that headroom-ai ships no
  platform-independent artifact was wrong). Its harness is kept as `verify_pins-run1.py`.
  From run 2 on, the harness checks the arm64-compatible wheels and the absence of a
  `py3-none-any` wheel, inspects the sdist's build backend and also fetches serena's
  commit with `git`; the pin notes and the macOS page now say what PyPI publishes. Every
  digest an attempt reached matched its pin.
- **The config path.** The macOS rtk reminder and its instructions first used the Linux
  config path (above); the independent review of this change found it, and the fix and its
  tests, both part of this change, replaced it.
- Three earlier `rtk_config_path_check.sh` runs (06:40Z, 06:41Z, 06:48:28Z) were not kept.
  The first used a scratch `HOME` directory named `home`, and a committed `/home/<name>/`
  path reads as a personal path to `scripts/validate.py`, so the script now names it
  `scratch-home`; the next two ran before the script printed all the `dirs` and `dirs-sys`
  lines this README cites. The 06:48:46Z run of the version kept as
  `rtk_config_path_check-run1.sh` is retained as `rtk-config-path-run1.txt`.
- Earlier runs of the same two test classes were not kept. Four ran an earlier draft of the
  test file: before the fix at 06:39Z and 06:45Z (14 failures each), after the script fix
  but before the docs fix at 06:39Z (1 failure, the docs test), and after both at 06:43Z
  (all pass). One more, at 09:48Z, ran the harness kept as `reminder_path_red_green-run1.py`
  with the final test file and script but before the last documentation edits (before 14
  failures, mutant 13, fixed all pass). `reminder-path-red-green-run1.txt` is that harness's
  run on the final tree, and `reminder-path-red-green.txt` the fail-closed harness's.
- **Harnesses that failed open.** `rtk_config_path_check-run1.sh` and
  `reminder_path_red_green-run1.py` ([above](#fail-closed-harnesses)) are kept byte-identical,
  with their outputs.
- Eight runs made for the fail-closed fix were not kept; a retained run supersedes each:
  - 10:54Z: the first control run, against the `-run1` harnesses (none held);
  - 10:57Z: a trial of each fixed harness (the rtk check held all 16 checks; the red/green
    harness gave the same three results) and a control run against them (all held);
  - 10:58Z: a red/green run (the same three results) and control runs against the fixed
    harnesses (all held) and the `-run1` ones (none held);
  - 10:59Z: a control run against the fixed harnesses (all held).

  After those runs the red/green harness changed only its message for a missing `Ran N
  tests` line and then its docstring, and `fail_closed_controls.py` only how it prints the
  Python command, labels the bash 3.2 binary, quotes the shim's paths and handles a missing
  binary. The rtk check did not change after its 10:57Z trial, and the controls' inputs and
  conditions stayed the same.
- Runs made for the GPT-6 findings and not kept: `RtkExclusionInstructionTests` in an earlier
  draft that matched its two phrases case-sensitively, before the fix (the same 4 failures) and
  after it (1 failure: the macOS page opens a sentence with "Inside"), after which the test
  compares without case or line breaks; a 12:16Z trial of `rtk_hooks_table_control.py`
  whose output equals the retained one except for its timestamp line; and a 12:19Z run of
  `packaging_control.py`, before its docstring's run range was corrected and it resolved the
  checkout path, whose output equals the retained one except for its timestamps.
