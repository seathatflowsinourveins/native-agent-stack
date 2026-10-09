# MCP surfaces trial evidence

The [decision record](../../../docs/decisions/2026-10-09-mcp-surfaces-trials.md)
proposes one default, **mcporter 0.14.2**, from measured PSS and cold discovery
cost. Inspector 2.10.1 improves warm latency. Both new candidates remain TRIAL;
successful candidate fresh reach and owner deployment gates are open.

- [Conformance provenance](conformance/provenance.json) binds the upstream pin,
  official package SHA-256, quality checks, native install/inverse and protocol
  boundary. `host-checks/` contains six passing checks on the two active HTTP
  registrations and three unavailable-QMD probes. `client-checks/` retains the
  two corrected passing clients and the initial zero-check setup failures.
- [Inspector report](inspector/REPORT.md), [receipt](inspector/receipt.json) and
  [measurements](inspector/measurements.json) bind 42 timed operations, twenty
  paired results, private-daemon PSS, native retention observations and cleanup.
- [Fresh-session receipt](fresh-session/receipt.json) and
  [completed tool calls](fresh-session/tool-calls.json) retain the actual reach
  and failure boundary of the unnamed task. The original rollout is private;
  model prose and reasoning are excluded from publication.
- [Native command recorder](run_native.py) executes vendor commands and samples
  owned process-tree PSS. It implements no MCP protocol or replacement harness.
- [Conformance redaction map](conformance/redaction.json) and
  [Inspector redaction map](inspector/redaction.json) distinguish original capture
  digests from committed public-byte digests. Personal home paths use
  `/home/example` and transient session identifiers are redacted.

Source package archives, exact pinned source blobs and original captures remain
in the lane-owned research prefixes. Public logs are sanitized observations;
their original-byte hashes are not claims about the sanitized copy. No catalog,
user-level client configuration or platform status changes are part of this PR.
