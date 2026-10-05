# XNYS is the adaptive-paper NYSE calendar

Date: 2026-10-05. Lane: trading. Base: `f946c6d4ca988a17b6fa4392ecb488909f147883`.
North-star action: deterministic session admission and overnight session
navigation for the adaptive-paper engine on the separately qualified Alpaca
path. This change does not advance a broker-observed paper gate.

## Decision and sources

Use the required **exchange-calendars 4.13.2 XNYS** calendar for trading dates,
holidays, regular-session closing times and previous/next session navigation.
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
neighboring sessions. Use upstream's cache and `date_to_session` rather than
keeping the engine's bounded ten-day search. Calendar construction, missing
dependencies and range errors remain visible. No broker or other network call
was added to `sessions.py`.

The module derives its result from explicit inputs and timezone conversion.
PRE 04:00–09:30 and POST through 20:00 Eastern remain engine policy. The
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
Calendar tests use explicit timestamps and reject socket/wall-clock calls
during a session query; the session module's preflight
freshness oracle is frozen to an explicit fixture value.

The declared CI interpreter dependencies previously included only zizmor, while its
promotion-gate venv remained isolated. `.github/requirements-ci.txt` now
includes a separately hash-locked calendar-only subset of the qualified
engine environment. This supplies the new required calendar to CI without
installing NautilusTrader in that interpreter.

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
edits was corrected. The final affected suites pass.

The first broader 322-test run exited 1. In addition to the corrected
calendar-test issues, six credential-fixture outcomes fail in the mandated
scratch ancestry: this sandbox reports the root and home container directory
owners as UID 65534, which the unchanged credential guard rejects. These are
unrelated to calendar resolution. No credential guard, ancestor permissions,
live credential or host service was changed. The final 320-test affected
selection does not claim to qualify those credential fixtures.

Qualification is Linux x86_64 / Python 3.12 only. A different platform needs
its own resolved lock and checks. Scheduled future holidays are projections
of the pinned upstream rules; unforeseen closures require a qualified pin
update. PRE/POST policy and modern 09:30 RTH opens remain the existing
engine contract, not a historical extended-hours calendar qualification.

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
