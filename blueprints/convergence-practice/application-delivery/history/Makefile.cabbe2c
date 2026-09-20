.PHONY: setup schema migrate migrate-test run test verify browser postgres-install postgres-init postgres-start postgres-stop postgres-databases

setup:
	UV_CACHE_DIR=.runtime/uv-cache uv sync --frozen --no-build
	pnpm install --frozen-lockfile --ignore-scripts --store-dir .runtime/pnpm-store

schema:
	uv run --frozen python -m backend.export_openapi
	pnpm types

migrate:
	uv run --frozen alembic upgrade head

migrate-test:
	DATABASE_URL=postgresql://postgres@127.0.0.1:15432/ledger_test uv run --frozen alembic upgrade head

run:
	python3 serve.py

test:
	DATABASE_URL=postgresql://postgres@127.0.0.1:15432/ledger_test uv run --frozen pytest -q

browser:
	pnpm test:e2e

verify:
	pnpm peers check
	uv run --frozen python verify_schema.py
	pnpm typecheck
	NEXT_TELEMETRY_DISABLED=1 pnpm build
	DATABASE_URL=postgresql://postgres@127.0.0.1:15432/ledger_test uv run --frozen pytest -q
	pnpm test:e2e

# One-time native source build. Refuse to overwrite an existing installation.
postgres-install:
	test ! -e .runtime/postgresql/18.6
	mkdir -p .runtime/postgresql-source .runtime/postgresql-build
	curl --fail --location --proto '=https' --tlsv1.2 https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2 --output .runtime/postgresql-source/postgresql-18.6.tar.bz2
	printf '%s  %s\n' 555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f .runtime/postgresql-source/postgresql-18.6.tar.bz2 | shasum -a 256 -c -
	tar -xjf .runtime/postgresql-source/postgresql-18.6.tar.bz2 -C .runtime/postgresql-source
	cd .runtime/postgresql-build && ../postgresql-source/postgresql-18.6/configure --prefix="$$(pwd)/../postgresql/18.6" --without-icu --without-readline --without-zlib
	$(MAKE) -C .runtime/postgresql-build -j 4
	$(MAKE) -C .runtime/postgresql-build install
	cp .runtime/postgresql-source/postgresql-18.6/COPYRIGHT .runtime/postgresql/18.6/COPYRIGHT

postgres-init:
	test ! -e .runtime/native-pgdata
	.runtime/postgresql/18.6/bin/initdb --pgdata=.runtime/native-pgdata --username=postgres --auth=trust --no-locale --encoding=UTF8
	printf "\nlisten_addresses = '127.0.0.1'\nport = 15432\nunix_socket_directories = ''\n" >> .runtime/native-pgdata/postgresql.conf

postgres-start:
	.runtime/postgresql/18.6/bin/pg_ctl -D .runtime/native-pgdata -l .runtime/postgres.log -w start

postgres-stop:
	.runtime/postgresql/18.6/bin/pg_ctl -D .runtime/native-pgdata -m fast -w stop

postgres-databases:
	.runtime/postgresql/18.6/bin/createdb --host=127.0.0.1 --port=15432 --username=postgres ledger
	.runtime/postgresql/18.6/bin/createdb --host=127.0.0.1 --port=15432 --username=postgres ledger_test
