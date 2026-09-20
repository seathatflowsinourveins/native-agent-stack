# Convergence architecture for native engineering work

Start with one engineering outcome and the evidence needed to accept it. This
guide connects research, implementation, native Codex/Claude workers, validation
and recovery. It applies to an ordinary software repository before adding a
specialized research, data or GPU layer. The financial blueprints remain useful
worked examples; their data and broker gates do not become general engineering
prerequisites.

Use the [adoption manifest](../adoption/manifest.json) to select an existing
profile, the [update protocol](../adoption/update.md) to preserve an accepted
installation, and the [convergence blueprint](../blueprints/convergence-practice/README.md)
to evaluate a proposed change. Source pins live in
[the stack manifest](../manifests/stack.json); evidence classes and publication
limits live in [the evidence guide](evidence.md).

The working sequence is:

```text
Outcome + acceptance test
        ↓
Current baseline + one decision-changing gap
        ↓
Primary-source review + frozen task envelope
        ↓
Native worker in an owned checkout
        ↓
Independent checks + complete attempt record
        ↓
Retain / trial / adopt within scope / defer / reject
        ↓
Recoverable handoff + next unresolved gate
```

## 1. Make the task envelope the entry point

Before a worker starts, give it a compact contract: the requested result, exact
repository revision, allowed paths, relevant source references, acceptance
commands, task owner, available runtime, limits, output destination and stop
conditions. Include only the project rules that affect this task. Resolve
missing prerequisites before asking an agent to rediscover the whole ecosystem.

For a small bug fix, the envelope should identify the failing behavior and
meaningful regression test, rather than prescribe every edit. For research,
freeze the question, corpus, scoring rule and required uncertainty handling.
Keep complete logs and source bytes outside the prompt, with precise locators
and hashes in the handoff.

The proposed [contract reference](../blueprints/convergence-practice/contract-reference.md)
and [schema](../blueprints/convergence-practice/contract.schema.json) accompany
the [convergence validator](../scripts/validate_convergence.py) in this integration
wave:

```sh
python3 scripts/validate_convergence.py RECORD.json --root . --json
```

`RECORD.json` means the selected contract/receipt described by that reference.
Schema validation checks recorded structure and evidence references; it does
not enforce permissions, reserve resources or run the acceptance task. These
links are integration dependencies until the coordinator includes those files.

## 2. Review a component against the gap it would close

Use owned repositories, stars and curated lists to discover candidates. Read
the current primary documentation and exact source/release before adoption.
Record license, platform and dependency compatibility, overlap with the current
stack, installation scope, rollback and the result that would justify a switch.
A newer release can reopen a decision without changing the accepted pin.

Compare the working baseline with the smallest useful alternative. The existing
[external retrieval experiment](../blueprints/convergence-practice/arb-trace2code/README.md)
and [local documentation experiment](../blueprints/convergence-practice/local-fixture/evaluation.md)
favor different rankers on different tasks. That supports evaluating the target
workload, not selecting a universal retrieval winner. A catalog entry alone
never triggers installation or qualifies another machine.

## 3. Keep instructions, retrieval and durable state distinct

Keep the always-loaded repository contract short. Load detailed skills for the
current operation. Start a known-code question with exact identifiers or syntax
search; use the selected conceptual index for cross-file questions and the
selected document collection for source material. Verify retrieved passages
against the actual revision before editing. An empty, stale or wrong-project
result should remain visible rather than be replaced with a plausible answer.

Save approved decisions with project scope, rationale, source revision and the
condition that would reopen them. Preserve unfinished proposals in an explicit
outbox. Do not turn every conversation into permanent guidance or copy another
host's live memory/index database into the worker. Reuse a decision only while
its assumptions still apply.

The [memory lifecycle fixture](../blueprints/us-equities/memory-lifecycle/README.md)
demonstrates scoped retrieval and explicit deletion in a disposable store. Its
expiry observation is narrower than immediate access revocation. Historical
native hooks and memory receipts retain their original scope; this guide does
not silently enable capture or claim those earlier configurations were absent.

## 4. Give each native worker one owner and an actual base

The coordinator owns requirements and integration. Each writing worker owns one
checkout and a bounded set of paths. Accounts, global settings and shared
services need a separate designated writer because worktrees do not isolate
them. Read-only research workers should return findings and evidence, leaving
implementation to the assigned writer.

