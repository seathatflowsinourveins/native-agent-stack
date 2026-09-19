# Native architecture review adjudication

Both native reviewers received the same bounded 12-fact packet and were asked
to use no tools. Their reports are preserved in [astra.report.json](astra.report.json)
and [claude.report.json](claude.report.json). They did not independently verify
the primary sources. Source research is recorded separately in the catalog.

Accepted suggestions are to retain one baseline engine/workflow owner, require a
numeric research specification and point-in-time data, separate execution realism
from successful backtesting, keep advanced routing unaccepted, and validate
recovery before unattended hosting. These now appear in the architecture and
open gates. Neither model's agreement establishes strategy validity.

Corrections to Claude's report:

1. Its proposal to stop all catalog/architecture work until the user supplies a
   numeric strategy spec is too broad. The user explicitly authorized this
   research. Independent source review, data contracts and architecture can
   proceed; provisional research specs can be proposed transparently. Actual
   capital/risk and broker progression require the user's decisions.
2. Its IEX statement must be limited to a **paper-only account**. A generic paper
   account's feed cannot be inferred without its entitlements. No account/feed
   entitlement was inspected in this wave.
3. Dagu scheduling does not establish durable in-graph checkpoints or currently
   accepted unattended scheduling. Optional DeerFlow/LangGraph internals and a
   Dagu job boundary are different responsibilities.
4. Official Elite capabilities are documented vendor features, not merely an
   unsupported marketing guess. What is unverified is this account's eligibility,
   limits, actual adapter behavior and performance. A trading product's
   subscription is also separate from coding-client hosting terms.
5. Its conclusion that there is one blocking item is incomplete: accepted data,
   recovery destination and broker entitlement are also independent gates.

Astra appropriately labels its architectural priorities as inferences. Its
proposal for offline fault injection is a next acceptance activity, not work
already completed by these reviews. Both reports include the earlier 453-row
historical index and 37,069-token paired run as packet facts; the current typed
union and this wave's new token usage are recorded separately.

The offline Alpaca probe is a compatibility observation. It does **not** implement
an order boundary, make upstream Pydantic reject unknown fields, or prove valid
DMA/VWAP/TWAP request schemas. The architecture requires that later behavior;
the current code only detects failure to preserve synthetic instructions.

Packet fact F6 abbreviated the engine receipt path incorrectly as
`blueprints/us-equities/receipt.json`; the retained native engine evidence is
`blueprints/us-equities/engine/receipt.json`. The original supplied packet is
preserved so its bytes and model input remain reproducible.
