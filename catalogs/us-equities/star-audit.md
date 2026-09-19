# Public-star decision audit

Checked **2026-09-19**. The refreshed native GitHub listing contains **337 public repositories**, unchanged from the earlier snapshot. No private repositories were returned. Every public star now has an explicit disposition in [star-audit.json](star-audit.json).

This closes the **unassessed-star decision gap**. It does not certify that every repository is secure, maintained, compatible, installed or useful, and it does not establish an exhaustive list of everything beyond the stars. Source review cannot prove strategy returns, broker behavior or token savings.

## What was actually reviewed

| Evidence depth | Repositories | Scope |
| --- | ---: | --- |
| Existing catalog cards | 41 | Link the earlier decision and its evidence; no redundant re-review. |
| Existing baseline components | 10 | Link the installed/reference component and scoped receipts. |
| New README/license overview | 268 | Inspect purpose, headings and license declaration; individually decide relevance. |
| New selected primary-file review | 18 | Also inspect the enumerated workflow, configuration, API or implementation sections. |
| Unassessed | 0 | No public star remains without a decision. |

The 286 new records have current default-branch commit pins and commit dates. These are **source snapshots**, not an assertion that a release, package or local installation has the same version. The 51 earlier records retain prior evidence; missing historical commit dates remain null. A license value is the observed declaration/classification, not a legal review of every file, binary, model or dependency.

These review-depth and decision counts preserve the original audit. A later [restic acceptance](../../blueprints/us-equities/hosting/backup/receipt.json) promotes that already reviewed starred identity into a scoped adopted catalog card. Current coverage therefore has 42 starred catalog repositories; the original selected-file review is not relabeled as a new source audit.

Native `gh api` pagination supplied the public/private flags. README and license requests used resolved commit hashes. One oversized README initially returned no body and was recovered with GitHub's raw-content media type. Excerpt selection bounded the reading; it did not score or decide repository quality. Full downloaded sources and account-bearing discovery responses are not published. The public JSON contains conclusions, exact source links, review extents and existing receipt references.

## Decisions

| Disposition | Count | Meaning |
| --- | ---: | --- |
| Already covered | 51 | Retain the linked decision and its actual evidence scope. |
| Alternative | 156 | Conditional substitute or extension; no default adoption. |
| Outside the north star | 53 | No current role in US-equity research, engineering or execution. |
| Overlaps established capability | 50 | Reference or function is already represented. |
| Targeted candidate | 14 | A specific, bounded future acceptance case is justified. |
| Obsolete or ineligible now | 13 | Deprecation, unresolved terms, incompatible scope or unnecessary risk prevents current adoption. |

The 14 targeted candidates are not 14 installation commitments. The six more tentative README-only leads—llmfit, Switchyard, Dependabot Core, open-multi-agent, dbt and Trail of Bits skills—remain alternatives until a concrete unmet requirement warrants deeper evaluation. Entire skill directories and linked resource lists were not recursively audited.

## Highest-value missing candidates

These choices are conditioned on the existing LEAN research-first and Alpaca-paper direction. Commands below are **unexecuted upstream examples**, to be used only after selecting the recorded source pin and satisfying prerequisites. No model, broker or install command ran in this audit.

### Scoped review scaffolding: Open Code Review