Codex roles without model/effort overrides inherit those settings from the
parent; explicit spawn or role settings can change them. Claude's
`model: inherit` and omitted `effort` preserve the session choices, subject to
its native override rules. Inspect actual behavior rather than assuming a
configuration name proves inheritance. Claude's native worktree isolation can
start from the default branch, so compare its actual Git base with the task
envelope before edits. [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Claude subagents](https://code.claude.com/docs/en/sub-agents).

Delegate independent work when it improves the task. A child has its own model
and tool activity, so parallelism can increase total usage. Avoid nested workers
and repeated reviews without a concrete unresolved question. Permission settings
enforce access; prose such as “read only” is not itself an isolation mechanism.

## 5. Preserve native context and cache behavior

Treat model choice, reasoning effort, orchestration and authentication as
separate settings. Codex's native Ultra supports parallel work. Its experimental
same-task context management uses
`features.context_management.experimental_mode = true` for eligible accounts
and requires a new task. Configuration presence alone is not activation evidence.
[Codex models](https://learn.chatgpt.com/docs/models).

Claude Ultracode combines `xhigh` reasoning with dynamic workflows. The native
setting is `ultracode: true`; it is not an external repository or a persisted
`effortLevel` value. Model capability and workflow availability still apply.
Keep the requested model and record the one that actually ran. The `best` alias
can resolve to Fable, whose usage-credit behavior requires an account-specific
check before unattended work. [Claude model configuration](https://code.claude.com/docs/en/model-config).

Keep stable prefixes, deferred tool discovery and native compaction. Ordinary
Claude subagents build their own caches; a fork carries the parent's context
and can reuse its prefix. Subscription main-conversation cache lifetime and
worker cache lifetime differ. Matching workflow agents can share their initial
prefix; the native stagger helps that reuse. Do not remove it or extend cache
lifetime merely because a longer value sounds better. Measure the intended
workload before changing defaults. [Prompt caching](https://code.claude.com/docs/en/prompt-caching),
[dynamic workflows](https://code.claude.com/docs/en/workflows).

## 6. Count every attempt and preserve failed conditions

Record task correctness, retrieved text, elapsed time, provider usage and billing
as separate quantities. For Codex, cached input is a subset of reported input;
for Claude, ordinary input, cache creation and cache reads are separate
categories. Reasoning can be a subset of output. Choose one authoritative
aggregate for an attempt and do not add cumulative snapshots or per-model totals
to it again. [Existing accounting conventions](evidence.md#token-measurements).

An efficiency comparison needs matched inputs and quality criteria, all parents
and children, retries, failed attempts, cache conditions and explicit exclusions.
Unknown usage stays unknown. A short failed answer is not accepted efficiency.
The [prepared-context comparison](../blueprints/us-equities/research-efficiency/README.md)
retains eight native answers, structural failures and provider categories. It
also excludes coordinator/preparation/reviewer usage, so it cannot establish
savings for the enclosing workflow.

Keep bounded retries for a diagnosed recoverable failure. Authentication,
entitlement and unchanged quota refusals need a changed condition, not an
automatic loop or paid fallback. Native `/usage` cost estimates and account
credit spend answer different questions; a print-mode dollar cap is not proof
that no usage credits can be spent. [Claude usage accounting](https://code.claude.com/docs/en/costs).

## 7. Separate deterministic checks from live qualification

Let deterministic code own arithmetic, schema validation, source hashes and
test assertions. Ask an agent to investigate and implement; independently
inspect its patch and rerun the checks relevant to the changed behavior. A
fixture should catch a real failure, not simply restate implementation details.

Use the repository's existing offline checks:

```sh
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
python3 scripts/build_ecosystem.py --check
python3 -m unittest
```

These are the commands in [the current CI workflow](../.github/workflows/validate.yml).
Validate the exact integrated commit, including negative tests that demonstrate
malformed or contradictory evidence is rejected. A hosted pass checks the
publication and its deterministic behavior. A native model run, GPU operation,
client activation or another host requires its own observed acceptance.

**Integration checkpoint, pending:** this wave plans a bounded native-worker
patch fixture and a deliberate CI failure/rejection case. The coordinator will
add the final paths and outcomes after execution and review. Until then, neither
is a passed result of this guide. Existing receipts remain the evidence baseline.

## 8. Close the task with a recoverable decision

Choose retain, trial, adopt within scope, defer or reject. State the accepted
host/component/task scope and the next observation that would change it. The
handoff includes the source revision, patch, actual checks, unresolved work,
attempt accounting and a rollback boundary. Save this compact decision; resume
the native task when its working context is needed.

Test recovery in layers. Reopening a task, stopping a local process tree,
resuming application work and restoring state on an independent host are
different checks. The [worker-supervision fixture](../blueprints/us-equities/worker-supervision/README.md)
observed local descendant termination and a fresh successful launch; it did not
prove remote provider cancellation or exactly-once effects. The
[state-recovery receipts](../blueprints/us-equities/state-recovery/README.md)
exercise selected application data while retaining an independent-host/key
recovery gap.

Preserve the accepted environment while a candidate is tested. After an
interruption, reconcile the native task identity and any external effects
before resubmitting. A successful same-host restore or a service that restarts
does not certify an entire Mac/WSL ecosystem after power loss or network change.

## Apply the loop to the next repository

For an application bug: select the existing engineering profile, record its
current setup/test commands, freeze a useful failing case, assign one native
worker the relevant files, verify the patch, and save the resulting decision.
Add retrieval, GPU execution or another framework only when that task exposes a
specific gap and the candidate passes the corresponding acceptance lane.

For a research question: freeze the corpus and question, retrieve a bounded
packet with negative cases, require source-grounded output, score correctness
and completeness, then compare usage within the same provider/task conditions.
Promote only the demonstrated change. That makes the ecosystem useful for
building complex systems while keeping evidence, ownership and recovery small
enough to inspect.
