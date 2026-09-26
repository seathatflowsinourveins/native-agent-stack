# adoption_status truth: Codex hook parse, trust and matchers (2026-09-26)

`scripts/adoption_status.py --client-wiring` reports how many Codex events run an
ai-memory hook and how many of those Codex actually runs (`ai_memory_hook_events` and
`ai_memory_hook_events_trusted`), and whether RTK's instructions reach the Codex model
(`rtk_instructions`). This directory retains what those answers were compared against,
all on the NativeStack WSL2 workstation on 2026-09-26, with Codex 0.157.1:

- Codex's own `codex app-server` `hooks/list`, asked in throwaway `CODEX_HOME`/`HOME`
  directories, about 64 `hooks.json` shapes, 126 matchers and 12 hook-trust states;
- the checker's unit tests of those behaviours, failing on the change as first reviewed
  and passing after the repair;
- this host's own hook trust, read by the repaired checker without starting Codex;
- the Prometheus and Loki observation behind the G1 text in
  `observability/native-data/render.py`;
- the u5 host scripts (`apply.sh`, `rollback.sh`, `prove.sh`, `prove.py`), as reviewed and
  as repaired, with fixture runs of both in an owned test repository;
- the second review's five findings, with runs before and after their repair
  ([Second review](#second-review)).

## Evidence class

All of it is `local_integration`: harnesses written for this change, not upstream tests.
Codex's `hooks/list` answers are Codex's own verdicts, but only for the shapes asked, in
throwaway homes. Nothing here ran `apply.sh --apply` or `rollback.sh --apply` on this host,
edited a client home, or restarted a service. The second review's harnesses run stub
app-servers; its one Codex start is the known-answers rerun, in throwaway homes. The Codex source read for the model is tag
`rust-v0.157.1` (`codex-rs/hooks/src/engine/discovery.rs`, `config_rules.rs`,
`events/common.rs`, `codex-rs/config/src/hook_config.rs`, `fingerprint.rs`), with the crate
versions its `Cargo.lock` pins: serde 1.0.228, serde_json 1.0.149 (built with its
`arbitrary_precision` feature, as the "invalid type: map, expected u64" answers show),
regex 1.12.3 and regex-syntax 0.8.8.

## What Codex decided, and what the checker now does

- **Parse.** Codex reads `hooks.json` with `serde_json::from_str::<HooksFile>` and loads no
  hook at all from a file that fails. It fails on a repeated known field (top-level
  `hooks` or `description`, an event, a group's `matcher`, a handler's `command`, `type`,
  or both `commandWindows` spellings), `NaN` or `Infinity` anywhere, a lone surrogate
  escape in anything it parses as text (a key, a known string field, or anything inside a
  handler, which serde buffers whole), a number a `timeout` cannot hold (above 2^64-1, or
  any fraction), an array or object nested 128 deep inside a handler, an unknown top-level
  key, a numeric `type`, and an MCP `input` whose last duplicate is null. It accepts
  repeated unknown keys, lone surrogates and any number in a skipped value, deep nesting
  in a skipped value, `-0` as a timeout, and serde's array form of every struct. A
  `timeout` above 2^63-1 on a hook Codex hashes, or such an `additionalContextLimit` on an
  event that keeps it, makes 0.157.1 stop answering `hooks/list` (its TOML conversion of
  the hook identity fails). The repaired checker follows each of these and reports both
  Codex counts `null` for a file Codex rejects; the reviewed checker counted such files as
  wired, and crashed on a lone surrogate in a command.
- **Matchers.** Codex compiles a group's matcher with Rust's `regex` crate and skips the
  group when that fails. Python's `re` differs in both directions (for example `(?#note)`,
  `\0`, `a{,2}` and `[\b]` only in Python; `\z`, `\p{L}`, `a**` and `^*` only in Rust). The
  checker now decides a matcher only inside a subset both engines parse alike and answers
  `null` otherwise: 78 of the 126 matchers were decided, all as Codex decided them.
- **Trust.** Codex runs a user hook only when it is enabled and its `[hooks.state]`
  `trusted_hash` equals its current hash (`hook_trust_status`: an exact string equality;
  keys trimmed with Rust's `str::trim`). For the 12 shapes, each checker hash equalled
  Codex's `currentHash`, and the checker's run verdict equalled Codex's for all six state
  variants, including a key padded with spaces (trimmed: trusted) and one prefixed with
  U+001C (not trimmed by Rust: untrusted).

## Files

| File | Run | Result |
| --- | --- | --- |
| [`codex_oracle.py`](codex_oracle.py) | the oracle; `parse`, `matchers` and `trust` modes, each with `--repo` pointing at the repaired checkout; since the second review `--base` must be a new or empty directory (the outputs below came from [the oracle before that guard](review-2/as-reviewed/codex_oracle.py), whose modes are unchanged) | |
| [`codex-parse-oracle.jsonl`](codex-parse-oracle.jsonl) | `codex_oracle.py parse` | 64 shapes, 0 disagreements |
| [`codex-matcher-oracle.jsonl`](codex-matcher-oracle.jsonl) | `codex_oracle.py matchers` | 126 matchers, 78 decided, 0 disagreements |
| [`codex-trust-oracle.jsonl`](codex-trust-oracle.jsonl) | `codex_oracle.py trust` | 12 hooks, every hash equal, 0 disagreements |
| [`codex_known_answers.py`](codex_known_answers.py), [`codex-known-answers.json`](codex-known-answers.json) | the builder's probe for the six `currentHash` known answers in `tests/test_adoption_status.py`; rerun during the repair with identical output, and again after the second review moved it onto `codex_oracle.hooks_list` (byte-identical output) | |
| [`checker-tests-red.txt`](checker-tests-red.txt) | the five repaired `ClientWiringTests` against the checker as reviewed | 54 failures, 1 error (the surrogate crash) |
| [`checker-tests-green.txt`](checker-tests-green.txt) | the same five tests against the repaired checker | OK |
| [`host_trust.py`](host_trust.py), [`host-trust.json`](host-trust.json) | the repaired checker on this host, read-only, with the builder's Codex `hooks/list` cross-check of 16:03Z | 7 of 7 ai-memory hooks: current hash equal to `trusted_hash`, enabled; Codex's `hooks/list` also says 7 of 7 trusted, and neither hook file changed after it |
| [`g1_observation.py`](g1_observation.py), [`g1-observation.json`](g1-observation.json) | loopback Prometheus and Loki at one instant | all 112 token-counter series `instance="unscoped"`, 4,504 counter resets in the hour, `increase()` of output tokens 55.2 times the output tokens Loki's `api_request` events logged in it |
| [`host-scripts/`](host-scripts/) | the repaired scripts, the reviewed ones under `reviewed/`, and two harnesses run on both | see below |
| [`builder-runs/`](builder-runs/) | the builder's `prove.sh` runs before any repair, from the primary checkout, the live clone and the u5 worktree | retained for their native observations: `codex debug prompt-input` carried no RTK.md text while origin/main's checker said `rtk_instructions: true`, and `hooks/list` showed 7 of 7 ai-memory hooks trusted |

In `host-scripts/`:

| File | Result |
| --- | --- |
| [`fixture-reviewed.txt`](host-scripts/fixture-reviewed.txt), [`fixture-fixed.txt`](host-scripts/fixture-fixed.txt) | [`host_scripts_fixture.sh`](host-scripts/host_scripts_fixture.sh) on each pair of `apply.sh`/`rollback.sh`: 11 of 16 expectations unmet for the reviewed scripts, 0 for the repaired ones (an `--apply` without a reviewed `--target` SHA or with `--fetch`, a live process in the checkout, a target lacking the u5 change while HEAD is already there, a missing `wt`, a data dir not in allowlist mode, enrollment checked against the hook's own data dir, rollback). These runs used [the fixture before the second review](review-2/as-reviewed/host_scripts_fixture.sh) |
| [`prove-harness-reviewed.txt`](host-scripts/prove-harness-reviewed.txt), [`prove-harness-fixed.txt`](host-scripts/prove-harness-fixed.txt) | [`prove_harness.py`](host-scripts/prove_harness.py) on each `prove.py`, with every native probe stubbed: 5 of 6 expectations unmet for the reviewed one, 0 for the repaired one (no blocker reads UNTESTED, the capture check passes the hook's `--data-dir` and fails a denylist admission, the Prometheus half of the G1 check is observed rather than grepped). The repaired one is [`prove.py` before the second review](review-2/as-reviewed/prove.py): its pin check passed with no `--version` observation (line 9), which the current `prove.py` reads UNTESTED under the same harness |

Paths are shown as `$SCRATCH`, `$WORK`, `$BASE`, `$TMP`, `$TEST_HOME` (a test's temporary
home), `$SANDBOX`, `$CHECKOUT` and `~`; no hash of a real hook, command, credential or
configuration value is recorded.

## Second review

The GPT-6 cross-family review of commit `b1df549f` reported five defects, and each held
against the source. The files as that review saw them are in `review-2/as-reviewed/`; every
harness below ran on those first, then on the repaired files.

- **High: the fixture deleted the WORK_DIR it was given.** `host_scripts_fixture.sh` ran
  `rm -rf` on its second argument. It now requires a path that does not exist, creates it
  with `mkdir` and works only inside it. Git in the fixture sees only that sandbox, as git's
  own `t/test-lib.sh` (v2.43.0) arranges: every inherited `GIT_*` variable unset,
  `GIT_CONFIG_NOSYSTEM`, `GIT_ATTR_NOSYSTEM` and `GIT_CEILING_DIRECTORIES` set, `HOME`
  inside WORK_DIR. [`fixture_guard_check.sh`](review-2/fixture_guard_check.sh), with stub
  `apply.sh` and `rollback.sh`: the reviewed fixture deleted an existing WORK_DIR's file,
  rewrote the caller's `GIT_CONFIG_GLOBAL` file and made six fixture commits in the
  caller's `GIT_DIR` repository ([before](review-2/fixture-guard-before.txt)); the repaired
  one refuses the existing directory and changes neither
  ([after](review-2/fixture-guard-after.txt)). It still meets 16 of 16 expectations on the
  repaired `apply.sh` and `rollback.sh` ([`fixture-fixed.txt`](review-2/fixture-fixed.txt),
  which differs from round 1's run only in commit ids, times and process ids). The same
  class in `codex_oracle.py`, which deletes and recreates `trust`, `matchers` and
  `parse-NN` under `--base`: `--base` must now be a new or empty directory (harness case
  O1: the reviewed oracle deleted an existing `trust/keep.txt`, the repaired one refuses).
- **Medium: the three oracle outputs were not in the repository.** `.gitignore`'s
  `*.jsonl` matched them, and `scripts/validate.py` lists files through Git, which leaves
  ignored files out, so they passed on this host while no clone had them. A `.gitignore`
  exception for this directory's `*.jsonl` and their registration repair it.
  `RetainedEvidenceTests` in `tests/test_adoption_status.py` checks that every file this
  README links is registered and not ignored: it failed on the three
  ([before](review-2/checker-tests-before.txt)) and passes
  ([after](review-2/checker-tests-after.txt)). Across all 21 evidence READMEs, these three
  were the only linked files unregistered or ignored.
- **Medium: `prove.py`'s pin check passed without a version observation.** It now fails
  on any contradiction of an observed `--version`, reads UNTESTED when a version is
  unavailable or nothing differs from its pin, and passes only for an observed mismatch
  that the checker surfaces at the top. [`review2_harness.py`](review-2/review2_harness.py)
  cases V1 to V5: V1 (no observation) and V2 (both at their pins) read PASS before and
  UNTESTED after; V3 (surfaced) passes and V4 (not surfaced) and V5 (a mismatch the host
  does not have) fail in both ([before](review-2/harness-before.txt),
  [after](review-2/harness-after.txt)).
- **Medium: a silent app-server could block `prove.py` without end.** Its `readline()`
  loop never reached the 90 s deadline, and its cleanup waited without a bound after
  SIGTERM; `codex_known_answers.py` read the same way. `prove.py` now reads through a
  thread and a queue with a deadline, as `codex_oracle.py` does, and ends the app-server
  with bounded waits (end of input 15 s, SIGTERM 3 s, SIGKILL 10 s);
  `codex_known_answers.py` asks through `codex_oracle.hooks_list`. Cases R1 to R3, against
  a stub app-server that ignores SIGTERM and either never answers or lingers after
  answering: none returned within 120 s before, all within 30 s after. Asked of Codex
  0.157.1 in throwaway homes, the reworked `codex_known_answers.py` printed a file
  byte-identical to [`codex-known-answers.json`](codex-known-answers.json).
- **Low: the checker chose the instruction file by Python's whitespace.** `str.strip()`
  removes U+001C to U+001F; Rust's `str::trim`, which Codex applies to
  `AGENTS.override.md` (`codex-rs/codex-home/src/instructions/mod.rs` at `rust-v0.157.1`),
  does not. So an override holding only U+001C made the checker read `AGENTS.md` while
  Codex sends the override. The check now strips `RUST_WHITESPACE`, which equals the
  Unicode White_Space set; `test_a_non_blank_agents_override_replaces_agents_md` gained two
  such overrides (`true` before, `false` after).

## Rerun

```sh
python3 codex_oracle.py parse --base "$(mktemp -d)" --repo "$CHECKOUT"      # also: matchers, trust
host-scripts/host_scripts_fixture.sh host-scripts "$(mktemp -d)/fx"          # needs wt, jq and ai-memory on PATH
python3 host-scripts/prove_harness.py host-scripts/prove.py "$CHECKOUT" "$MAIN_REPO" "$(mktemp -d)"
review-2/fixture_guard_check.sh host-scripts/host_scripts_fixture.sh "$(mktemp -d)/guard"
python3 review-2/review2_harness.py host-scripts/prove.py codex_known_answers.py "$CHECKOUT" "$(mktemp -d)/h"
```

The oracle and the fixture start Codex, Worktrunk and `ai-memory hook --check-capture`
only in the throwaway directories they create. The fixture, the guard check and the
second-review harness each take a path that does not exist yet and create it; the oracle
takes a new or empty `--base`.
