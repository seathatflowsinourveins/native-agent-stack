# Decision: host requests go through GitHub issues and are tracked on the target host (2026-09-25)

**Decided by:** the foundation-lane writer on branch `claude/workstation-requests-20260925`
(base `origin/main@3f267b5c`), working from the coordinator's brief and an earlier read-only
audit. The audit's findings were used as leads and checked against the original sources below.

**Scope:** [`adoption/host-roles.json`](../../adoption/host-roles.json), the issue form
[`.github/ISSUE_TEMPLATE/workstation-request.yml`](../../.github/ISSUE_TEMPLATE/workstation-request.yml),
[`scripts/host_requests.py`](../../scripts/host_requests.py) and its tests, the drafted units
`adoption/templates/systemd/host-requests-workstation.{service,timer}`, and the recipe
[`recipes/host-request-lane.md`](../../recipes/host-request-lane.md). Lane: `lane:foundation`.
This change does not touch `docs/lanes.md`, `AGENTS.md`, the grand-dashboard `state.json` or any
workflow.

## Context

- Every PC signs in to GitHub as the same owner account, and the repository is public. GitHub
  therefore cannot tell hosts apart. Hosts already identify themselves in text, for example in the
  comments on #140.
- The workstation `nativestack-5975wx-20260925` holds the RTX 4090 and the native Hugging Face
  sign-in. End-to-end memory, RAG, model hosting and qualification work belongs there. Other PCs
  need a way to ask for that work and see what came back.
