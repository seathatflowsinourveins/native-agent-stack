# Retain failed Claude federation diagnostics before acceptance — 2026-10-10

**Superseded for CI review (2026-10-10).** The owner then ruled that CI Claude review authenticates with an API key, `ANTHROPIC_API_KEY` of the main-only `claude-review` environment, and federation stays unconfigured (`docs/decisions/2026-10-08-claude-actions-pr-review.md`, "Authentication by API key"). This record stays as the diagnosis behind that move; its vendor snapshots stay retained and tested.

The three federated workflows already select Claude Opus 5.5 through
`anthropics/claude-code-action` v1.0.247 at
`2dca132ff0e0c4094ce6048b422c6915a071210b`. This P1 slice keeps that supported
authentication and review mechanism and makes its zero-cost failure diagnosable.
It starts from main at `f6ae0de74c151dce9204f6b6bdae7ea048932881`.
Its scope is diagnostics and documentation. The audit plan's O7/O8 Console
correction and native acceptance dispatch remain owner work; the source change
does not claim that those operational acceptance steps passed. The broad review
schedule stays off and harness audit stays disabled until that acceptance.

## Problem and change

An error result with `is_error: true`, `total_cost_usd: 0` and `modelUsage: {}`
failed the existing nonempty-model guard before accounting wrote a record or
summary. Synthetic execution of the actual shell independently reproduced this
in `claude-pr-review.yml`, `claude-pr-toolkit-review.yml` and `harness-audit.yml`:
all three exited at jq's `usage unavailable` error, rc 5.

Accounting now retains the fixed class `zero_cost_error_without_model_usage`,
includes it in the job summary and failed-bound message, and exits 1. The class
describes exactly those three result fields; it does not establish a federation
denial, its reason, or a successful model call. Raw provider error strings and
transcript text are excluded. Normal usable results carry a null `error_class`.
Toolkit accounting checks every result, so a later success cannot hide an earlier
zero-cost error. Its incomplete record keeps null total cost and message count,
with any usable assistant token counts still explicitly a lower bound.

The original read-only tools, budgets, turn and cache checks, publication
conditions, Opus selector and action pins retain their existing contract.
P3's resolver, scheduling and cache changes belong to a separate slice.

## Native state and remaining acceptance

Native GitHub reads on 2026-10-10 confirmed repository ID `1376766892`, owner ID
`234074349`, and OIDC customization `use_default: true`,
`use_immutable_subject: true`. The main subject is therefore:

```
repo:seathatflowsinourveins@234074349/native-agent-stack@1376766892:ref:refs/heads/main
```

The following native run metadata was rechecked without reading credentials,
repository variable values, identity tokens or an execution transcript:

| Run | Event and source | Native conclusion |
| --- | --- | --- |
| [37739403956](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37739403956) | dispatch on main `7a3637f5df7111fda87f2f1408e23963d18caadc`, 2026-10-08T06:45:40Z | completed, failure |
| [37988961127](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37988961127) | schedule on main `f1fae6faf1c74fcadde68f8495ddcd26a51ef942`, 2026-10-09T20:44:12Z | completed, failure |

