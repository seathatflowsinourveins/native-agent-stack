-- All temporal predicates and ordering use signed integer UTC nanoseconds.
WITH requested AS (
    SELECT ?::BIGINT cutoff_ns, ?::VARCHAR universe_id, ?::VARCHAR feed
), members AS (
    SELECT u.* FROM universe u, requested r
    WHERE u.universe_id = r.universe_id
      AND u.available_ns <= r.cutoff_ns AND u.effective_ns <= r.cutoff_ns
    QUALIFY row_number() OVER (
        PARTITION BY asset_id ORDER BY effective_ns DESC, available_ns DESC, source_sequence DESC
    ) = 1
), versions AS (
    SELECT o.*, m.row_id AS universe_row_id, m.effective_ns AS universe_effective_ns
    FROM observations o JOIN members m ON o.asset_id = m.asset_id AND m.is_member
    CROSS JOIN requested r
    WHERE o.feed = r.feed AND o.event_ns <= r.cutoff_ns AND o.available_ns <= r.cutoff_ns
    QUALIFY row_number() OVER (
        PARTITION BY o.asset_id, o.logical_event_id, o.feed
        ORDER BY o.available_ns DESC, o.source_sequence DESC
    ) = 1
)
SELECT * FROM versions ORDER BY asset_id, logical_event_id;
