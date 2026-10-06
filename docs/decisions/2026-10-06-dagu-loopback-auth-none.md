---
status: proposed
date: 2026-10-06
review_by: 2027-01-01
decision-makers: command center
consulted: ns2604-coop; paper-lane classification requested
informed: NativeStack2604 operators
---

# Record Dagu as a passwordless loopback operator path on NativeStack2604

## Context and problem statement

The user chose passwordless local operation. The command center reports that
at 10:08Z it selected `DAGU_AUTH_MODE='none'` for the existing NativeStack2604
service, retained a backup and restarted that service. This records PR does not
repeat that operation or inspect the environment file, backup, keys or private
Dagu home. The reported configuration and this lane's later read-only
observations have separate provenance in the [receipt](../../evidence/receipts/dagu-loopback-auth-none-20261006.json).

The operator interface serves recoverable local research and oversight of the
US-equities research/simulation and independently qualified paper workflows.
API access or a scheduler inventory does not qualify a paper strategy, broker,
order path or unattended runtime.

The existing [new-WSL pin decision](2026-10-05-dagu-mise-pin-move.md) selects Dagu
2.18.2 only for that profile. The workstation/trading stack remains held at
2.16.6. Both the PATH CLI and the service's health response now report 2.18.2;
this is consistent with that scoped selection, not an unapproved pin move.
Version strings are not binary checksum or installation acceptance evidence.

## Decision drivers

- Preserve the chosen passwordless local workflow and the native Dagu interface.
- Describe operator access accurately; keep Grafana's Viewer role distinct.
- Keep the Dagu listener on loopback, with no listener or tunnel exposure.
- Preserve historical authentication observations and each check's actual scope.
- Inspect only supported read-only interfaces, without credential or DAG-body capture.

## Considered options

1. Retain native `auth.mode: none` for the existing loopback operator interface.
2. Require Dagu's native authentication for that local operator interface.
3. Treat Dagu as an anonymous Viewer interface through another wrapper.

## Decision outcome

Record option 1, following the user's local-workflow choice and the existing
trading hosting recipe. Dagu's native `none` mode disables authentication; it
does not create a global Viewer role. Grafana's anonymous Viewer access remains
an observation path, while Dagu is an operator path without authentication.
No new wrapper, authentication proxy, installer, validator or runner is added.

Keep the service on `127.0.0.1:21080` and never expose this mode through another
listener or a tunnel. A deployment that requires network access needs its own
upstream authentication decision. This record introduces no host/config change
and no permission to start a DAG or broker operation.

### Confirmation and evidence classes

At 10:39:36Z, `ss -H -ltn '( sport = :21080 )'` returned one loopback listener,
with exit 0. Three direct TCP probes to the host's non-loopback IPv4 addresses
all returned `ECONNREFUSED` (111). These are native read-only observations of
direct listener/interface reachability. They do not establish absence of a
reverse proxy, tunnel or off-host forwarding path. The public receipt excludes
the host-interface addresses.

At 10:41:05Z, the public health API returned HTTP 200, `status: healthy` and
`version: 2.18.2`. Health is a public route even with other authentication modes;
that response alone does not prove operator access without credentials.

At 10:44:26Z, a fresh curl request with default configuration disabled, no
Authorization/cookie argument and proxies bypassed returned HTTP 200 from the
supported DAG-list API. It returned eight of eight records. Maintained jq
filtered the response outside model context to names, tags and counts. The raw
response includes parameter fields; it is not a server-side metadata-only
projection. Raw bodies, parameters/default parameters and definitions were not
retained. The earlier inventory request did not disable automatic curl
configuration and is retained as inventory evidence only, not credential-free
proof.
At 10:59:15Z, an explicit tag-presence capture confirmed that all eight native
tag fields are present and empty arrays. The earlier filter's null-to-empty
normalization is preserved as an earlier attempt, with no ownership conclusion
drawn from it.

These observations establish the returned interface results on this host. They
are not unchanged upstream tests, source-package acceptance, complete role/API
qualification or paper execution. The command center's configuration report is
reported historical execution; the publication's independent read is pending.

### Observed DAG identities and paper-lane ownership

All eight native tag fields are present and empty arrays. Names and tags alone
do not establish unchanged definitions or ownership. The co-op's A25 at
11:01:22Z supplies the [operator classification](../../evidence/artifacts/dagu-loopback-auth-none-20261006/owner-classification.json)
after reading only installed descriptions, comments and schedules. None of
these eight is a paper-lane execution or support DAG. The current paper runs are
reported as NativeStack systemd timers outside this service. This classification
is reported metadata inspection, not this lane's inspection of workflow bodies.

| Observed DAG name | Source association | Paper-lane membership |
| --- | --- | --- |
| `example-01-basic-sequential` | Upstream 2.18.2 filename/header, `examples_unix.go:10`; co-op A25 | Bundled sample, outside paper lane |
| `example-02-parallel-execution` | Upstream filename/header, `:29`; A25 | Bundled sample, outside paper lane |
| `example-03-scheduling` | Upstream filename/header, `:67`; A25 | Bundled sample, outside paper lane |
| `example-04-nested-workflows` | Upstream filename/header, `:113`; A25 | Bundled sample, outside paper lane |
| `example-05-template-and-file` | Upstream filename/header, `:155`; A25 | Bundled sample, outside paper lane |
| `restic-backup` | Backup reminder in `scripts/currency_due.py:800-801`; installed description reported in A25 | Foundation whole-host backup, outside paper lane |
| `restic-restore-check` | Same reminder; installed description reported in A25 | Foundation canary restore check, outside paper lane |
| `tz-currency-check` | Installed description/schedule reported in A25; reported dashboard tie is PR #775 | Foundation time practice, outside paper lane |

