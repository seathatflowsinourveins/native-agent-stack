# Isolation (`isolation`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## sandbox

**Status:** trial. **Default:** Hardened native Bash sandbox, delivered through `claude --settings` or managed settings

- **Route:** `enabled`, `allowUnsandboxedCommands: false`, `failIfUnavailable: true`, `autoAllowBashIfSandboxed: false`, `network.strictAllowlist` in user scope, credential deny entries; owner opt-in after M1's arms pass
- **Alternatives, ranked:** 1. anthropics/sandbox-runtime around the whole process; 2. Dev container or VM for bypass sessions (the docs' guidance; candidate, not adopted without measurement)
- **Rejected:** dagger/container-use; Prompt-contract isolation; Sandbox without filesystem isolation
- **Evidence:** sandboxing.md; sandbox-environments.md (bypass sessions belong in a container, VM or the sandbox runtime)
- **Notes:** The native sandbox bounds shell commands only; file tools, MCP servers, hooks and the status line stay outside it. Bypass is not reopened.
- **Supersedes:** M1 refined
- **Overturn when:** M1's arms pass on this host and the owner opts in, or a worker is seen taking a harmful action.

## worktrees

**Status:** default (scoped). **Default:** Coordinator-created worktree at the exact base (`git worktree add --no-track <path> -b <branch> <base>`), with the session started in it

- **Route:** The native isolation checks apply only to `--worktree` and EnterWorktree sessions; for a plain launch the main-checkout protection is the builder's prompt contract
- **Alternatives, ranked:** 1. A WorktreeCreate hook that creates each worktree at its exact base; 2. Pre-create at the exact base under `.claude/worktrees/<name>`, then `claude --worktree <name>`; 3. Native `--worktree` with `worktree.baseRef: head`; 4. max-sixty/worktrunk
- **Rejected:** `isolation: worktree` in builder frontmatter (rewrote core.hooksPath on 2026-09-25)
- **Evidence:** worktrees.md (checks apply to --worktree and EnterWorktree sessions); 2026-09-27 settings record (hooksPath incident)
- **Notes:** Adjudicated: the current practice stands (refuter pending at writing). Owed: the M49 probe on 2.1.295 for the WorktreeCreate and pre-create paths.
- **Supersedes:** M49 refined
- **Overturn when:** The M49 probe passes for a native path: concurrent builders from different exact bases, the four checks applied and core.hooksPath unchanged.
- **Primary sources** (read 2026-10-09; 1 of 1 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/) (2026-02-11; asserted; extends): Make the running application legible to the agent: one bootable app instance per git worktree, browser automation through Chrome DevTools Protocol skills, and a short-lived per-worktree logs, metrics and traces stack the agent queries with LogQL and PromQL, so it can reproduce bugs and validate fixes itself.
