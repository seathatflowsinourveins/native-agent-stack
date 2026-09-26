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
  as repaired, with fixture runs of both in an owned test repository.

## Evidence class

All of it is `local_integration`: harnesses written for this change, not upstream tests.
Codex's `hooks/list` answers are Codex's own verdicts, but only for the shapes asked, in
throwaway homes. Nothing here ran `apply.sh --apply` or `rollback.sh --apply` on this host,
edited a client home, or restarted a service. The Codex source read for the model is tag
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
| [`codex_oracle.py`](codex_oracle.py) | the oracle; `parse`, `matchers` and `trust` modes, each with `--repo` pointing at the repaired checkout | |
| [`codex-parse-oracle.jsonl`](codex-parse-oracle.jsonl) | `codex_oracle.py parse` | 64 shapes, 0 disagreements |
| [`codex-matcher-oracle.jsonl`](codex-matcher-oracle.jsonl) | `codex_oracle.py matchers` | 126 matchers, 78 decided, 0 disagreements |
| [`codex-trust-oracle.jsonl`](codex-trust-oracle.jsonl) | `codex_oracle.py trust` | 12 hooks, every hash equal, 0 disagreements |
| [`codex_known_answers.py`](codex_known_answers.py), [`codex-known-answers.json`](codex-known-answers.json) | the builder's probe for the six `currentHash` known answers in `tests/test_adoption_status.py`; rerun during the repair with identical output | |
| [`checker-tests-red.txt`](checker-tests-red.txt) | the five repaired `ClientWiringTests` against the checker as reviewed | 54 failures, 1 error (the surrogate crash) |
| [`checker-tests-green.txt`](checker-tests-green.txt) | the same five tests against the repaired checker | OK |
| [`host_trust.py`](host_trust.py), [`host-trust.json`](host-trust.json) | the repaired checker on this host, read-only, with the builder's Codex `hooks/list` cross-check of 16:03Z | 7 of 7 ai-memory hooks: current hash equal to `trusted_hash`, enabled; Codex's `hooks/list` also says 7 of 7 trusted, and neither hook file changed after it |
| [`g1_observation.py`](g1_observation.py), [`g1-observation.json`](g1-observation.json) | loopback Prometheus and Loki at one instant | all 112 token-counter series `instance="unscoped"`, 4,504 counter resets in the hour, `increase()` of output tokens 55.2 times the output tokens Loki's `api_request` events logged in it |
| [`host-scripts/`](host-scripts/) | the repaired scripts, the reviewed ones under `reviewed/`, and two harnesses run on both | see below |
| [`builder-runs/`](builder-runs/) | the builder's `prove.sh` runs before any repair, from the primary checkout, the live clone and the u5 worktree | retained for their native observations: `codex debug prompt-input` carried no RTK.md text while origin/main's checker said `rtk_instructions: true`, and `hooks/list` showed 7 of 7 ai-memory hooks trusted |

In `host-scripts/`:

| File | Result |
| --- | --- |
| [`fixture-reviewed.txt`](host-scripts/fixture-reviewed.txt), [`fixture-fixed.txt`](host-scripts/fixture-fixed.txt) | [`host_scripts_fixture.sh`](host-scripts/host_scripts_fixture.sh) on each pair of `apply.sh`/`rollback.sh`: 11 of 16 expectations unmet for the reviewed scripts, 0 for the repaired ones (an `--apply` without a reviewed `--target` SHA or with `--fetch`, a live process in the checkout, a target lacking the u5 change while HEAD is already there, a missing `wt`, a data dir not in allowlist mode, enrollment checked against the hook's own data dir, rollback) |
| [`prove-harness-reviewed.txt`](host-scripts/prove-harness-reviewed.txt), [`prove-harness-fixed.txt`](host-scripts/prove-harness-fixed.txt) | [`prove_harness.py`](host-scripts/prove_harness.py) on each `prove.py`, with every native probe stubbed: 5 of 6 expectations unmet for the reviewed one, 0 for the repaired one (no blocker reads UNTESTED, the capture check passes the hook's `--data-dir` and fails a denylist admission, the Prometheus half of the G1 check is observed rather than grepped) |

Paths are shown as `$SCRATCH`, `$WORK`, `$BASE`, `$TMP`, `$TEST_HOME` (a test's temporary
home) and `~`; no hash of a real hook, command, credential or configuration value is
recorded.

## Rerun

```sh
python3 codex_oracle.py parse --base "$(mktemp -d)" --repo "$CHECKOUT"      # also: matchers, trust
host-scripts/host_scripts_fixture.sh host-scripts "$(mktemp -d)/fx"          # needs wt, jq and ai-memory on PATH
python3 host-scripts/prove_harness.py host-scripts/prove.py "$CHECKOUT" "$MAIN_REPO" "$(mktemp -d)"
```

The oracle and the fixture start Codex, Worktrunk and `ai-memory hook --check-capture`
only in the throwaway directories they create.
