-- Realized observations and effective universe state, using explicit knowledge cutoffs.
-- Parameters: cutoff, universe_id, feed, adjustment, field, unit.
WITH requested AS (
    SELECT ?::TIMESTAMPTZ AS cutoff, ?::VARCHAR AS universe_id,
           ?::VARCHAR AS feed, ?::VARCHAR AS adjustment,
           ?::VARCHAR AS field, ?::VARCHAR AS unit
), membership AS (
    SELECT u.*
    FROM universe u, requested r
    WHERE u.universe_id = r.universe_id
      AND u.available_at <= r.cutoff AND u.effective_at <= r.cutoff
    QUALIFY row_number() OVER (
        PARTITION BY u.asset_id
        ORDER BY u.effective_at DESC, u.available_at DESC
    ) = 1
), selected AS (
    SELECT o.*, m.row_id AS universe_row_id,
           m.effective_at AS universe_effective_at,
           m.available_at AS universe_available_at
    FROM observations o
    JOIN membership m ON o.asset_id = m.asset_id AND m.is_member
    CROSS JOIN requested r
    WHERE o.available_at <= r.cutoff AND o.event_at <= r.cutoff
      AND o.feed = r.feed AND o.adjustment = r.adjustment
      AND o.field = r.field AND o.unit = r.unit
    QUALIFY row_number() OVER (
        PARTITION BY o.asset_id, o.field, o.unit
        ORDER BY o.event_at DESC, o.available_at DESC
    ) = 1
)
SELECT * EXCLUDE (value_decimal) FROM selected ORDER BY asset_id, field, unit;
