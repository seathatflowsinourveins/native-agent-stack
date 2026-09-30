# Native token lifecycle evidence, 2026-09-30

[Decision and upstream sources](../../../docs/decisions/2026-09-30-token-lifecycle-resolution.md)
and [compact receipt](../../receipts/token-lifecycle-resolution-20260930.json)
define the acceptance scope. Native returned outputs and independent observations
remain distinct from our assertions and synthetic fixtures.

| Artifact | Result and boundary |
| --- | --- |
| `clean-prefix/receipt.json` | Original 259-command disposable installation; exit 1 at the stale Claude Serena reference. |
| `serena-existing/receipt.json` | Existing pinned executable independently reproduced the mismatch. |
| `serena-repair/` | Immutable source comparison, exact native preimages, red/green tests and two live schema-changing negative controls. |
| `clean-prefix-repaired/receipt.json` | Final fresh run: exit 0, 259 commands, 82 checks, owned temporary install removed. |
| `workflow-installer/` | 77 focused local integration tests, three preexisting PyYAML skips, source checksums and conflict/rollback/removal controls. |
| `claude-client-install.json` | Native reinstall/version and independent release-manifest byte comparison; existing signed-in host. |
| `claude-workflow*.json` | Live synthetic role-bound Workflow; both Sonnet/max and Opus/max children completed useful work. |
| `claude-role-marker.json` | Correct token-lane marker observed; absent-marker local guard fails without misreporting native helper exit status. |
| `claude-saved-partial.json` | Saved native discovery and two completed readers; verifier incomplete at transport cutoff. |
| `claude-saved-recovery.json` | Cached-prefix native resume; enclosing parent terminated after the 480-second deadline. |
| `claude-saved-complete.json` | Independently confirmed completed saved Workflow/verifier and cached reader reuse; source-coverage acceptance only. |
| `claude-saved-parent-limit.json` | Parent-only output review reached its four-turn limit; no Workflow rerun. |
| `claude-saved-parent-complete.json` | Final same-session parent reply exited 0 without tool calls or Workflow/child rerun. |
| `claude-agent-timeout.json` | Initial ordinary Agent timeout; no initial final handoff. |
| `claude-agent-recovery.json` | Resumed builder preload/discovery/tool-use observation; final handoff remains separately assessed. |
| `claude-agent-complete.json` | Same-child continuation, native handback/completed notice and clean parent exit; earlier failures retained. |
| `codex-clean-install.json` | Official disposable npm install, platform signature/provenance check and uninstall; active account/client retained. |
| `codex-native-incomplete.json` | Original stream and incorrect V1-close requirement retained. |
| `codex-native-observation.json` | Independent supported app-server/own-rollout evidence of the actual V2 Astra/max completed child. |

Prompt files are public synthetic inputs; private native paths use placeholders.
Raw conversations, authentication and personal active configuration are not
copied here. The supervised recovery's raw streams remain private. Repeated
cumulative usage snapshots are never summed, and interrupted usage is not
promoted to a final total. No equal-quality provider-token saving is claimed.

Reproduce the clean selected-tools fixture with:

```sh
rtk python3 scripts/native_token_ci.py --install --output <owned-evidence-directory>
```

That fixture invokes upstream installers and tools on synthetic inputs. It does
not install Claude/Codex, perform provider tasks, or accept every catalog layer.
For client setup, native saved-script recovery and scoped removal, follow the
linked decision and the selected adoption profile.
