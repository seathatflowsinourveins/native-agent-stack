# Runtime roster qualification, 2026-09-30

These are bounded native observations for three source-pinned candidates. They
do not promote a default SDK or certify an entire research/review workflow.
Native installation, selected unchanged upstream tests, local integration
fixtures and provider execution remain distinct.

| Candidate and source | Returned native evidence | Remaining gate |
| --- | --- | --- |
| [GPT Researcher v3.7.0](https://github.com/assafelovic/gpt-researcher/tree/0957c301ed06c2a5857b834358c7227c739041d4) | 24 selected unchanged upstream tests passed; runtime/proxy/grader compatibility checks passed for 198/68/8 distributions | No model report, grounded-citation score or complete provider usage |
| [DeerFlow v2.1.0](https://github.com/bytedance/deer-flow/tree/345f08be00c8a9495079b732a39b46aa9af1584e) | Native backend install and CLI; 309 selected unchanged backend tests; 8 unchanged GAIA scorer tests | Backend `uv pip check` exits 1 for upstream's explicit websockets override; no service/model acceptance |
| [Crawl4AI v0.9.4](https://github.com/unclecode/crawl4ai/tree/133e1d92e37885dfccc03ea2e3687d06c98b7ceb) | One completed native model-free REST job; 16 unchanged extraction tests passed, 1 skipped, 4 network cases deselected; 99 distributions compatible with the explicit four-package test overlay | No integrated Responses caller/quality comparison; legacy Chat Completions extraction unqualified for the target route |

The exact command outputs and artifact/source hashes are in
[gpt-researcher-native.json](gpt-researcher-native.json),
[deerflow-native.json](deerflow-native.json) and
[crawl4ai-native.json](crawl4ai-native.json). DeerFlow's
[detailed evidence note](README-deerflow.md) explains its retained failures and
native upstream override. Original logs, browser HTML and host state stay
outside the checkout. Public outputs replace private paths with placeholders;
native job/thread IDs and credential values are excluded.

Crawl4AI now defaults to native model-free crawling. Its old LLM extraction path
is an explicitly selected historical comparison, rather than the reviewed
Responses path. The actual crawl's old receipt included unused model/route
metadata despite `llm_used: false`; that original receipt is retained by hash.
Current source removes the unused claim. Only the owned crawl container and
network were stopped and removed; independent native listings confirm absence.

The three recipes retain bounded dispatch, host-owned state, scoped MCP tools,
native installers and recovery/cleanup examples. Generic `check`/`receipt`
module names in their local test loaders initially collided across recipe
families; the loaders now isolate imports. The stale SocraticCode path was
corrected to the canonical Linux 1.15.0 pin; 1.16.0 remains a separate candidate.
These are integration corrections, not new upstream features.

No token saving is claimed. The crawl does not use an LLM; enclosing task,
research, retry and judge usage remains unknown where no authoritative native
counter is available. Historical engines-on aliases and embedding services
need fresh native discovery before a trial. Frozen quality tasks, negative
controls and complete attempt/judge accounting must pass before broader
adoption. Source installation or grader import alone does not pass that gate.
