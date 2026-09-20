"""Initial transactional run ledger."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE runs (
        id uuid PRIMARY KEY,
        title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 120),
        status text NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','running','passed','failed')),
        revision integer NOT NULL DEFAULT 1 CHECK(revision >= 1),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    op.execute("""CREATE TABLE run_events (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        run_id uuid NOT NULL REFERENCES runs(id),
        revision integer NOT NULL CHECK(revision >= 1),
        status text NOT NULL CHECK(status IN ('planned','running','passed','failed')),
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE (run_id, revision)
    )""")


def downgrade():
    op.drop_table("run_events")
    op.drop_table("runs")
