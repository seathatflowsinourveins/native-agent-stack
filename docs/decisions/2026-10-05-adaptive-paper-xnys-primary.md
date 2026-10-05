# XNYS is the adaptive-paper NYSE calendar

Date: 2026-10-05. Lane: trading. Base: `f946c6d4ca988a17b6fa4392ecb488909f147883`.
North-star action: deterministic session admission and overnight session
navigation for the adaptive-paper engine on the separately qualified Alpaca
path. This change does not advance a broker-observed paper gate.

## Decision and sources

Use the required **exchange-calendars 4.13.2 XNYS** calendar for trading dates,
holidays, regular-session opening/closing times and previous/next session navigation.
The upstream tag resolves to
`dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a` (Apache-2.0). The installed source
files used here were byte-compared with their originals at that commit.

- [XNYS rules](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar_xnys.py#L157-L258): holidays, local timezone and regular/special closes.
- [Calendar factory and native cache](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/calendar_utils.py#L214-L326): `get_calendar("XNYS", start=..., end=...)`.
- [Session queries and navigation](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar.py#L1006-L1058), [date_to_session](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar.py#L1281-L1324): retain default parsing/range checks.
- [Range validation](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/calendar_helpers.py#L324-L391): `DateOutOfBounds` must propagate.
- [Package dependencies](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/pyproject.toml#L30-L37) and [versioned release](https://github.com/gerrymanoim/exchange_calendars/releases/tag/4.13.2).

For each queried date `d`, pass **December 1 of `d.year - 1` through January 31
of `d.year + 1`**, explicitly. Padding includes year-boundary holidays and
neighboring sessions. Use upstream's `date_to_session` rather than
keeping the engine's bounded ten-day search. A four-entry `functools.lru_cache`
retains calendars by query year: upstream's factory cache keeps only the latest
bounds per calendar name, so it does not cover alternating years. Calendar construction, missing
dependencies and range errors remain visible. No broker or other network call
was added to `sessions.py`.

The module derives its result from explicit inputs and timezone conversion.
PRE starts at 04:00 and ends at XNYS's `session_open`; POST ends at 20:00
Eastern. These extended-hours endpoints remain engine policy. The
session policy, reconciliation and boundary-receipt functions are unchanged.
An early-close flag now comes from XNYS's actual local close, including years
outside 2026/2027.

The [upstream default bounds](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar.py#L59-L62)
read `pd.Timestamp.now()` at **dependency import**. Explicit bounds make query
results independent of those unused globals; this is not a claim that the
unmodified dependency performs zero wall-clock reads during import. A test
poisons both globals and still queries 2031 with the required explicit bounds.

The former tables remain only as immutable migration fixtures in
`tests/test_adaptive_paper_sessions.py`. They add an independent comparison
against the engine's previous behavior: every one of 730 calendar dates in
2026/2027, 502 regular sessions, and their three early closes. Production has
no holiday table or optional parity helper. These fixtures are historical
regression evidence, not a second maintained calendar.

## Why the engine previously excluded the package

No substantive exclusion rationale was found in the recorded Git history.
`git log -S "environment constraints" -- blueprints/us-equities/adaptive-paper/sessions.py`
identifies commit `4ba8ac9a52c8cfc5b11b99eac364e383a1229c87` (PR #69,
2026-09-22). Its original docstring says:

> An optional `exchange_calendars` cross-check is provided for environments
> that already have that package installed; it is never a hard dependency of
> this module or of the engine, and this shared engine environment deliberately
> does not install it (see the task's environment constraints).

That names unspecified task constraints, without recording a dependency
conflict, platform problem or other technical reason. The same commit's
message describes the NYSE 2026 session model and synthetic checks, without
an exclusion explanation. `git log -S "exchange_calendars"` on `sessions.py`
also identifies the later corporate-action change
`4289143ab` and its dated 2027 cross-check, which does not explain the original
exclusion. Searches for the exclusion wording in the decision/documentation
history found no recorded rationale.

`git log -S "nautilus"` and `git log -S "alpaca-py==0.44.0"` on the engine's
`requirements.txt` identify its introduction in
`7e7eefe28315f3de3aa4dc75cc8b6524f70829cb` (2026-09-21). Its complete original
content was:

```text
# Tested together in an isolated Python 3.12 environment.
nautilus-trader==2.0.0rc5
alpaca-py==0.44.0
```

`git log -S "exchange_calendars"` on that requirements file has no match.
This establishes the recorded omission, not an inferred incompatibility.
The current exclusion is resolved by explicit installation, a hash lock and
the scratch-environment qualification below.

## Environment qualification and acceptance evidence

The engine directory previously provided the two exact direct requirements
above, with no complete engine transitive lock. The historical macOS lock in
`evidence/artifacts/macos-syn-e2e-20260924/` is platform-specific comparison
evidence and was left unchanged. We followed that repository's maintained
`uv pip compile --generate-hashes` requirements-lock format, using installed
uv 0.12.17 and Python 3.12.3 on Linux x86_64.

First resolve the original engine requirements into
[engine-baseline.lock](../../blueprints/us-equities/adaptive-paper/receipts/xnys-primary-20261005/engine-baseline.lock)
and install it in a fresh scratch venv. Then constrain every baseline package
while adding exchange-calendars 4.13.2. A second, clean venv installs the
complete [engine lock](../../blueprints/us-equities/adaptive-paper/requirements-linux-x86_64-py312.lock)
with `uv pip sync --require-hashes`. This is a reproducible qualification of
the committed engine requirement pins, not a reconstruction of a live host's
unrecorded transitive environment.

The [sanitized resolution diff](../../blueprints/us-equities/adaptive-paper/receipts/xnys-primary-20261005/resolution-diff.json)
records **all 20 baseline packages unchanged**, none removed, and only:

| Added distribution | Exact version |
| --- | --- |
| exchange-calendars | 4.13.2 |
| korean-lunar-calendar | 0.4.0 |
| pyluach | 2.3.0 |
| toolz | 1.1.0 |
| tzdata | 2026.5 |

All 25 distributions have generated hashes in the complete lock. pandas
3.0.6 and numpy 2.5.3 remain unchanged. Actual imports succeeded for
`nautilus_trader` 2.0.0rc5, its `nautilus_trader.live.LiveNode`, `alpaca` /
`alpaca.trading.client.TradingClient` 0.44.0, and `exchange_calendars` 4.13.2.
`uv pip check` returned exit 0. The source comparison covered calendar_utils,
exchange_calendar, exchange_calendar_xnys, us_holidays and calendar_helpers.

The [qualification record](../../blueprints/us-equities/adaptive-paper/receipts/xnys-primary-20261005/qualification.json)
retains exact command results, output digests, sanitized excerpts and failed
attempts. Checks use the native `unittest` runner and the real installed
calendar. They are **local integration checks**, not unchanged upstream tests
or broker acceptance:

- Session module suite: 145 tests, exit 0, no skips.
- Session module plus affected corporate-action, financing, native-adapter
  suites and runner corporate-action wiring: 320 tests, exit 0, no skips.
- Calendar-only CI dependencies installed into a separate scratch venv;
  session-clock, workflow-hardening and dependency-pin contract checks:
  151 tests, exit 0. Unchanged skips: no hash-frozen workflow exemptions,
  and the optional PyYAML parser is absent.
- Negative control: replacing the explicit-bounds adapter with default
  `get_calendar("XNYS")` makes the same bounds test error, exit 1 as intended.

Coverage includes Juneteenth and its Saturday observance, Good Friday,
observed July 3 and July 5, Thanksgiving, Christmas, 13:00 Black Friday and
Christmas Eve, a Christmas Eve full closure, weekday New Year, both weekend
New Year forms, both sides of DST transitions and the Sundays themselves,
weekends, year-crossing navigation, real `DateOutOfBounds` propagation,
construction errors and an unsupported upstream timestamp range. Saturday
New Year has **no preceding-Friday closure**; Sunday is observed Monday
([pinned rule](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/us_holidays.py#L45-L49)).
Calendar tests use explicit timestamps. The guarded query test rejects
`socket.socket`, `time.time`, pandas `Timestamp.now`, and the sessions module's
`datetime.now`/`today` calls during a cold query; it does not instrument every
clock or networking API. Poisoned upstream default globals and explicit factory
argument assertions independently guard the bounds. Only the preflight test
classes replace runner's `time` binding for the freshness oracle; the shared
process `time.time` is left intact.

The declared CI interpreter dependencies previously included only zizmor, while its
promotion-gate venv remained isolated. `.github/requirements-ci.txt` now
includes a separately hash-locked calendar-only subset of the qualified
engine environment. Linux validate/security-scan install that subset via
requirements-ci. The repair also installs the hash-locked calendar subset in
adoption-bootstrap's required Python 3.13 macOS job (both modes) and in
catalog-freshness before unittest. These test interpreters do not install
NautilusTrader.

## Corrections and limits observed during qualification

The first clean-install command incorrectly passed `-r` to `uv pip sync`
(exit 2). Installed `uv pip sync --help` requires positional requirement
files; the corrected command and README use that native interface (exit 0).
An extra import probe initially guessed `nautilus_trader.live.node` (exit 1).
The installed client and the existing native adapter instead use
`from nautilus_trader.live import LiveNode`; the corrected probe passed.

An initial new year-boundary assertion confused stop arming with a triggered
exit (session suite exit 1). The native strategy's bid must cross the armed
stop; the corrected check verifies that the prior session is confirmed and
the stop is armed. Supplemental suites also exposed two tests whose injected
calendar failure had depended on the removed table's year limit. They now
inject the actual error explicitly. A missing `mock` import in one of those
edits was corrected. The listed 320-test selection passed; that selection
omitted ingestion, the source-hash contract, mover suites and the full CI
suite. The first-round statement that all affected suites passed was too
broad. The repair evidence below covers the omitted consumers and reports
the complete suite's actual outcome.

The first broader 322-test run exited 1. In addition to the corrected
calendar-test issues, six credential-fixture outcomes fail in the mandated
scratch ancestry: this sandbox reports the root and home container directory
owners as UID 65534, which the unchanged credential guard rejects. These are
unrelated to calendar resolution. No credential guard, ancestor permissions,
live credential or host service was changed. The final 320-test affected
selection does not claim to qualify those credential fixtures.

Engine qualification is Linux x86_64 / Python 3.12 only. A different platform needs
its own resolved engine lock and checks. The repair checks wheel availability
for the separate calendar-only Python 3.13 macOS arm64 test environment;
it does not execute macOS tests. Scheduled future holidays are projections
of the pinned upstream rules; unforeseen closures require a qualified pin
update. PRE/POST policy remains the existing engine contract, not a
historical extended-hours or broker qualification; RTH opens come from XNYS.

## Alternatives, cross-check and overturn conditions

**Alpaca calendar:** alpaca-py 0.44.0 at
`cc4cb3b7ba50ae250e621983c2779047fb16bb28` offers
[`TradingClient.get_calendar`](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/alpaca/trading/client.py#L438-L461),
which calls `/calendar`. It can provide an independently retained
session-start receipt cross-check from the transport/operator layer. It
cannot be the pure clock because it requires a broker network response.
No endpoint was called or new cross-check integration added in this change.

**Hand table:** it preserves the prior 2026/2027 results as a test oracle,
but annual updates and missing coverage duplicate upstream functionality.
Keeping it as an executable fallback would conceal provider errors.

**pandas_market_calendars:** the recorded alternative 5.4.0 at
`275890784073a3a3a347e4f05f4dc986456e6a75` has a native
[`NYSE` calendar](https://github.com/rsheftel/pandas_market_calendars/blob/275890784073a3a3a347e4f05f4dc986456e6a75/pandas_market_calendars/calendars/nyse.py)
and bounded `schedule` API. It was not installed here. There is no new
comparison establishing a correctness or environment advantage over the
requested XNYS adapter. A future comparison must use its native NYSE calendar
rather than a mirrored XNYS calendar, and retain concrete discrepancies.

Overturn this decision for a reproduced session/open/close discrepancy
resolved against dated NYSE evidence and a broker receipt, or a demonstrated
engine compatibility or deterministic-bounds defect. Qualify the proposed
upstream pin/alternative in the unchanged engine baseline, rerun the migration
oracle and refusal tests, and preserve the failed condition. A different
calendar must improve correctness while keeping visible errors and explicit
inputs; popularity alone does not overturn the choice.

Completeness critic: the initial requested list missed Saturday New Year's
special rule, the 2027 Christmas Eve full closure, both sides of each DST
change, and genuine provider bounds versus the retired table's coverage
limit. These now have tests. Exceptional closures and other host/platform
environments remain the next calendar qualification sweep's scope; no
unexecuted upstream or broker test is promoted to acceptance.

## Repair round 2 (2026-10-05)

The cross-family verdict identified three p1 and six p2 findings. Each
behavioral repair has a regression executed red before its implementation
and green afterward. Documentary corrections require no new behavior tests.
The [repair qualification](../../blueprints/us-equities/adaptive-paper/receipts/xnys-primary-20261005/repair-round-2.json)
retains command exits, test counts, output digests and sanitized summaries.
First-round attempts remain historical evidence.

- **Ingestion:** expose public `is_trading_day` as a direct native XNYS
  membership query, and migrate ingestion's import and callback. A synthetic
  `main()` regression completes a Labor Day snapshot using the real calendar,
  with transport and credentials replaced at their boundaries. The scheduled
  script is unchanged; no scheduled or broker process was run.
- **Privacy contract:** remove the engine `.lock` entry from source-hashes.
  Its digest remains in the evidence registry. The narrow key pattern and
  matching gitleaks allowlist stay intact; a regression enforces both the
  absence from source-hashes and the registry's actual-content attestation.
- **CI interpreters:** both omitted workflows install the hash-locked
  calendar before their tests. Workflow contracts verify placement and all-mode
  installation. Native pip downloaded all nine hashed wheels for Python 3.13
  macOS arm64, including numpy/pandas cp313 wheels. Hosted macOS execution
  remains a coordinator/CI check. Editing adoption-bootstrap selects full mode.
- **Stale explanations and offline instructions:** runner, native strategy,
  financing and its tests describe query-year bounds and actual provider
  errors. The repository and offline throughput instructions now require the
  calendar subset or the qualified engine interpreter.
- **Native opening time:** `_boundaries` uses
  [upstream `session_open`](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/exchange_calendar.py#L1006-L1010).
  A provider-boundary delayed-open fixture demonstrates PRE continuing until
  10:00 and RTH starting then. The pinned XNYS has no scheduled late opens;
  this fixture checks adaptation, not a historical NYSE event.
- **Calendar reuse:** stdlib LRU glue retains four query years because
  [upstream retains one bounds tuple per name](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/exchange_calendars/calendar_utils.py#L212-L235).
  Alternating year-end CLOSED queries construct three calendars once;
  ordinary queries reuse the first close. Cold-cache fault-injection tests
  still prove construction/range errors and explicit bounds.
- **Mover X1:** the former table returned a nominal close on non-sessions;
  XNYS correctly refuses them. `plan_timing` now translates native non-session
  membership into `MoverRefusal("mover_x1_non_session")`, with weekend and
  holiday regressions. Construction and range failures continue to propagate.
- **Clock fixture:** freshness fixtures replace only runner's time binding
  inside their two test classes. A regression verifies the process clock is
  unchanged; the cold query also guards pandas `Timestamp.now`. The evidence
  claim now names exactly the APIs guarded.

Native `timeit` used the scratch engine, `-n 40 -r 5`, and an explicit warm-up
for ordinary 2026-03-10 16:00 UTC and year-boundary 2027-01-01 02:00 UTC
(2026-12-31 21:00 Eastern). Best repeat per call before/after:

| Query | First-round implementation | Repaired implementation |
| --- | --- | --- |
| Ordinary RTH | 190 microseconds | 138 microseconds |
| Year-boundary CLOSED | 242 milliseconds | 302 microseconds |

These are local warm-call probes under niceness 19, including construction
thrashing in the first-round boundary query, not cold-start or live-order
latency qualification. The bounded cache affects cost only; results still
derive from explicit inputs and retain upstream range checks.

Scratch engine imports for XNYS 4.13.2, Alpaca 0.44.0 and NautilusTrader's
LiveNode passed. A native sync dry-run reports all 25 locked packages unchanged
in that scratch engine. This does not inspect or attest the live engine's drift.
Deployment must separately review the live environment before syncing it.

The resumed final selection ran 179 engine tests covering sessions, ingestion,
source hashes and financing (exit 0, no skips), and 117 workflow-hardening
tests (exit 0, two unchanged skips). Earlier unchanged-input results include
98 mover/native-mover tests and 131 native/corporate-action tests, both exit 0
with no skips. The numpy/pandas qualification selection ran 151 tests (exit 0,
27 optional-runtime skips); the newly enabled mover/statistics and pandas
cases passed.

Two broader targeted runs require a coordinator host: the 310-test runner /
native / corporate-action run exited 1 with six credential-fixture outcomes,
and the 76-test throughput module exited 1 on its credential fixture. The
unchanged guard rejects this sandbox's root/home ancestor owner UID 65534.
The supplemental macOS-bootstrap test selection exited 1 with two native
`npm pack` calls returning 226; no host launcher or service was adjusted.

The full CI-equivalent suite was started with the pinned calendar/numpy/pandas
environment, but the previous turn deadline interrupted it. Its retained log
has 8,131 verbose outcome lines from a discovery of 10,962 cases, ending
during `test_secret_path_guard.K4GuardTests.test_k4_timing`; these lines include
subtests and omit multiline descriptions, so they are not a completed-case
count. No final summary or process exit was captured. Partial failures span
29 modules, including host credential, launcher, scratch-root and gitleaks
access checks; they have not all been diagnosed. The repaired calendar,
ingestion and source-hash cases observed in that run had no failed outcomes.
This is an incomplete check, and the coordinator must rerun the full suite
and host-dependent targeted checks. The resumed turn reused the bounded
passing evidence and did not restart the long suite.

Completeness review of this repair covered ingestion before the scheduler's
gate, every suite-running CI interpreter, source-hash privacy, mover refusal,
and year-boundary cache behavior. The retained parity oracle still covers all
2026/2027 dates. Broker early-close after-hours policy and the alternative
calendar's PRE/POST support remain unqualified leads; no broker call or new
calendar comparison was authorized for this repair.

## Registry and deployment boundary

Register finalized files last with `scripts/host_receipts.py register_file`
through its repository-supported Python API. The evidence manifest excludes
its own bytes, as required by `docs/lanes.md`'s hot-file protocol. Required
publication, catalog, manifest-order, per-file scans and diff checks are
reported with exit codes in the builder handoff.

**This changes both engine code and the engine environment. Deployment to
the live paper host is a separate operator step, outside paper run windows.**
This builder did not deploy, touch a live process/timer/credential/service,
commit or push. The authorized paper schedule remains 10:45:05Z and
13:30:05Z; heavy work is excluded from 10:35Z through 10:55Z.
