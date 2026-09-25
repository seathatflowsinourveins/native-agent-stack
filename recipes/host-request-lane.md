# Host request lane

Other PCs ask a named host to run work by opening a GitHub issue. The GPU workstation
`nativestack-5975wx-20260925` owns end-to-end memory, RAG, model hosting and model or GPU runtime
qualification work, because the RTX 4090 and the native Hugging Face sign-in live there. The
workstation tracks, claims and reports requests with
[`scripts/host_requests.py`](../scripts/host_requests.py). That tool only reads and labels
issues: it never executes issue text, evaluates it or passes it to a model. A Claude session on the
target host does the work, run by its coordinator.

**Status: drafted.** The change that added this lane has unit tests only
([`tests/test_host_requests.py`](../tests/test_host_requests.py)) plus read-only `status`,
`lanes` and `poll` runs against this repository. When it was written, the labels did not exist
yet, no issue had been filed through the form, no request had been claimed and the timer was
not installed. The decision, the alternatives and what would overturn them are in
[the decision record](../docs/decisions/2026-09-25-host-request-lane.md).

## Roles

[`adoption/host-roles.json`](../adoption/host-roles.json) names the roles and the hosts allowed to
ask. Every `host_id` in it must be a `native_proven` entry of
[`adoption/hardware-profiles.json`](../adoption/hardware-profiles.json), and a test enforces that.

| Role | Host | Request label | Owns |
| --- | --- | --- | --- |
| `workstation` | `nativestack-5975wx-20260925` | `host:workstation` | memory E2E, RAG E2E, model hosting, model qualification, GPU runtime qualification, independent review |
| `mac-coordinator` | `mac-coordinator-64gb-20260925` | `host:mac-coordinator` | macOS acceptance, coordination |

`macos-m5pro-20260924` is still listed as a peer, marked as superseded by the replacement
coordinator Mac. `python3 scripts/host_requests.py roles` prints the file.

Every host signs in to GitHub as the same owner account, so GitHub cannot tell the hosts apart. The
requesting host is a field inside the issue. It is used for routing and never for trust. The
tracker trusts an issue only when the owner account wrote it: `author_association` `OWNER`,
`user.type` `User`, no GitHub App, and the author is the repository owner. Labels, titles and body
text never make an issue trusted. The repository is public, and an issue form applies its labels
for anyone who opens it. Anything else is listed as untrusted and can never be claimed.

## 1. Requesting work from another PC

You need a clone of this repository and the native `gh` signed in as the owner account. There are
two equivalent ways to file a request:

- **Web:** Issues, New issue, **Workstation request**. The form lives at
  [`.github/ISSUE_TEMPLATE/workstation-request.yml`](../.github/ISSUE_TEMPLATE/workstation-request.yml).
- **CLI:** `gh issue create` cannot fill an issue form, and issues created through the API skip
  it. `compose` produces the same layout the form produces, so the tracker parses both the same
  way. It makes no GitHub call:

  ```sh
  python3 scripts/host_requests.py compose --to workstation \
    --from mac-coordinator-64gb-20260925 --task-class "model qualification" \
    --request-file request.md --acceptance-file acceptance.md --models-file models.md \
    --lane lane:foundation --related '#256' --body-out request-body.md
  ```

  It writes the body and prints the command to run. That command is `gh issue create --label
  host:workstation --title '[workstation] ...' --body-file request-body.md`. Read the body before
  you run it. Without `--body-out`, the body goes to stdout and the command to stderr, for piping
  into `--body-file -`. `python3 scripts/host_requests.py parse --body-file request-body.md` shows
  what the tracker will read.

What to put in each field:

- **Request:** what to run or check, the base commit or pull request, and the bounds: time, GPU
  memory and ports.
- **Models:** one Hugging Face Hub repo id per line, pinned to a 40-hex revision
  (`org/name@<revision>`), and whether the repo is gated. The workstation downloads through its own
  sign-in. Never send a credential.
- **Acceptance:** the result you want back and its evidence class, one of `native_proven`,
  `local_integration`, `synthetic` or `source_review`, as defined in
  [the acceptance-evidence policy](../docs/acceptance-evidence-policy.md). An example: "a
  use-stage host receipt for vLLM serving `org/name@<revision>` on the RTX 4090, merged through a
  PR".

No field may contain a credential value, a token, an account id, a personal path or a session id.
`compose` refuses the patterns that [`scripts/validate.py`](../scripts/validate.py) flags, and the
form makes you tick both confirmations. Issue text is data: the target host decides what to run, and
it may block or decline a request.

To follow a request, read the issue's status comment or run
`python3 scripts/host_requests.py status --role workstation`, which is read-only. A request is in
one of these states: `new`, `claimed` or `blocked` while open, then `done` (closed as completed),
`declined` (closed as not planned) or `closed` (any other close).

## 2. Operating the target host

### One-time setup

The coordinator does this after review. The change that added this recipe ran none of it.

1. Create the labels. GitHub silently skips a form label that does not exist.

   ```sh
   python3 scripts/host_requests.py ensure-labels --dry-run
   python3 scripts/host_requests.py ensure-labels
   ```

