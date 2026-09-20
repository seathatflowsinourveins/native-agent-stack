-- Every query scope remains separate. Time is exact signed UTC nanoseconds.
-- The current asset snapshot is intentionally absent from historical eligibility.
SELECT * FROM bars
WHERE (?::VARCHAR IS NULL OR case_id = ?::VARCHAR)
  AND event_ns <= ?::BIGINT
  AND observed_ns <= ?::BIGINT
  AND available_ns <= ?::BIGINT
ORDER BY case_id, event_ns, observed_ns, source_sha256;
