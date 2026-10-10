# Review verdicts carry a GitHub App identity

Date: 2026-10-09. Status: accepted by the foundation CC on 2026-10-09. The App waits on the owner's registration (steps below). Until the CC has verified enforcement (see Transition), the interim rule below stays in force.

## Owner direction

On 2026-10-09 a side agent told the owner that every agent session, Claude and Codex alike, uses the owner's one GitHub account. Any session could therefore post the "review passed" commit statuses that the landing scripts had started to read. The agent suggested either a separate GitHub identity for reviewers or a landing check of the written review record. At 22:57Z the owner replied that converged practice should always proceed. This is a paraphrase; the owner's words are not reproduced.

## Problem

- **Anyone with push access can post a status.** GitHub's commit-status API states that "users with push access in a repository can create commit statuses for a given SHA" [statuses], and every session shares that one account.
- **So a review mark proves nothing about the reviewer.** A confused or prompt-injected session can mark risk or order code as reviewed. The security micro on us-equities-trading #42 at `57f68472` (finding N3) found the same gap for the `claude-pr-review` status.

## Decision

1. **One review App.** A GitHub App is registered under the owner's account and installed only on native-agent-stack and us-equities-trading. Its webhook is inactive.
   - Repository permissions: Checks read and write, Commit statuses read and write, Pull requests read, Contents read, Metadata read.
   - It has no comment permission: the check run's output is the visible verdict.
2. **Check runs, not statuses.** A reviewer posts a check run on the exact head SHA, named one of:
   - `trading-cc-read`, for trading-cc's Claude reads;
   - `claude-review/local`, for the local Claude review worker.

   `conclusion` is `success` for PASS or ACK and `failure` for CHANGES_REQUESTED.
   - On public repositories `output.summary` is model-free: the verdict, the count of findings at each P-level, and the record's path relative to the coordination root.
   - Check-run writes are "only available to GitHub Apps" [checks]. The current page also lists fine-grained tokens with Checks write. Either way, the owner's shared token can't post a check run in the App's name.
3. **Tokens.** Each post mints an installation access token through the credential runner: a JWT signed with the App's key, then `POST /app/installations/{installation_id}/access_tokens` [install-token]. api-actions builds the minting into the local review worker.
4. **Key custody.** The private key is a 0600 file outside every worktree, reached by pointer through the credential runner's inventory. The owner moves the downloaded file into custody. No agent reads, prints or copies it.
5. **Landing predicate.** For an essential PR, the CC's landing script resolves the PR's current head SHA at landing time. It then lists that head's check runs by name, with `filter=all` [checks-list], and keeps only runs whose `app.id` equals the App's ID.
   - **Which run counts:** the publisher numbers each verdict for a (head, check name) pair under a per-head lock: attempt 1, 2, 3 and so on. It writes the number into the check run's `external_id` as `attempt-<n>` and publishes only after the previous attempt has finished. The run with the **highest attempt number** is authoritative, and it counts only with `status` `completed` and `conclusion` `success`.
   - **Why not time:** `completed_at` and `started_at` are values the poster supplies when it creates the check run [checks], so they can't show publication order. A later attempt therefore supersedes an earlier one whatever their timestamps say, and an older attempt that completes late never overrides a newer failure.
   - **What blocks:**
     - an App run that is queued or in progress;
     - an authoritative `failure`;
     - a missing or malformed attempt number, or a gap in the numbers;
     - two runs sharing a number;
     - no App run at all.
   - **Rulesets:** pinning the App as the ruleset's expected source of the status check [rulesets] is optional, because a ruleset can't express the essential-path condition.
   - **#42's statuses:** `claude-pr-review` statuses (us-equities-trading #42) come from github-actions[bot]. For those, the script also verifies that the status's run is a trusted `schedule` or `workflow_dispatch` run on main.
   - **Nothing is waived:** an App verdict adds a gate. The co-op GPT read, the non-author trading acknowledgement, CI and the landing script's own readiness decision all still apply. The CC's independent review is preserved.

## Limit, stated plainly

Every agent session runs as the same Unix user, so any session that goes looking can read the key file. That session can then sign a JWT and post a check run as the App directly, without the credential runner.
- **The App ID identifies the credential, not the reviewer.**
- **What version 1 stops:** accidental or confused posting with the ambient owner token, which no longer carries the reviewer's identity.
- **What it doesn't stop:** a session that deliberately reads the key. Such a forgery may leave no runner log, so this record claims no runner audit trail.
- **The interim pair has the same limit.** A status plus a PASS record proves nothing more, since every local session can write the records directory.

App verdicts therefore stay advisory evidence beside the CC's independent review until signing is restricted. GitHub's own guidance is stronger: keep the key in a sign-only vault, from which it "can never be read" [keys]. A runner audit can be claimed only once key access and signing are confined to the runner, under its own Unix user or a sign-only store. That is optional later hardening; the owner has asked for no new security layers for now.