[Delegation mode](https://github.com/alibaba/open-code-review/blob/a003b9341a65130b024829101ea35494b56569e1/pages/src/content/docs/en/integrations/delegate.md) supplies file selection and grouped review rules while the existing native host performs inference. The inspected Go command implements `preview` and `rule`. This is distinct from ordinary `ocr review`, which configures an OCR-side model endpoint.

```sh
ocr delegate preview --from main --to HEAD
ocr delegate rule src/example.py
```

The acceptance case is a known patch with seeded defects: verify exclusions, rule coverage and reviewer findings using existing native quota. No savings claim follows from avoiding a second endpoint.

### Backtest checklist, not order authority

[The backtest skill](https://github.com/tradermonty/claude-trading-skills/blob/8f787ab23ceb346e4bfc936785f92fd162087d82/skills/backtest-expert/SKILL.md) emphasizes pessimistic costs, parameter robustness and rejection scenarios. Its daily workflow produces exposure posture rather than an order. Select one checklist for an existing LEAN report; check every criterion against actual artifacts. Do not install the whole skill pack or treat a narrative score as strategy approval.

### Vibe-Trading: inspect a real adapter, retain an unaccepted status

[Alpaca profiles](https://github.com/HKUDS/Vibe-Trading/blob/2dfbc03dd633bde4fdb3f6a550d2ff9a2b7b1021/agent/src/trading/connectors/alpaca/profiles.py) distinguish read-only, paper-trade and live-trade capabilities. [The SDK gate](https://github.com/HKUDS/Vibe-Trading/blob/2dfbc03dd633bde4fdb3f6a550d2ff9a2b7b1021/agent/src/live/sdk_order_gate.py) checks mandates, expiry and halt state; the selected reconciliation module documents ambiguity handling without automatic resend. This is substantive source, not proof every route enforces the gate.

Its current README also records a broker reply-shape defect that passed fixtures while actual orders were refused. Before any substitution, require paper-account contract tests, restart reconciliation, duplicate/partial-fill handling, a kill switch and independent review. The current accepted LEAN backtest is not replaced by this audit.

### whchien/ai-trader: bounded secondary backtest interface

[Four MCP tools](https://github.com/whchien/ai-trader/blob/7681fe331fb638beab1ae20d3552c802bbaa9174/ai_trader/mcp/server.py) expose backtesting, quick backtesting, data fetching and strategy listing. Source package metadata says 0.3.4, Python 3.11+, GPL-3.0. An upstream replay example is:

```sh
ai-trader run config/backtest/classic/sma_example.yaml
```

The inspected example uses a US-stock CSV but labels its commission as Taiwanese and allocates 95% of cash. Those defaults are unsuitable as evidence of realistic US execution. Compare a fixed local dataset against LEAN, checking calendars, corporate actions, fills and costs; do not infer an Alpaca adapter from MCP availability.

### Strict data boundaries and readonly research databases

[Pydantic strict mode](https://github.com/pydantic/pydantic/blob/915896d163835a57fd7987180087409a3229bd71/docs/concepts/strict_mode.md) is opt-in. `ConfigDict(strict=True, extra="forbid")` can reject many malformed proposals; documented JSON-type exceptions, business constraints, freshness, money precision and risk limits still require explicit handling.

[DBHub configuration](https://github.com/bytebase/dbhub/blob/e9e56aa3d9338187c16a4b883af081cea516c814/docs/config/toml.mdx) defaults `execute_sql` readonly to **false**. `readonly=true` and `max_rows` belong at tool level. A future research database connector should additionally use a database-level readonly principal and a scoped source; no unrestricted connection should be inferred from an MCP read-only hint.

### Recovery and reproducible environments

[Restic check](https://github.com/restic/restic/blob/ba802d42b7294c98b62c16d1157ea3e80820c019/doc/man/restic-check.1) distinguishes structural integrity from reading stored data. Native examples, with operator-owned destinations:

```sh
restic --repo "${BACKUP_REPOSITORY}" backup "${CONSISTENT_EXPORT}" --dry-run
restic --repo "${BACKUP_REPOSITORY}" check --read-data
restic --repo "${BACKUP_REPOSITORY}" restore latest --target "${RESTORE_DIRECTORY}"
```

A dry run is not a backup. Acceptance requires a real application-consistent export, separate storage, password recovery arrangements and a verified restore into a new directory. Never assume copying a live database file is a consistent snapshot.

Subsequent [native restic 0.19.1 acceptance](../../blueprints/us-equities/hosting/backup/README.md) backed up and restored 22 selected static public files (160,642 bytes) with a full-data check and independent hashes. This closes that narrow local-file case. Same-host storage/password placement, absent scheduling, off-host recovery and application-consistent live-database restores remain limitations.

[mise exec](https://github.com/jdx/mise/blob/3fed64c0713554b7f5bc60d4d208ac11ec385015/docs/cli/exec.md) could standardize project runtime selection. Its trust step and downloaded executables remain review boundaries; the documented `mise exec node@20 -- node ./app.js` syntax is an example, not an exact runtime lock.

### Task continuity without a second memory authority

[Beads](https://github.com/gastownhall/beads/blob/71c4cd08b9991e7ba4e53822769c78337e0f4ee4/docs/CLI_REFERENCE.md) offers dependency-aware task state (`bd ready`, `bd show <issue-id>`). Its README says initialization changes agent instructions/integrations by default. [LoopX](https://github.com/huangruiteng/loopx/blob/4077b87a54d37ca008533739079cedf5898a1fad/docs/quota-allocation.md) describes quota-controlled goals and re-planning. They can be evaluated for task scheduling only if the current coordinator and scheduler leave a real gap; neither should silently replace ai-memory or canonical execution policy.

[abtop snapshots](https://github.com/graykode/abtop/blob/4b96568666c1f3b887202d14b0a1c6171315e520/src/snapshot.rs) expose useful local runtime observability (`abtop --json`), but distinguish active-token rate from cache totals and can include prompt-derived titles. Do not publish raw snapshots or infer billed savings from their counters.

### Forecast and skill-optimization research

[Kronos prediction](https://github.com/shiyu-coder/Kronos/blob/67b630e67f6a18c9e9be918d9b4337c960db1e9a/examples/prediction_example.py) loads `NeoQuasar/Kronos-small` and its tokenizer. Its fine-tuning example defaults to Chinese CSI300/Qlib data, with overlapping ranges for lookback. Model-specific terms, training-data overlap and leakage-safe US-equity splits remain unverified. Compare against simple and cataloged forecasting baselines; a forecast is not a trade or profitable strategy.

[SkillOpt](https://github.com/microsoft/SkillOpt/blob/79124b37e9a6371e13b753f8bcd7adb1e493ade1/docs/guide/first-experiment.md) separates training from `valid_unseen` evaluation. Its inspected default configuration uses OpenAI chat backends; native-host options are not the default. Training/evaluation still consume inference. Any experiment must keep risk rules immutable, use held-out cases and a fixed budget; its WebUI also needs an explicit loopback host instead of the documented all-interface default.

## Near matches with important boundaries

| Repository / inspected source pin | Pin | Disposition and gap |
| --- | --- | --- |
| [atilaahmettaner/tradingview-mcp](https://github.com/atilaahmettaner/tradingview-mcp/blob/a1e54b07e5c21b375363607920f297c5adfbeed4/README.md) | `a1e54b07e5c2` | Targeted research connector: public-endpoint analysis without a TradingView session; package 0.9.0 supports Python 3.10–3.13. Data rights, freshness and point-in-time history remain unverified; no order execution. |
| [tradesdontlie/tradingview-mcp](https://github.com/tradesdontlie/tradingview-mcp/blob/c05b8f5755ed8e64ea242de88ddbf46aa24d56a4/README.md) | `c05b8f5755ed` | Alternative: CDP control of the user’s TradingView Desktop app. Requires the desktop/subscription and explicitly warns about automated data restrictions; not the same server as the previous row. |
| [asavinov/intelligent-trading-bot](https://github.com/asavinov/intelligent-trading-bot/blob/0f8748d21906d37b7d33de9278f4742b8f419456/README.md) | `0f8748d21906` | Alternative: inspected configuration targets Binance and simulation; no verified native Alpaca path. Server startup may activate configured outputs. |
| [HKUDS/AI-Trader](https://github.com/HKUDS/AI-Trader/blob/d03ff6c056b32ced735adf7c19ed8175adb1c8df/README.md) | `d03ff6c056b3` | Ineligible for current adoption: hosted registration path, no returned root license, and service README calls implementation proprietary despite an MIT badge elsewhere. |
| [akfamily/akshare](https://github.com/akfamily/akshare/blob/2e13a5f2fb003d299b5c299289c318b7979986e8/README.md) | `2e13a5f2fb00` | Alternative: US-stock module uses Sina endpoints. An available Python function is not an exchange entitlement, stable historical archive or validated adjusted-price contract. |

## Licensing and maintenance change the answer

The current source declarations matter more than an old star description. Examples found in this pass:

- [screenpipe/screenpipe](https://github.com/screenpipe/screenpipe/blob/02d94c48a6445f7c176b33d117cc483ac68aea13/LICENSE.md): commercial license with bounded evaluation and noncommercial terms.
- [jgravelle/jcodemunch-mcp](https://github.com/jgravelle/jcodemunch-mcp/blob/9853afb12c5e12ad1cb591f38b6021314d0ddccb/LICENSE): Dual-Use License 1.1, effective 2026-06-30.
- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman/blob/542442bab314973709f95b85b1ac0b3f6f5b5dc6/LICENSE): MIT outside listed engine directories; BSL-1.1 for engine-linked scope.
- [ykdojo/claude-code-tips](https://github.com/ykdojo/claude-code-tips/blob/7fbe9a74b32b9d0550e39e82fb9958185d7e7773/LICENSE): All Rights Reserved.
- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus/blob/a578747455f377f2073178c38c35189990cd7026/LICENSE): PolyForm Noncommercial 1.0.0.
- [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills/blob/3c546bc08c56f79e0068f1ea4f0acedf5bf69b5e/LICENSE): CC-BY-NC-4.0.
- [multica-ai/multica](https://github.com/multica-ai/multica/blob/8c4f4328f6e3baff08394b309034463b5db9d7af/LICENSE): Apache-based license with additional conditions.
- [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/24efd6e7cbd7a074e6b3b781eb370891df40afad/LICENSE): Apache transition retaining some MIT contributions and CC-BY documentation.

[humanlayer/humanlayer](https://github.com/humanlayer/humanlayer/blob/99abe673498cf8bdcd5f989aebe9406a27185b3b/README.md) now describes the old code as deprecated. [openai/skills](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/README.md) redirects new examples to openai/plugins. Existing pinned evidence remains historical; a current discovery route can change without retroactively changing what ran.

## Closure and remaining acceptance boundaries

All public stars have a useful decision with traceable evidence depth. No private discovery data or complete third-party README has been copied into this publication. Earlier core/runtime receipts remain scoped to their own tasks; this research does not upgrade alternatives to installed components.

Production trading still requires licensed and correctly timestamped data; leakage-aware research; realistic slippage, fees and borrow assumptions; account-authorized paper acceptance; deterministic order/risk checks; idempotency and reconciliation; monitoring and restore drills. The broader gap-resolution work may close individual items through separate receipts. Neither star coverage nor passing catalog validation proves those outcomes.
