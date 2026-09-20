-- Source-supported documentary claims available to this observer.
-- This selects no asset universe, tradability, fill, or latest semantic revision.
SELECT case_id, documentary_security_scope, event_kind, symbol_before, symbol_after,
       effective_date, effective_timing, publisher_claimed_publication,
       sec_acceptance_raw, sec_acceptance_zone, sec_filing_date_raw,
       observed_ns, available_ns, source_id, source_sha256
FROM claims
WHERE status = 'supported_documentary_claim' AND available_ns <= ?
ORDER BY case_id;
