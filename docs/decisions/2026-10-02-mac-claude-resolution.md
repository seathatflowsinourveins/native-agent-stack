# Mac native Claude deployment resolution

Decision date: 2026-10-02. Canonical deployment source:
`18eea2c1de992b46c266d79ef0cc40f93c9fb943`.
Scope: the existing Mac Claude deployment and one bounded native integration
check. No component selection, service placement or workstation acceptance
changes follow from this record.

## Deployment repairs and checks

The Mac owner replaced the stale installed
[effort guard](../../adoption/hooks/claude/effort-default-guard.py) through its
existing installer and deployed the byte-identical
[canonical Mac launcher](../../adoption/bootstrap-macos.sh). A scoped interactive
shell alias now routes ordinary `claude` invocations through that launcher.
Its default terminal case adds `--effort max`; explicit effort, headless inputs
and environment overrides retain the upstream launcher's controls.

The obsolete guard reproduced two regression errors before replacement;
the original failures remain retained. After repair, all 14 selected source
tests passed (nine guard tests and five launcher tests), exit 0. The launcher
source tests include nine
deliberately broken controls. The deployed launcher passed all 27 existing
argument/PTY cases; shell syntax and fresh interactive resolution/version
checks passed. These counts describe distinct checks and are not added to a
whole-stack total.

A separate bounded Sol review found no material issues; all nine reviewed
input hashes matched. It confirmed canonical guard/launcher bytes, only the
scoped shell alias added, the saved settings and native binary unchanged, the
full 332-byte retrieval seal, and the historical S12 result preserved. This
source/evidence review does not establish blind cross-family convergence.

| Verified deployment artifact | SHA256 |
| --- | --- |
| Canonical effort guard | `2a5f087f2c10437bab302e19469ae6b2e715828083a8bae07a7b177540b63e0e` |
| Canonical Mac launcher | `f48eb13407391d73becb0848a7114d5662dc55dba4335b64bd0378b6210a2cd5` |

The official auto-updating Claude binary remained intact, observed at 2.1.287.
Saved Opus/xhigh preferences and Ultracode remained as observed. The owner observed
filtered native auth-status: first-party login with Max subscription; the native
stream independently confirms the `firstParty` provider, not the subscription
plan. No authentication store, service, global MCP configuration or SDK/provider
route changed.

## Separate native integration result

One Claude Opus 5.5 session, explicitly `--effort max`, used official installed
SocratiCode 1.16.0 with task-only strict MCP configuration and an owned unchanged
332-byte fixture. The identical preregistered query returned `Not Found` before
indexing. One full index explicitly completed in 2.0 seconds; the query then
retrieved exactly `pipeline.py` lines 1–10. The owner independently compared the
full source text and function oracle. The session completed successfully in
178.728 seconds, exit 0, within its 300-second deadline.

The native return contains two search calls, one index call and two status
calls, plus one denied extra `codebase_watch(action=status)` call. No denial was
bypassed. The allowed status operation independently confirmed the task watcher
disabled. The task-cwd process scan found no remaining native/node process
after exit; escaped descendants were not independently attested. The task index
is retained with watchers off.

| Retained local evidence identity | SHA256 |
| --- | --- |
| Native event log | `5f9515514cba5ed64f6f60777b63f72a6d6d2dc44016062f9293ab60262b8198` |
| Unchanged source fixture | `49c4104563a1b55c8d08235905afa0537ef4f2eecd213deb87cb2438a3b0cd8a` |

The complete native stream, session history, configuration and authentication
stores stay local. These hashes identify evidence; they do not make the private
stream independently reproducible from this source record.

## Acceptance boundaries

The historical read-only Claude suite remains **11 pass / 1 partial / 0 fail**
with all 22 prescribed inputs matched. Its S12 contract prohibited indexing and
search. This new check is separate local integration evidence using unchanged
upstream operations; it does not rewrite S12 or complete the upstream Docker
E2E suite, representative native lifecycle, full-stack or workstation acceptance.

The closed Mac memory qualification stays closed: retain official ai-memory
2.5.2 and Ollama 0.34.4; no candidate experiment, holdout or canary is queued.
SDK acceptance does not qualify CLI/ACP gateway adapters. Claude-native
authentication remains separate from the Codex/OpenAI SDK route. Whole-task
usage and net savings remain unknown.

This record complements the
[two-host North Star architecture](2026-10-02-two-host-north-star-architecture.md).
Mac deployment rollback artifacts remain with the designated Mac owner; source
rollback is a documentation revert and does not itself roll back deployment.