The zero paper execution/support counts come from the separate operator mapping,
not a name-based inference. Generic whole-host backup and time correctness also
serve trading, but are classified as foundation work. The five sample-header
associations do not prove byte-identical live bodies or inactivity; no sample is
removed. The inventory applies to this one service and capture time, and does
not qualify backup success, job execution or paper operation elsewhere.

### Credential inventory and environment-loader housekeeping

No Dagu declaration was found in the current credential inventory or
`docs/secret-storage.md`; there is no current builtin-auth entry to amend.
Existing provider sign-ins and historical protected-Dagu receipts keep their
original scope. In particular, the old dashboard receipt's required-operator-auth
limitation is historical; this dated record supersedes it only for the present
NativeStack2604 loopback operator path. The old Collector recipe's expected 401
also describes a protected-Dagu configuration. Its owner must re-qualify that
expectation before treating it as this host's current mode.

The scoped repository/lane-script search found no demonstrated naive
`export $(cat ...)` loader for `dagu.env`. Known installer copies use value-reader
functions and systemd `EnvironmentFile`; copied trading-arm matches are
heredocs, not evidence of that parser defect. No private environment file or
loader was executed and no peer-owned script was changed. Any additional
alleged co-op loader needs an exact source locator before correction.
The widened Python/Bash-script search found the example inside the staged
dispatcher's task-message string; AST inspection confirms it is an instruction,
not executable loader code. The archived value-reader helpers dot-source shell
assignments and interpret quoting. These source checks do not read their actual
environment files or prove every possible host loader is covered.

If a loader needs correction, reuse shell assignment parsing
(`set -a; . file; set +a`) for a shell assignment file, or native systemd
`EnvironmentFile` for a unit. Do not parse assignment text through command
substitution: quote characters produced by expansion do not become shell
quoting. Systemd does not expand `$` in EnvironmentFile values, so private
deployment paths must follow that interface's documented syntax. No credential
value belongs in a public example. The reported stray quoted home and its
quarantine remain uninspected.

## Consequences and recheck conditions

The public dashboard wording now distinguishes the local operator path from
Viewer observation without changing historical receipts. Native service state,
source findings and structural publication checks stay separate. The paper-lane
owner mapping is recorded as reported metadata; the independent publication read
remains open. No adoption or readiness status is promoted.

Recheck if Dagu's version or auth mode changes, the listener moves, a tunnel or
network deployment is proposed, the inventory changes, or the paper owner
supplies a different DAG classification. A reproduction showing network
exposure or a changed upstream mode invalidates this loopback-only record.
Host changes following any new proposal wait for the command center's ACK;
there is no new host apply step in this PR.

## More information

- `native-agent-stack@c1300c15b42f1a6643f3dc4172f40c01d99abdcd:blueprints/us-equities/hosting/README.md:95-106`
  supplies the existing loopback `none` recipe and operator/Viewer distinction.
- The same pin's `docs/decisions/2026-10-05-dagu-mise-pin-move.md:7,15`
  separates the new-WSL 2.18.2 selection from the trading 2.16.6 hold.
- `dagucloud/dagu@5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4:internal/service/frontend/api/v1/api.go:725,733-742`
  and `:health.go:16-22` define the auth bypass and public health interface.
  [Official 2.18.2 release](https://github.com/dagucloud/dagu/releases/tag/v2.18.2).
- At that Dagu pin, `api/v1/api.yaml:789,12963,13037-13044` supplies the
  supported list, health and parameter-bearing response contracts;
  `internal/persis/file/dag/examples_unix.go:10,29,67,113,155` supplies the five
  example-name associations (source SHA256
  `9100a0b07dde5d63ca1bd3c978fb53e1feef6820987937394df651dd56ad4d35`).
- [curl's supported command-line interface](https://curl.se/docs/manpage.html)
  supplies `--disable` as the first option, proxy bypass and HTTP status
  write-out; [jq 1.8 manual](https://jqlang.org/manual/v1.8/) supplies field
  filtering. No HTTP/JSON wrapper is adopted.
- `systemd/systemd@781d9d0789379d1ea1f2ecefb804d41e9c8b6c38:man/systemd.exec.xml:3107-3109,3145-3182`
  supplies native EnvironmentFile expansion and quoting behavior. The installed
  GNU Bash 5.3 manual, dated 2025-04-07, `QUOTING:1199,1235-1254`, supplies shell
  quote semantics. These are source findings, not an executed loader test.
- `dagucloud/dagu@v2.18.1:scripts/installer.sh:281-285,1036-1056,1647,1751,1763-1770`
  supplies the quote writer and shell-evaluated value-reader helpers matched by
  the archived installer copies. The three selected helper bodies have SHA256
  `3152dedc8920ac57ed56cf495385eb631c92a7958b04cb3820b57f21db0f7768`;
  actual environment files remain unread.
- The forwarded command-center item
  `task-ns2604-coop-20261006T102431Z-prs` has SHA256
  `aedbffe132af2017b918d3b3c6fc3011d746478fdaa60833e7142861b7ff3f33`.
  Its configuration report is kept apart from the native observations in
  [native-observations.json](../../evidence/artifacts/dagu-loopback-auth-none-20261006/native-observations.json).
