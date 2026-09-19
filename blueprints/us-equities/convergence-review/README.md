# Native architecture review and adjudication

On September 19, a fresh native **Claude Opus 5** process reviewed a bounded
nine-fact packet about the current ecosystem. It returned a structured critique
in **25.019 seconds**, with zero exposed tools and 16 native hook events.
The [receipt](receipt.json), [input](prompt.txt) and [unaltered model report](model-report.json)
separate successful execution from the correctness of model reasoning.

```bash
claude -p --model claude-opus-5 --output-format stream-json --verbose \
  --include-hook-events --max-turns 2 --tools '' --disallowedTools '*' \
  --permission-mode dontAsk --permission-prompts none < prompt.txt
```

The actual invocation used the existing native process supervisor, a 240-second
deadline and filtered environment in the adopted workspace. It kept native
account discovery and hooks. This is not an operating-system sandbox or a
separate paid API route. The published prompt has a trailing newline; the receipt
retains the exact original stdin size/hash.
The native response wrapped its JSON in a Markdown fence; the existing parser
removed that wrapper. The published report is the exact parsed JSON result.
The prompt is a text artifact so the Markdown documentation index does not
promote its duplicated input packet as another independently sourced guide.

## Direct usage and observation

| Native category | Tokens |
| --- | ---: |
| Input | 2 |
| Cache creation | 13,962 |
| Cache read | 531 |
| Output | 4,875 |
| Total | **19,370** |
| Thinking, already included in output | 2,225 |

All four additive categories matched the native response, Prometheus and one
Loki API-request event for the same private process instance and time window.
Loki retained **51 records**, with content bodies omitted. Native output contained
eight hook-response events. **7/7 Prometheus targets were up.** The response,
metrics and logs describe the same usage; do not add them together. These are
tokens consumed, not savings or complete multi-agent task usage.

Native observation uses:

```promql
last_over_time(ecosystem_claude_code_token_usage_tokens_total{client_scope="financial-research"}[30m])
```

Filter the returned `instance` to the exact process. Loki uses
`{service_name="claude-code"} | service_instance_id="$NATIVE_INSTANCE_ID"` with
the matching start/end window. Public receipts omit private process identifiers.

## Coordinator adjudication

The model's report is untrusted analysis of the supplied packet, not independent
source verification. Its useful priorities are a user-specific research/risk/data
specification, restored native Codex access, measured retrieval quality, and
recovery through the consumer plus an independent backup/key destination.
The following report assertions are rejected or narrowed:

1. **Scorer direction is reversed.** Upstream QMD suffix matching reports
   recall@1 **6/12**; the separate strict full-path audit reports **5/12**. The
   local audit does not inflate upstream results. Both are retained unchanged.
2. **No gold-source exclusion was shown.** All intended documents belong to the
   18 eligible foundation sources. The wider 33-document FTS corpus affects BM25
   statistics; it is not evidence that filtering discarded a gold document.
   The two empty searches are observed lexical misses. The baseline is neither
   a measured production quality score nor a guaranteed lower bound for it.
3. **Qdrant recovery went beyond archive bytes.** A new native server loaded the
   Restic-recovered snapshot; live API state and a real exact-vector query were
   independently compared. Missing MCP rebinding/off-host proof limits that
   result, but does not erase the demonstrated application restore. Memory
   recovery separately exercised native restore and SQLite/FTS state.
4. **The discovery counts do not imply three empty sweeps.** The public-star
   refresh found zero new identities; other searches found new candidates.
   A finite two-wave review supports scoped choices, not universal saturation.
5. **A demo algorithm exists.** The missing item is a user-selected strategy,
   universe, horizon, data availability and numeric risk specification. The LEAN
   run proves engine plumbing, not alpha. The packet alone cannot establish that
   no point-in-time vendor was ever evaluated elsewhere in the catalog.
6. **Account access is the current paired-run blocker, not proof of future
   success.** After native access is restored, the new paired workflow still
   requires actual execution and acceptance; unknown defects cannot be ruled out
   by saying the account is the only possible remaining problem.
7. **Proposed overclaims are hypothetical.** The model's `unsupported_claims`
   entries are not verified quotations from project artifacts. The input also
   simplified the fixture as natural-language questions; the actual queries mix
   domain keywords and natural wording. The frozen fixture is authoritative.

The new native Astra-to-Claude paired workflow has not passed. This standalone
Claude review and Desktop Astra research workers are distinct execution paths.
