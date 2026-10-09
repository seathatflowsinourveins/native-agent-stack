# Native diagnostic integration seams

The native node builder accepts optional `(name, config)` pairs through
`builtin_strategies`. It forwards each config unchanged to NautilusTrader's
supported `LiveNode.add_builtin_strategy` API while preserving the existing
Python strategy registrations, native risk engine and startup reconciliation.
The default empty tuple preserves the existing builder behavior.
Builtin configs are accepted only with the upstream `dry_run` field set to
literal `True`. A false, missing or non-boolean flag refuses the entire builtin
set before node construction. Upstream-generated client order IDs have not
been qualified under R-PAP-04; an executable diagnostic needs a separately
reviewed change before a non-dry-run builtin may be registered.

The reference is NautilusTrader **2.0.0rc5**, commit
[`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`](https://github.com/nautechsystems/nautilus_trader/tree/1b0a49d2792a9432a3aca3fcb617ce7a630d905e).
Its [native Python API](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/live/__init__.pyi)
and [IB execution tester example](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/examples/live/interactive_brokers/exec_tester.py)
provide the registration seam. The upstream
[ExecTester implementation](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/testkit/src/testers/exec/strategy.rs)
and [configuration](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/testkit/__init__.pyi)
are reused rather than copied or replaced. Primary-source inspection was
recorded on 2026-10-09 through 19:56:28 UTC.

`Controller(stop_file=...)` adds a per-run STOP pointer. The canonical global
STOP and controller abort remain effective. The pointer reaches both durable
intent reservation and the final pending-intent check. Entry readiness is
checked again after pending validation, and the existing lifecycle cleanup
condition consults both STOP pointers. With `stop_file=None`, the controller
continues to pass the ledger's original default STOP arguments. These checks
do not claim atomicity with the eventual broker network request.

The seam fixtures exercise configuration identity, default registration,
entry refusal before reservation and before a request, and global STOP,
port-readiness and controller-abort changes during local pending validation.
They also verify that reducing sells and cancellations remain available under
an active abort. Their temporary ledgers and STOP files are synthetic inputs.
One registration fixture uses a mocked node to establish forwarding and
guarded configuration. A separate installed-runtime fixture builds a real node
and registers a dry-run ExecTester without starting it or connecting a broker.
The native lifecycle fixture establishes cleanup before its ordinary duration
deadline when the per-run latch is already active. Existing adapter and
controller fixtures supply regression coverage. These results establish
offline integration; they do not establish broker acceptance. Tests make no
broker calls and do not read a host STOP file.

This change is preparation for a separately reviewed deterministic paper
diagnostic. It supplies no executable broker command or strategy fork. A
bounded lifecycle, exact account binding, journal/reconciliation contract and
observed reducing cleanup still have to be established before an order
acceptance. Native order acceptance remains **NOT_RUN**. A clock call, CLI
help or a mocked registration cannot substitute for that acceptance.

The protected N2 trial remains held. Its STOP, admission, bundle, timer and
evidence state are not inputs to these fixtures. Agent-native order tools
remain confined to the separately authorized account-C lane after its
authority exception has landed; these seams grant no such authority.
