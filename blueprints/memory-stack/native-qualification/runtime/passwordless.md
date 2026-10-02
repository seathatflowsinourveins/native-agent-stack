# Passwordless native integration boundary — 2026-10-02

Codex 0.160.0 reports a ChatGPT login and Claude 2.1.287 reports a native
claude.ai/firstParty login. Both status commands exited zero. Native credential
stores remain native. The operator does not need to supply a key for that
authentication; the earlier missing gateway-key observation is not evidence
that either native client needs a new login.

The installed OmniRoute 3.8.52 instance is a patched host variant, not an
unmodified release claim. Its dashboard advertises a CLI broker, but the
installed `config/cli-tools-manifest.json` defines Claude and Codex as
`stdio-adapter`, not native ACP:

- Claude: `claude --print --output-format json`.
- Codex: `codex --quiet`; that flag is absent from observed Codex 0.160.0 help.
- `src/lib/acp/manager.ts` writes prompt text to stdin and waits for output/exit
  without closing stdin. This creates an unresolved EOF contract for Claude.
- `src/lib/acp/launchConfig.ts` supports process-specific `cwd` and `env`, so a
  per-request PATH can address discovery without restarting the shared service.
  PATH alone does not repair the protocol mismatch.

No broker model call was made through these unqualified definitions. No
production gateway setting, launch agent, native account or hook was changed.
An authenticated dashboard session is not a successful provider execution or a
blind review result. The original `/v1/models` HTTP 401 remains recorded.

## Supported upstream direction

The official [Claude ACP adapter 0.23.1 source](https://github.com/zed-industries/claude-agent-acp/tree/5268661b7fed327e33d744ce49615fcd804fea20)
exposes the native `claude-login` terminal method and supports
`CLAUDE_CODE_EXECUTABLE` in `src/acp-agent.ts`. Its default setting sources are
user, project and local; using an adapter therefore does not establish hook or
MCP isolation. [Zed's authentication documentation](https://zed.dev/docs/ai/external-agents#claude-agent)
explicitly leaves authentication and billing with the external agent and
documents Claude Code authentication where supported.

The official release API returned the following artifact, redirecting the
repository to its current `agentclientprotocol` organization:

- [Darwin ARM64 ZIP](https://github.com/agentclientprotocol/claude-agent-acp/releases/download/v0.23.1/claude-agent-acp-darwin-arm64.zip)
- Size: 26,417,238 bytes.
- Reported SHA256: `d61e6123a833675728e4551ed9d54921da4ce3c8e68ac884b6e0be94c03dcc6e`.

This artifact was discovered, not installed or runtime-qualified in this task.
Do not treat release metadata as a locally verified download digest.

The shared gateway owner should first reproduce a bounded native ACP handshake
and one synthetic model response using a pinned official adapter and the existing
native executable. Keep native HOME and login unchanged; attest the resolved
model, effort, loaded settings/hooks, subprocess ownership and cleanup. Verify
the gateway's ACP protocol support and model selection before registering the
adapter. Use an owned isolated instance only after its supported data-directory,
port and authentication boundaries are verified; that isolation contract was
not established here.

Only after those checks should the coordinator run the predeclared blind
cross-family lane. No token copying, homemade CLI wrapper, authentication bypass
or additional user-managed key is part of this proposal. Failure of this host
integration is not evidence against Hindsight retrieval quality.