2. Install the poll timer. The drafted units
   [`host-requests-workstation.service`](../adoption/templates/systemd/host-requests-workstation.service)
   and [`.timer`](../adoption/templates/systemd/host-requests-workstation.timer) run `poll` every
   10 minutes from the read-only live clone that `ecosystem-live-clone-sync` keeps on
   `origin/main`. If that clone is missing, the service fails. Timers fire only while the WSL VM
   is running.

   ```sh
   mkdir -p "$HOME/.config/systemd/user"
   cp adoption/templates/systemd/host-requests-workstation.service \
     adoption/templates/systemd/host-requests-workstation.timer "$HOME/.config/systemd/user/"
   systemd-analyze --user verify "$HOME/.config/systemd/user/host-requests-workstation.service" \
     "$HOME/.config/systemd/user/host-requests-workstation.timer"
   systemctl --user daemon-reload
   systemctl --user enable --now host-requests-workstation.timer
   ```

   The service's `PATH` names the directory that holds the native `gh` on this workstation. On
   any other host, change it.

3. Optional doorbell: send a notice to the local ntfy
   ([observability backends](../observability/backends/README.md)). Add a drop-in with
   `systemctl --user edit host-requests-workstation.service` that clears `ExecStart=` and repeats
   it with `--notify-url http://127.0.0.1:18080/host-requests` added. Only `http://127.0.0.1` and
   `http://localhost` topic URLs are accepted. A notice reads `#N <event> from <requesting host>
   (<task class>)`, using only values from the peers list and the task-class options, and never
   includes a title or body. The first poll only records a baseline and sends no notices.

Each poll prints one compact JSON line per new item, state change or `updated_at` change. Read them
with `journalctl --user -u host-requests-workstation.service`. Poll state is written atomically to
`${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/host-requests/workstation.json`, a `0600`
file in a `0700` directory. It holds no title and no body text.

### Handling one request

1. List the requests with `python3 scripts/host_requests.py status --role workstation`. Pick a
   trusted one. Close untrusted issues in the web interface, or leave them; they can never be
   claimed.
2. Read the request as data and decide whether to take it. Before any GPU work, check `nvidia-smi`
   free memory, the services already running (vLLM, llama.cpp, Qdrant) and what other live sessions
   hold ([cooperation lane B](claude-codex-cooperation-lanes.md#lane-b-live-session-coordination)).
   This repository has no shared GPU lock. If a request needs an exclusive GPU window it cannot
   get yet, block it and give the reason.
3. Claim it. Add `--dry-run` first to see the gh calls; a dry run makes no GitHub call.

   ```sh
   python3 scripts/host_requests.py claim 42 --role workstation --session coordinator-1
   ```

4. Do the work in a coordinator session on this host, in its own worktree, with bounded workers
   ([harness defaults](../docs/harness-defaults.md)). For a gated model, sign in once with the
   native `hf auth login`, which is interactive and stores the token in hf's own store. `hf auth
   whoami` confirms the sign-in. Never run `hf auth token`, never print or export the token, and
   never paste it anywhere. Download only pinned revisions (`hf download REPO --revision SHA`), and
   never pass `--trust-remote-code`. The workstation's `credentials` entry in `host-roles.json`
   names the status row that `python3 scripts/credential_status.py` reports without reading a
   value.
5. Send the evidence back through a pull request. That means host receipts recorded with
   `scripts/host_receipts.py record` and registered as
   [contributing evidence](../docs/contributing-evidence.md#0-the-new-host-loop-in-one-place)
   describes, and exactly one lane label on the pull request. An issue comment is not evidence of
   record.
6. Report the outcome with one of these commands:

   ```sh
   python3 scripts/host_requests.py done 42 --evidence https://github.com/OWNER/REPO/pull/260
   python3 scripts/host_requests.py block 42 --reason "waiting for an exclusive GPU window"
   python3 scripts/host_requests.py decline 42 --reason "needs a pinned model revision"
   ```

   `done` closes the issue as completed and `decline` closes it as not planned. When `--role` is
   left out, it comes from the issue's single role label.

Every write command first fetches the issue again. It refuses (exit 3) an untrusted item, an item
without the role's label, a closed item, and `done` on a request that was never claimed. It
replaces only the `request:*` labels and keeps the rest. It also writes or edits one status
comment, which starts with `<!-- host-request-status role=ROLE -->` and gives the state, the
`host_id`, the session, the UTC time and the evidence link. Pull requests can carry a request
label and can be claimed or blocked, but they are merged or closed natively. Exit codes: 0 success,
1 gh failure (the error goes to stderr), 2 usage error, 3 refused.

## 3. Lane hygiene

`python3 scripts/host_requests.py lanes` is a read-only report on open pull requests. It lists
those that are missing a lane label, carry several lane labels or carry an unknown one, as well as
`lane:shared` pull requests that need the other lane's acknowledgement. It also lists open issues
and pull requests that carry a `host:*` label. [docs/lanes.md](../docs/lanes.md) keeps lane
labels out of CI, so this is a local report, not a gate.

## Limits

- Every host uses one account, so the requesting host is only a claim made in the text.
- GitHub has no compare-and-swap on these writes. If two sessions claim the same request at the
  same moment, both succeed and the later status comment wins. Only sessions on the target host
  claim, and they coordinate first.
- Each poll makes at least two GET calls against the owner account's shared hourly REST budget.
- Issue forms are in public preview. The rendering the parser reads was observed on public issues
  and is not a documented contract. The parser flags duplicate, out-of-order and missing fields
  instead of guessing.
