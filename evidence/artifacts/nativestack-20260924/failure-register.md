# NativeStack nonzero receipt register (Windows-only audit, 2026-09-24)

Source: regenerated `work/public-ledger.json` (271 commands, 36 nonzero exits), matched to private `work/receipts/<id>/receipt.json` and existing agent handoffs. IDs, exit codes and successor IDs below are safe metadata; raw streams and argument payloads remain private. A later passing check never changes a failed receipt's actual exit. `4294967295` is the ledger's unsigned representation of a native `-1`/WSL launch failure, not a successful command.

## Still open or limited

| Receipt | Exit | Status |
| --- | ---: | --- |
| `agent-research-sdk-tests` | 1 | **Open upstream/test-environment conflict:** 3,501 tests, 1 failure, 203 skips. Selected lock includes `exchange-calendars`; the failing test assumes it absent. SDK install and `uv pip check` passed separately. No full-suite pass. |
| `agent-gap-gitleaks-dir` | 1 | **Open findings:** 218 redacted, untriaged matches in bounded catalog directory scan; full-history scan was interrupted and not clean. New contribution files need their own targeted scan. |

## Expected negative checks

| Receipt | Exit | Why nonzero is expected |
| --- | ---: | --- |
| `agent-gap-difft-compare` | 1 | `difft --exit-code` on deliberately different frozen fixtures; structural difference observed. |
| `agent-gap-zizmor-unsafe2` | 14 | Deliberately unsafe `.yml` fixture produced expected `artipacked`, `template-injection` and `unpinned-uses` findings. The regular 17-workflow scan was exit 0 (`agent-gap-zizmor-workflows`). |

## Corrected attempts or later narrower success

