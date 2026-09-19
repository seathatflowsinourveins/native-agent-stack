# Native paired review and coordinator adjudication

The unchanged native Dagu workflow ran GPT-6 Astra through the installed official
Codex SDK, then native Claude Opus 5 against the accepted Astra report. Both
completed on their first attempt; the upstream history reports **27 seconds**.
The [receipt](review-receipt.json) binds the packet, reports, native results,
private command hashes and exported Astra observation.

Native reported usage was **21,066 Astra + 16,085 Claude = 37,151 tokens**.
This is usage for this pair, excluding the coordinator, other workers and prior
waves. Cached inputs are included in those counters. No causal net token saving
was measured. The dashboard SDK panel includes its observed Astra receipt; it
does not silently combine that receipt with overlapping native histograms or the
separate Claude terminal result.

The models correctly limited the new native memory, timestamp and supervision
acceptances to their fixtures. Their agreement does not verify the underlying
evidence; independent code/source review and deterministic native checks do that.

The packet's 169 pinned-file figure counts per-lane captures; independent review
found 167 distinct repository/path/hash files because two license captures recur
across lanes. This is a capture count, not 169 unique implementations or complete
file audits. That clarification does not alter the original frozen packet.

Two model limitations need correction rather than repetition as facts. The
packet's `as_of` is a review date, while the memory API's `as_of` denotes
ingestion-time version selection. Those are different fields in different
contexts. SEC reporting periods and amendments are inapplicable to this
engineering packet, as Claude partly identified. Also, historical simulation is
not globally unestablished: prior native LEAN receipts already exist, and the new
historical stress experiment is a separate acceptance. Neither proves alpha,
full historical universe coverage or broker fill realism.

No rerun was needed to correct these interpretive limitations. The original
reports are preserved unchanged. The coordinator retains responsibility for
source adjudication, deterministic checks and publication.
