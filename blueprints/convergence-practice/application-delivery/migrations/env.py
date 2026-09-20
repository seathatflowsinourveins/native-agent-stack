from alembic import context
from sqlalchemy import create_engine
from backend.app import DATABASE_URL

engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1))
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