`harness-audit.yml` is natively `disabled_manually`. Its bounded-workflow PR
[#892](https://github.com/seathatflowsinourveins/native-agent-stack/pull/892)
already squash-merged as main commit `b0b4b10972def3741f90daa350a275a078aa3c8e`
at 2026-10-10T00:46:20Z. This diagnostic patch does not re-enable it.

The CC's native federation acceptance follows the vendor path:

1. Read the failed exchange's native Console authentication-history reason.
   An opaque authentication failure or this fixed accounting class cannot supply
   that reason. For `match_subject_prefix`, bind the exact immutable main subject,
   audience `https://api.anthropic.com`, and main/owner/repository claim values.
   A workspace-membership denial instead needs the documented workspace correction.
2. Dispatch the merged main workflow against an eligible current PR head.
   Require native review success, positive client cost, nonempty actual model
   usage naming Opus 5.5, and accepted authentication history. Keep the broad
   review schedule off until this succeeds.
3. Re-enable the separately bounded harness audit only after that acceptance.
   Its native run must meet its existing client cost bound of $5.50.

There is no new native model or federation run in this slice. The local review
worker [#953](https://github.com/seathatflowsinourveins/native-agent-stack/pull/953)
was still open at the native read; adoption and testing use its landed main
implementation after it merges. This change does not depend on a PR-branch pin.

## SOTA sources

- [anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b:base-action/src/run-claude-sdk.ts:141](https://github.com/anthropics/claude-code-action/blob/2dca132ff0e0c4094ce6048b422c6915a071210b/base-action/src/run-claude-sdk.ts#L141): the result's sanitized field list includes `is_error`, `total_cost_usd` and `modelUsage`; [line 222](https://github.com/anthropics/claude-code-action/blob/2dca132ff0e0c4094ce6048b422c6915a071210b/base-action/src/run-claude-sdk.ts#L222) writes the execution records.
- [The same action:base-action/src/workload-identity.ts:51](https://github.com/anthropics/claude-code-action/blob/2dca132ff0e0c4094ce6048b422c6915a071210b/base-action/src/workload-identity.ts#L51) requests the GitHub identity token through the supported Actions client; [examples/claude-wif.yml:31](https://github.com/anthropics/claude-code-action/blob/2dca132ff0e0c4094ce6048b422c6915a071210b/examples/claude-wif.yml#L31) names the required federation permission.
- GitHub OIDC reference, [retained snapshot:352](../../evidence/artifacts/claude-federation-docs-20261010/docs.github.com_actions_reference_security_oidc.txt#L352), revision `sha256:35d79cb17e94732a467c63e59c3a01d18029b47f4b5f9cbf15d92037164b03cd`, retrieved `2026-10-10`, 37248 bytes; [vendor URL](https://docs.github.com/en/actions/reference/security/oidc). Lines 352–359 support the immutable owner/repository syntax. Primary REST reads confirmed this repository's customization; no JWT was read. The pull_request suffix is separately documented at 332–336.
- Anthropic WIF GitHub guide, [retained snapshot:316](../../evidence/artifacts/claude-federation-docs-20261010/platform.claude.com_wif-providers_github-actions.md#L316), revision `sha256:edc97bf1872a1292911b08600aadfc494295009cc6db1da232279dae46c0429b`, retrieved `2026-10-10`, 14693 bytes; [vendor URL](https://platform.claude.com/docs/en/manage-claude/wif-providers/github-actions). The exchange failure is opaque; native history supplies the actual deny reason, with `match_subject_prefix` a common cause.
- Anthropic WIF concepts, [retained snapshot:42](../../evidence/artifacts/claude-federation-docs-20261010/platform.claude.com_workload-identity-federation.md#L42), revision `sha256:d929e36810bcfdcc7a9bf5de39df8b08fbfde60a6d4c138b097f0940feb13bb7`, retrieved `2026-10-10`, 25749 bytes; [vendor URL](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation). All configured subject, audience and exact claim matchers must pass. The source change preserves the vendor mechanism.

[Snapshot index](../../evidence/artifacts/claude-federation-docs-20261010/snapshots.json)
records source URLs, revision hashes, sizes and claim locators. All retained files
are registered in `manifests/evidence.json`. The source packet was staged at
2026-10-10T07:03:18Z; its date-level retrieval record is preserved without
inventing individual request timestamps or vendor publication versions.
The two Claude pages contain public organization-ID examples. The generic
publication UUID heuristic initially refused those exact vendor bytes. A
content-bound exception applies only to their reviewed paths and hashes and
only to that UUID classification; every credential/private-path check still
runs. Modified bytes, another path or missing registration are refused by the
new validator regressions. This keeps the referenced snapshots readable and
byte-identical without widening privacy exemptions for other content.

## Validation boundary

`tests/test_claude_federation_diagnostics.py` executes the actual accounting shell
through the existing isolated workflow harnesses, with synthetic result records.
It checks retained diagnosis, continued rejection, no raw message publication,
each of the three required fields, normal cached success, and toolkit error-before-
success ordering. The initial red run reproduced four failed controls and the
absence of the new field in three positive schema controls. No fixture stands in
for native federation acceptance. The three existing complete workflow test
modules remain part of the local validation, including their budget-stop and
incomplete-accounting controls.
The failed-exchange test also executes the retained hosted S2 shape: native
run 37988961127 reports `subtype: success`, `is_error: true` and `num_turns: 1`,
with zero cost and empty model usage. This is a synthetic subtest of the native
observed shape, grounded in pinned `run-claude-sdk.ts:252–256`, not a replay of
the provider exchange. A source regression checks that the cited three revision
hashes, byte counts, claim-line content and evidence registrations match the
actual retained bytes.

The privacy arms use separate publication fixtures because CPython
[v3.13.16:Lib/unittest/case.py:647](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py#L647)
calls `setUp` once before the test method at:651, while
[subTest at:538](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py#L538)
is a context manager within that same test case. It does not reset fixture files.
Each arm uses the supported `TemporaryDirectory`/`copytree` lifecycle so a prior
arm cannot supply the next arm's expected UUID error.

Returning only jq's original usage error would keep the diagnosis gap. Printing
provider errors would publish arbitrary strings without establishing the cause.
Treating missing model usage as successful accounting would incorrectly accept
an unmeasured review. The fixed class with continued rejection is the smallest
change that distinguishes this known shape while preserving those boundaries.
