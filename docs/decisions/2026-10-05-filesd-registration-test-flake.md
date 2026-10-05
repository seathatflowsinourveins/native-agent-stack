# Decision: correct file_sd registration test evidence and timing bounds

Date: 2026-10-05. Repair round: `filesd-flake-r2`.

North-star action: keep adaptive-paper registration lifecycle checks reliable
before broker-specific paper qualification. This repair changes tests and their
evidence records; it exercises synthetic ledgers and loopback listeners.

## Root cause correction

`start()`'s set difference cannot see a re-registration of an address that an
earlier, still-registered exporter in the same test used; random ephemeral-port
reuse triggers it. The earlier exporter has stopped, while its target remains
listed. It accepts no connection before stopping, so closing its listener frees
the port for another listener.

This corrects the causal interpretation in commit `46e3e5d45`'s root-cause
record. `SO_REUSEADDR` is not required for this reuse. The r1 observation of
378 repeated addresses in 1,000 sequential exporters describes one host's
sample, rather than a CI collision rate or an isolated test of that option.

The r2 native socket control ran 1,000 sequential `bind(('127.0.0.1', 0))`,
`listen()`, and `close()` operations per setting, with no accepted connections.
The observed Linux `ip_local_port_range` was 24145–28240, containing 4,096 ports.

| SO_REUSEADDR | Repeated addresses | Rate | Unique addresses |
| --- | ---: | ---: | ---: |
| Enabled | 357 / 1,000 | 35.7% | 643 |
| Disabled | 222 / 1,000 | 22.2% | 778 |

The control exited 0. Both settings produced repeated addresses. These rates
describe the recorded host and samples; CI rates remain unmeasured.

Original sources: CPython v3.13.15's
[TCPServer.server_bind](https://github.com/python/cpython/blob/v3.13.15/Lib/socketserver.py#L463)
conditionally sets the option before binding, and
[HTTPServer](https://github.com/python/cpython/blob/v3.13.15/Lib/http/server.py#L134)
enables it. The exporter at
[9ef5424acc1a71acc15e3c8fb6cf5fa59f97ca42](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9ef5424acc1a71acc15e3c8fb6cf5fa59f97ca42/blueprints/us-equities/adaptive-paper/metrics.py#L411)
replaces the same single-target group and emits readiness after registration.
Its target groups follow the
[Prometheus v3.15.0 file_sd format](https://github.com/prometheus/prometheus/blob/v3.15.0/docs/configuration/configuration.md#file_sd_config).

## Timing repair and discriminating checks

The helper drains nonblocking stderr once more at its deadline, stopping at
`BlockingIOError` or EOF before constructing the failure message. The negative
control now uses a 5-second timeout and a 10-second elapsed bound. The early-exit
test uses a 30-second timeout and proves failure within 15 seconds.

The alternative of retaining the 1-second negative timeout and 3-second elapsed
assertions failed a native unittest control with a four-second startup delay:
both selected tests failed, exit 1, in 9.323 seconds. The identical control after
the repair passed both tests, exit 0, in 13.426 seconds. This is local fault
injection into the real exporter, not a measurement of macOS startup.

The requested mutation proofs ran in scratch copies of the test module:

- Old detection body, retaining the new signature and Popen arguments:
  `test_a_reused_port_is_recognised_as_this_exporters_registration` failed with
  `exporter never registered its target`, exit 1, in 30.233 seconds.
- Readiness regex with its file_sd suffix removed:
  `test_an_unscraped_exporter_cannot_satisfy_readiness_with_an_old_registration`
  failed with `AssertionError not raised`, exit 1, in 0.235 seconds.

The unmutated module passed all 42 tests, exit 0, in 12.237 seconds. Twenty
sequential runs of `FileSdRegistrationTests` all exited 0: 19 tests per run,
380 tests total, with run durations of 9.381–10.406 seconds.

Returned logs and the socket-control JSON remain under the requested private
`TMPDIR=$HOME/.cache/filesd-r2`; executions used `nice -n 19`. These are local
integration checks, not upstream-suite or provider acceptance.

Completeness review covered retained addresses, no-registration output, early
exit, deadline output draining, both socket-option settings, and both detector
mutations. Native macos-15 execution remains unmeasured here. Revisit these bounds
if CI supplies evidence of startup beyond their margin; revisit the parser if
the exporter's readiness output changes. Production code remains unchanged.
