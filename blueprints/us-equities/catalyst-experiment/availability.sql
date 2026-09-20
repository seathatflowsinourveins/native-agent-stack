-- Project-owned eligibility contract executed by native DuckDB.
-- BIGINT nanoseconds stay exact; quality is separate from historical availability.
SELECT observation_id
FROM observations
WHERE available_at_ns IS NOT NULL
  AND available_at_ns >= feature_end_ns
  AND available_at_ns <= $cutoff
  AND feature_end_ns <= $cutoff
  AND quality_qualified IS TRUE
ORDER BY observation_id;
