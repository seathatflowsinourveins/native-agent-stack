# Review verdicts carry a GitHub App identity

Date: 2026-10-09. Status: accepted by the foundation CC on 2026-10-09. The App waits on the owner's registration (steps below); until its first check run, the interim rule below is in force.

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
5. **Landing.** For essential PRs, the CC's landing scripts require a check run on the exact head with the right name and an `app.id` equal to the App's ID.
   - Pinning the App as the ruleset's expected source of the status check [rulesets] is optional, because a ruleset can't express the essential-path condition.
   - `claude-pr-review` statuses (us-equities-trading #42) come from github-actions[bot]. For those, the scripts also verify that the status's run is a trusted `schedule` or `workflow_dispatch` run on main.

## Limit, stated plainly

Every agent session runs as the same Unix user, so any session that goes looking can read the key file. Version 1 therefore gives an **auditable identity, not isolation**:
- A session can no longer post a verdict with the ambient owner token.
- A forgery now takes a deliberate, logged call to the credential runner.

GitHub's own guidance is stronger: keep the key in a sign-only vault, from which it "can never be read" [keys]. Moving the runner to its own Unix user, or to a sign-only store, is optional later hardening. The owner has asked for no new security layers for now.

## Interim, in force until the App's first check run

The CC implemented this on 2026-10-09:
- `trading-cc-read` and `claude-review/local` statuses are advisory, except that a failure blocks landing.
- A success counts only when its named record exists under the coordination root's `trading-cc/reads/` directory and names that head SHA with PASS or ACK.

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
4. **Tell the CC.** Send the CC the App ID and the installation ID; neither is secret. The CC registers the key's pointer, and the App's first check run moves the landing scripts off the interim rule.

## Sources

Fetched 2026-10-09 between 22:58Z and 23:01Z.

| Key | Source |
| --- | --- |
| statuses | <https://docs.github.com/en/rest/commits/statuses#create-a-commit-status> |
| checks | <https://docs.github.com/en/rest/checks/runs> |
| rulesets | <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-status-checks-to-pass-before-merging> |
| register | <https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app> |
| install-own | <https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app> |
| keys | <https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps> |
| install-token | <https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app> |
| #42 N3 | us-equities-trading #42, security micro at `57f68472` |