| Failed receipt | Exit | Subsequent evidence and retained limit |
| --- | ---: | --- |
| `agent-gap-difftastic-install` | 1 | `agent-gap-difftastic-install3:0`; helper cap was too small for verified archive. |
| `agent-gap-difftastic-install2` | 1 | `agent-gap-difftastic-install3:0`; existing download required hash-preserving reuse. |
| `agent-gap-gitleaks-install` | 1 | `agent-gap-gitleaks-install3:0`; direct WSL PATH lacked `gh`. This does not resolve scan findings above. |
| `agent-gap-gitleaks-install2` | 1 | `agent-gap-gitleaks-install3:0`; precreated download directory. |
| `agent-gap-inspector-dryrun` | 254 | `agent-gap-inspector-dryrun2:0`, then install and 23-tool handshake passed; initial npm prefix `lib` absent. |
| `agent-gap-sandbox-dryrun` | 254 | `agent-gap-sandbox-dryrun2:0`, then install/file-policy fixture passed; initial npm prefix `lib` absent. |
| `agent-gap-sandbox-list` | 4294967295 | Transient WSL launch failure during an npm list attempt; later `agent-gap-sandbox-version2:0` and `agent-gap-srt-accept:0` qualify installed CLI/file policy, not that failed list invocation. |
| `agent-gap-sandbox-version` | 4294967295 | Transient WSL launch failure; `agent-gap-sandbox-version2:0` later returned CLI fallback version 1.0.0 while package metadata is 0.0.77. |
| `agent-gap-zizmor-unsafe` | 1 | Fixture had `.yml.txt`, not a workflow extension; corrected fixture `agent-gap-zizmor-unsafe2:14` yielded expected findings. |
| `agent-poppler-qualify` | 127 | Direct WSL PATH omitted managed Python; `agent-poppler-qualify2:0` passed frozen ingestion with explicit native PATH. |
| `agent-recovery-restic-signature` | 1 | Shell variable expansion produced wrong GPG directory; `agent-recovery-restic-verify-corrected:0` validated signature and archive hash. |
| `agent-research-dagu-run` | 1 | Published 180-second timeout; owned DAG copy raised timeout to 900 seconds, `agent-research-dagu-run2:0`. Original DAG was not silently claimed passing. |
| `agent-research-eval-venv` | 2 | Guessed interpreter path was wrong; `agent-research-eval-venv-corrected:0`, then offline study and tests passed. |
| `agent-research-nautilus-verify` | 1 | Earlier Bubblewrap mount exposed `/home`; corrected fresh runs and `agent-research-nautilus-verify-corrected:0` met isolation. |
| `claude-plugins-https` | 1 | HTTPS plugin route failed; `claude-plugins-local-pin:0` applied a reviewed local pinned path. Do not claim HTTPS route passed. |
| `claude-socraticode-native-session` | 4294967295 | Native WSL launch failure; `claude-socraticode-native-retry:0` is a separate successful invocation. |
| `client-native-config` | 1 | Initial config attempt failed; later `client-config-reviewed:0`, `claude-config-apply:0` and native client checks are separate evidence. |
| `code-tools-plan` | 2 | Initial plan failed; `code-tools-plan-v2:0` and `code-native-install:0` followed. |
| `codex-plugin-hook-manifest` | 1 | First manifest command failed; `codex-plugin-hook-source:0`, `codex-hook-review-complete:0` and hook proof are later checks. |
| `current-hf-model-discovery` | 2 | Initial discovery failed; `current-hf-model-discovery-corrected:0` supplied reviewed current model candidate. |
| `finish-mcp-config` | 1 | Config finishing attempt failed; later `code-mcp-acceptance:0`, `context-mcp-acceptance:0` and `rag-mcp-acceptance:0` qualify their specific endpoints, not a rerun of this exact command. |
| `memory-functional` | 1 | Initial memory test failed; `memory-functional-own-port:0` qualified the separately scoped port. |
| `model-runtime-release-pointer` | 127 | Release-pointer command failed; `model-runtime-candidates:0` and subsequent model/runtime install and generation acceptance are separate evidence. |
| `npm-tools-plan-v2` | 254 | npm plan failed; `npm-tools-plan-v3:0` followed. |
| `render-check` | 1 | Initial render check failed; `backend-config-render:0` later generated config. Its success is narrower than a pass of this failed check. |
| `render-output` | 1 | Initial output render failed; later `backend-config-render:0` and service acceptance are separate evidence. Do not relabel original rendering pass. |
| `serena-pin-preview` | 254 | Preview failed; `semantic-plan:0`, `semantic-install:0` and subsequent code MCP acceptance are later evidence. |

| `evidence-generator-check-before-refresh` | 1 | Expected stale generated reports after adding receipts; `evidence-generators-and-validation:0` regenerated both and passed validation. |
| `target-restart-functional-health` | 1 | Probe used unsupported ai-memory /health and timed out; `target-restart-health-corrected:0` used the native CLI and verified persisted state. |

| `contribution-scan-plan` | 1 | Publication helper initially omitted hardware-profiles.json from its owned-path allowlist. The exact six generated/registry paths and three owned evidence prefixes were reviewed; `contribution-scan-plan-corrected:0` accepted the 83-file scope. |

| `contribution-secret-scan` | 1 | Two Sourcegraph-rule matches were exact public catalog/Syft Git commit IDs, confirmed using redacted finding positions and existing source identities. Rendered them as explicit upstream commit links; no scanner rule or broad suppression was added. `contribution-secret-scan-source-links:0` rescanned all 83 contribution files and returned zero findings without rule suppression. |

## Revised public ledger payload check

`contribution-secret-scan-corrected` also exited 1 with the same two public commit-ID matches because the first triage helper stopped on a scanner column-offset mismatch before changing the document. The corrected helper (`publication-commit-id-triage:0`) checked the overlapping known source identities and applied explicit upstream links. Both scanner failures remain in the ledger.

The ledger withholds known model prompts and memory-page payloads, and all long or multiline arguments. Exact original argv hashes and raw-stream digests are retained. Public-content validation and a targeted scan cover the publication snapshot; these do not establish the absence of every possible private value or resolve the older catalog findings. The exact command data and raw streams remain private.