## Interim, in force until the Transition is verified

The CC implemented this on 2026-10-09:
- `trading-cc-read` and `claude-review/local` statuses are advisory, except that a failure blocks landing.
- A success counts only when its named record exists under the coordination root's `trading-cc/reads/` directory and names that head SHA with PASS or ACK.

## Transition

The landing script moves from the interim rule to the App predicate only after the CC has verified enforcement on a non-production PR and recorded a dated receipt. The receipt must show six things:
1. A `success` App check on the current head admits landing.
2. A later App `failure` on the same head blocks it. That includes a failure that is published after an earlier success but carries an earlier `completed_at`, and an older attempt's success that completes after a newer failure.
3. A queued App run blocks it.
4. A `success` check or status from any other source, including the owner token, is ignored.
5. A success on a superseded head doesn't count.
6. A missing, malformed, duplicated or gapped attempt number blocks.

## Compromise and rotation

Credentials are referred to by inventory id and pointer only, never by value.
1. **On suspected compromise, the CC stops trusting App verdicts at once.** Since the attempt numbers are written by whoever holds the key, they are only as trustworthy as the key. The landing script falls back to the interim rule, and the CC records the time.
2. **The owner suspends the installation.** While it is suspended, "the GitHub App cannot access resources owned by that installation account", and GitHub gives leaked credentials as a reason to do this [suspend]. Suspension also covers any outstanding installation tokens. A token still held by a trusted process can be revoked with `DELETE /installation/token` [installations].
3. **The owner generates a new key, then deletes the old one** under Credentials → Key pairs. GitHub requires a new key before an existing one can be deleted, and "Private keys do not expire and instead need to be manually revoked" [keys]. Deleting the local PEM file revokes nothing; only deletion on GitHub does.
4. **The owner places the new key in custody** through the credential tooling, under the same pointer, as in Owner steps 3. The CC verifies the key's fingerprint against the one GitHub shows, using the documented `openssl` command [keys], without printing the key.
5. **Re-enable after independent verification.** The owner unsuspends the installation. The CC re-runs the Transition checks and records a dated receipt before App verdicts count again.

Routine rotation follows steps 3–5 without suspension. GitHub allows up to 25 keys per App so keys can rotate without downtime [keys].

## Alternatives considered

| Alternative | Outcome |
| --- | --- |
| Keep commit statuses posted with the owner's token | Rejected: GitHub can't tell the reviewer from any other session. |
| Verify only the written record | Kept as the interim and as defence in depth. Every local session can write that directory too, so it isn't an identity. |
| One App per reviewer role | Deferred. One App with distinct check names gives the identity with a single key to keep. |
| Per-session fine-grained tokens without status write | A possible later layer. It narrows who can post but gives the verdict no identity of its own. |

Two developments would overturn this decision:
- GitHub attributing commit statuses per token in a way rulesets can pin;
- the review worker moving to a hosted service that has its own identity.

## Owner steps

These need the owner's login [register] [install-own] [keys]:
1. **Register the App.** Go to Settings → Developer settings → GitHub Apps → New GitHub App (<https://github.com/settings/apps/new>).
   - Pick a name that is unique on GitHub and at most 34 characters.
   - Set the homepage URL to the native-agent-stack repository.
   - Clear the Webhook "Active" box.
   - Set the permissions in Decision 1, and choose "Only on this account".
2. **Install it.** On the App's page, choose Install App → Install → "Only select repositories", then select native-agent-stack and us-equities-trading.
3. **Create the key.** On the App's page, choose Credentials → Key pairs → New key; the browser downloads a PEM file.
   - Move it yourself into the credential runner's custody directory as a 0600 file, then delete the download.
   - Don't paste it into any session.
4. **Tell the CC.** Send the CC the App ID and the installation ID; neither is secret. The CC registers the key's pointer and then runs the Transition checks.

## Sources

Fetched 2026-10-09 between 22:58Z and 23:37Z.

| Key | Source |
| --- | --- |
| statuses | <https://docs.github.com/en/rest/commits/statuses#create-a-commit-status> |
| checks | <https://docs.github.com/en/rest/checks/runs> |
| checks-list | <https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference> (`check_name`, `status`, `filter=latest\|all`) |
| rulesets | <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-status-checks-to-pass-before-merging> |
| register | <https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app> |
| install-own | <https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app> |
| keys | <https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps> (storing, deleting and verifying private keys) |
| install-token | <https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app> |
| suspend | <https://docs.github.com/en/apps/maintaining-github-apps/suspending-a-github-app-installation> |
| installations | <https://docs.github.com/en/rest/apps/installations#revoke-an-installation-access-token> |
| #42 N3 | us-equities-trading #42, security micro at `57f68472` |