- Measured with read-only `gh api` calls on 2026-09-25:
  - Owner-created issues and pull requests (#253 to #257) carry `author_association` `OWNER`,
    `user.type` `User` and `performed_via_github_app: null`.
  - The owner's comments on #140 carry the same three values.
  - The saturation workflow's issue #173 is `CONTRIBUTOR` with `user.type` `Bot`.
  - A percent-encoded `labels=lane%3Afoundation` filter returns only items with that label.
  - The open issue list held 13 pull requests, and 6 of them had no lane label.

## Decision

1. **A request is an issue** that carries the target role's `host:ROLE` label.
   - Web requesters use the issue form.
   - CLI requesters run `host_requests.py compose` and then `gh issue create`. `compose` renders
     the form's layout, because issues created through the API skip the form.
   - Roles and the hosts allowed to ask are data in `adoption/host-roles.json`. Every `host_id`
     there must be a `native_proven` entry of `adoption/hardware-profiles.json`, which a test
     enforces. `macos-m5pro-20260924` stays a peer, marked as superseded by
     `mac-coordinator-64gb-20260925`; the source is the #253 body, "the replacement coordinator
     Mac".
2. **Trust rests only on the owner account's own authorship.** An item must have
   `author_association` `OWNER`, `user.type` `User`, `performed_via_github_app` present and
   null, and an author login that equals the repository owner.
   - Any missing field fails closed.
   - Labels, the title, the body and the requesting-host field never grant trust. A form applies
     its labels for whoever opens the issue.
   - An untrusted item is listed and can never be claimed.
   - The status comment is found by its marker and by the owner's authorship, so a comment
     that copies the marker is never edited or adopted.
3. **State comes only from labels and the close reason.**
   - An open request is `new`, `claimed` (`request:claimed`) or `blocked` (`request:blocked`).
   - A closed request is `done` when `state_reason` is `completed` and `declined` when it is
     `not_planned`.
   - Any other close, such as `duplicate` or a merged pull request's null reason, is `closed`.
   - `claim` and `block` replace the `request:*` subset with exactly one label and keep every
     other label.
   - `done` and `decline` clear that subset and close the issue, because the four fixed labels
     include no done or declined label and the close reason carries that state.
   - Each transition also creates, or edits in place, one status comment that starts with
     `<!-- host-request-status role=ROLE -->`.
4. **The tracker never executes, evaluates or forwards issue text to a model.**
   - Its only subprocess is `gh api` with list arguments. `gh` keeps the token, and the script
     never reads it.
   - Execution is coordinator-run: a Claude session on the target host reads the request as data
     and decides what to run.
5. **Only five commands write:** `claim`, `block`, `done`, `decline` and `ensure-labels`. Each
   takes `--dry-run`, which prints the gh argv and payloads and makes no GitHub call. The author
   of this change ran every write command with `--dry-run` only.
6. **A systemd user timer is the watcher.**
   - It runs a oneshot `poll` every 10 minutes from the read-only live clone that
     `ecosystem-live-clone-sync` keeps on `origin/main`.
   - It uses monotonic triggers and no `Persistent=`.
   - `poll` diffs against a `0600` state file in a `0700` directory. It can send an optional
     fixed-format notice to a loopback ntfy topic, and that notice never includes a title or body.
   - The unit runs at `Nice=10` with best-effort I/O priority 7. It does not sandbox the network:
     a user unit has no measured way to allow "GitHub only". The script is what limits network use:
     its only subprocess is `gh`, and its only other request is the optional loopback POST, sent
     with no proxy and no redirects.

## Evidence

Official sources were read at pinned revisions: `github/docs@4dd05e9d` (committed
2026-09-25T14:35Z), `github/rest-api-description@d66b5eca` (committed 2026-09-25T06:50Z), and the
code.claude.com Markdown pages fetched at 2026-09-25T15:59Z.

- **Issue forms**,
  <https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms>:
  - Forms are YAML files in `/.github/ISSUE_TEMPLATE`, and `name`, `description` and `body` are
    required.
  - On `labels`: "If a label does not already exist in the repository, it will not be
    automatically added to the issue." The recipe therefore runs `ensure-labels` first.
  - "Issue forms are currently in public preview and subject to change."
  - No `config.yml` is added, so blank issues stay available.
- **Form schema**,
  <https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema>:
  - `id` "Can only use alpha-numeric characters, `-`, and `_`. Must be unique in the form
    definition."
  - `required` "Prevents form submission until element is completed. Only for public
    repositories."
  - Dropdown `options` "Cannot be empty and all choices must be distinct."
  - [Common validation errors](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/common-validation-errors-when-creating-issue-forms)
    adds forbidden words in input and textarea labels, the reserved dropdown option "None", and
    keys forbidden because YAML reads them as booleans.
  - `tests/test_host_requests.py` checks these rules on the form's text, and checks it against
    PyYAML when PyYAML is installed.
  - As a supplementary community check, not GitHub's own validator, the form validated with 0
    errors against SchemaStore's
    [`github-issue-forms.json`](https://json.schemastore.org/github-issue-forms.json), fetched
    2026-09-25 with sha256 `c2722dbf00334ce4fdeffa960b8c9047caf4f1cbb8f3809663f4d604b1d3ae76`.
    A mutant with an invalid id and a duplicate option gave 2 errors. GitHub validates the form
    only when the file is viewed on github.com or used after merge.
- **Form rendering** (observed on public issues, not documented):
  - astral-sh/uv#21986 shows `### <label>` sections separated by a blank line, `_No response_`
    for an empty field and no trailing newline.
  - RimSort/RimSort#2442 shows a dropdown rendered as the chosen option.
  - vitejs/vite#23549 shows checkboxes rendered as `- [x] <option>`. The same body also contains
    a heading the requester typed inside a textarea, which is why the parser splits only at known
    field headings.
- **REST issues**, <https://docs.github.com/en/rest/issues/issues>:
  - "Issues endpoints may return both issues and pull requests in the response. You can identify
    pull requests by the `pull_request` key."
  - `author_association` is "How the author is associated with the repository", with the values
    `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIMER`, `FIRST_TIME_CONTRIBUTOR`, `MANNEQUIN`, `MEMBER`,
    `NONE` and `OWNER`.
  - On update, `labels` means "Pass one or more labels to _replace_ the set of labels on this
    issue", and `state_reason` takes `completed`, `not_planned`, `duplicate` or `reopened`.
  - `since` means "Only show results that were last updated after the given time", so `status`
    also checks `closed_at` against the 14-day window.
  - Neither `author_association` nor `performed_via_github_app` is in the issue schema's
    `required` list, hence the fail-closed checks.
- **Self-hosted runners on a public repository:**
  - <https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners>:
    "We recommend that you only use self-hosted runners with private repositories. This is because
    forks of your public repository can potentially run dangerous code on your self-hosted runner
    machine by creating a pull request that executes the code in a workflow."
  - <https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners>:
    "self-hosted runners should almost never be used for public repositories on GitHub, because
    any user can open pull requests against the repository and compromise the environment."
- **Timer semantics:** `man systemd.timer` on this host (systemd 255.4-1ubuntu8.17) says of
  `Persistent=`: "Note that this setting only has an effect on timers configured with
  OnCalendar=". The same page says `OnStartupSec=` "is primarily useful when configured in units
  running in the per-user service manager".
  - `systemd-analyze --user verify` passed on scratch copies of both units.
  - A negative control (an unknown key, an unparsable time span and a missing executable) failed
    it with exit 1.

## Alternatives rejected

- **A self-hosted Actions runner with claude-code-action.** GitHub's guidance above rules out a
  runner on this public repository, and `tests/test_workflow_hardening.py` fails any job whose
  `runs-on` is not a GitHub-hosted ubuntu or macos label. The Claude Code GitHub Actions page
  says the action "runs on GitHub-hosted runners" and keeps the Anthropic credential as a
  repository secret. A GitHub-hosted runner has no RTX 4090 and no Hugging Face sign-in.
- **Cloud routines or RemoteTrigger.** Routines "execute on Anthropic-managed cloud
  infrastructure, or on your organization's self-hosted environment", and they are in research
  preview. Their GitHub triggers cover two event categories, Pull request and Release, and no
  issue event. Self-hosted environments "are in public beta on Team and Enterprise plans and are
  off by default". A cloud run would not reach this host's GPU or sign-ins.
- **A session-only `/loop` or CronCreate as the durable watcher.** The scheduled-tasks page says
  "Tasks are session-scoped", "Recurring tasks automatically expire 7 days after creation", tasks
  "only fire while Claude Code is running and idle", and there is "No catch-up for missed fires."
  These tools stay fine for watching inside one session, but not as the lane's watcher.
- **Remote Control or cross-session messaging as the queue.** Remote Control needs the local
  process to keep running, and messaging is a live channel: a message "can't approve anything",
  and "Commands don't run". Neither gives a durable, auditable queue that other PCs can read. Both
  remain optional: a person can drive the workstation interactively, or send a doorbell message
  that points at the issue.
- **Dagu as the poller.** Dagu 2.16.6 is installed on this host, with a reviewed `native_proven`
  use receipt
  ([`nativestack-5975wx-20260925--dagu--use--20260925.json`](../../evidence/hosts/nativestack-5975wx-20260925/nativestack-5975wx-20260925--dagu--use--20260925.json)),
  and it would be a valid later swap: a DAG running the same `poll` command would add retries and
  run history. For a read-only 10-minute poll, a user timer with a oneshot unit is the pattern
  this repository already ships (the grand dashboard, `codex-broker-reaper`) and needs no
  scheduler service to be up.
- **Auto-executing requests with `claude -p`.** That would feed untrusted issue text to a model
  that has tools. Anyone can open an issue on a public repository, and even the owner's text is
  data, not an instruction. Execution stays coordinator-run.
- **Webhooks instead of polling.** The host exposes no inbound endpoint. GitHub says CLI webhook
  forwarding "is only designed for use during testing and development. It is not supported for
  use in production environments for handling live webhooks."

## Comparisons that would overturn this

- **The repository becomes private.** GitHub's runner guidance no longer rules a runner out. Then
  compare a self-hosted runner lane with this tracker on time from request to claim, on
  auditability and on the exposure of the workstation's sign-ins.
- **Routines gain an issues trigger and can run on this host's hardware under this account's
  plan.** Then compare them with the timer on latency, missed or duplicated events over a week,
  and cost.
- **Hosts get distinct GitHub identities**, such as per-host machine accounts or a GitHub App per
  host. Trust could then be per host, and the requesting-host field would stop being only a claim.
- **The timer misses events.** If the journal shows poll gaps longer than 20 minutes while the VM
  was up, or an event lost between two polls, move the poll to a Dagu DAG and compare the two
  over the same week.
- **GitHub changes the form rendering.** A real form-created issue that `parse` misreads reopens
  the parser. The first real form submission is the check for that.
- **A second executor appears for one role.** GitHub offers no compare-and-swap on these writes,
  so concurrent claims would race. Add a claim lock or split the role.

## Evidence class

This is a drafted lane. Its evidence is `local_integration`, `synthetic` and `source_review` only.

- `tests/test_host_requests.py` has 39 tests. They pass under `/usr/bin/python3` 3.12.3 and
  under Python 3.13 run through uv with the CI requirements, which skips the one PyYAML
  cross-check; that check passes when PyYAML is added.
- A mutation check killed all 12 mutants of the trust, state, label, dry-run, notice, parse and
  state-file code.
- Read-only `status`, `lanes` and `poll` runs against this repository returned well-formed JSON
  with 0 requests, because no request label existed yet.
- `systemd-analyze --user verify` passed on copies of the units.

Not done yet: creating the labels, filing an issue through the form, any claim, block, done or
decline on GitHub, installing the timer, sending an ntfy notice, and executing a request end to
end. The lane becomes `native_proven` only after those have run and been recorded.
