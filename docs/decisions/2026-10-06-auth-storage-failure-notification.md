# Ring for authentication storage failures that need the user

Date: 2026-10-06. Owner: currency, under the command center's Q55 ruling.
This serves unattended native-client recovery during north-star R&D: a user
action must be audible while routine completion remains quiet.

## DECISIONS

| Date | Installed client observed by the host gate | Notification type | Decision | Reason |
| --- | --- | --- | --- | --- |
| 2026-10-06 | Claude Code 2.1.291 | `auth_storage_failure` | **RING** | A credential-storage or sign-in event that needs the user is an escalation under the user's quiet-bell-only-for-escalations rule (Q55). |

The executable row is in
[`notification_types_scan.py:23`](../../evidence/artifacts/notification-types-20260929/notification_types_scan.py).
Its documentation flag is false against the existing reference snapshot fetched
2026-09-29; this is not a claim that current upstream documentation omits it.
The source overlay names the new ring type and the deliberate coverage count
becomes 18. The host currency gate and the scanner's fail-closed checks retain
their predicates. Applying a live client configuration remains the CC's action.
The marked operative matcher in the recipe and maintained terminal decision
uses the same source list; their earlier host observations retain their dates.

## Exact observed evidence

Fixwave-defects' host-only currency gate ran
`tests.test_windows_terminal_defaults.OverlayTests.test_the_installed_client_knows_no_notification_type_without_a_decision`
at `tests/test_windows_terminal_defaults.py:166-176`. Its native version command
was `$HOME/.local/bin/claude --version`, exit 0, returning
`2.1.291 (Claude Code)` at 2026-10-06T15:12:17Z. Its exact returned failure was:

```text
AssertionError: Lists differ: ['auth_storage_failure'] != []

First list contains 1 additional elements.
First extra element 0:
'auth_storage_failure'

- ['auth_storage_failure']
+ [] : a type this client knows has no decision in DECISIONS
```

The installed client's new type is the observation; the failure is an unknown
decision, not evidence that an authentication failure occurred. The original
failure remains retained in fixwave-defects' `ci-repair-20261006.json`
`host_only_open_gap`, with version, exact output and gate/table locators.

Canonical source before this addition:
[native-agent-stack@0d5e6506: notification_types_scan.py:20-38](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/evidence/artifacts/notification-types-20260929/notification_types_scan.py#L20-L38)
and [installed-client gate:166-176](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/tests/test_windows_terminal_defaults.py#L166-L176).
The earlier policy's single executable table and matcher agreement are retained;
the command center assigned the new classification in Q55, item
`task-ns2604-coop-20261006T151719Z`, section C2.

## Scope and reopening

This is a dated operator policy plus installed-client/source observation.
The added source matcher and coverage count are integration consistency;
neither is an actual bell emission or a live configuration application.
No credential value or credential file was read, and no sign-in was attempted.
The lane does not change installed client configuration or notify the user by
emitting a bell during this check.

Reopen the decision if the client's event no longer needs user action, or if
the user changes the escalation-only bell rule. A later Notification type still
fails the unchanged currency gate until its own decision is recorded.
