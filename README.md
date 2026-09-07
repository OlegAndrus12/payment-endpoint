# payment-endpoint

A small Flask service that charges a user's saved card for a shopping cart.
A user adds products to a cart; `POST /carts/<cart_id>/payments` totals the
cart, charges the user's default payment method through a mock payment
provider, records a `payments` row, and marks the cart as checked out.

## Stack

| Layer          | Choice                                                      |
| -------------- | ----------------------------------------------------------- |
| Language       | Python 3.12                                                  |
| Web framework  | [Flask](https://flask.palletsprojects.com/) 3 (blueprints)   |
| WSGI server    | [gunicorn](https://gunicorn.org/) (in Docker)                |
| ORM            | [SQLAlchemy](https://www.sqlalchemy.org/) 2.0 typed declarative, via Flask-SQLAlchemy |
| Migrations     | [Alembic](https://alembic.sqlalchemy.org/) via Flask-Migrate |
| Database       | PostgreSQL 16 (`psycopg2`, `pgcrypto` for `gen_random_uuid()`) |
| Settings       | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Packaging      | [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`) |
| Tests          | [pytest](https://docs.pytest.org/), [factory_boy](https://factoryboy.readthedocs.io/), [Faker](https://faker.readthedocs.io/) |
| Lint / format  | [ruff](https://docs.astral.sh/ruff/), [black](https://black.readthedocs.io/) |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for PostgreSQL, and optionally for the app itself)

## Project layout

```
app/
  __init__.py          # create_app() application factory
  config.py            # pydantic-settings Settings, loaded from .env
  main.py              # payments blueprint (HTTP layer)
  payment_service.py   # use case: start_payment(cart_id)
  payment_provider.py  # mock payment gateway
  repository.py        # Repository(session) — all data access
  session.py           # session_scope() unit-of-work context manager
  models.py            # SQLAlchemy models + the db instance
  errors.py            # domain exceptions + Flask error handlers
migrations/            # Alembic environment and versions
tests/                 # pytest suite, fixtures, factories
```

The request flow is `main.py` → `payment_service.py` → `repository.py`, with
domain exceptions from `errors.py` translated to HTTP responses by the
handlers registered in `create_app()`.

## Build and run

### Option A — everything in Docker

```bash
docker compose up -d --build
```

| Service   | Default URL            | Port variable   | Notes                        |
| --------- | ---------------------- | --------------- | ---------------------------- |
| `web`     | http://127.0.0.1:8000  | `WEB_PORT`      | Flask app served by gunicorn |
| `db`      | localhost:5433         | `POSTGRES_PORT` | PostgreSQL 16                |
| `pgadmin` | http://127.0.0.1:5051  | `PGADMIN_PORT`  | DB browser, see [Browsing the database](#browsing-the-database) |

[docker-entrypoint.sh](docker-entrypoint.sh) runs `flask db upgrade` before
starting gunicorn, so migrations are applied on every container start — no
separate migration step is needed with this option.

```bash
curl -X POST http://127.0.0.1:8000/carts/eb1167b3-67a9-4378-bc65-c1e582e2e662/payments
```

### Option B — PostgreSQL in Docker, app run locally

Faster iteration: no image rebuild between code changes.

```bash
docker compose up -d db        # PostgreSQL on localhost:5433
uv sync                        # create .venv and install dependencies
cp .env.example .env           # optional — the defaults already match compose
uv run flask db upgrade        # apply migrations
uv run flask run               # http://127.0.0.1:5000
```

> PostgreSQL is published on port **5433**, not the default 5432, so it
> doesn't clash with a local Postgres install. Change it with `POSTGRES_PORT`
> — compose and the app both read it.

## Configuration

[app/config.py](app/config.py) defines a pydantic-settings `Settings` model
that reads these from the environment, falling back to a `.env` file
(`cp .env.example .env`) and then to the defaults below. Every value has a
default, so the app runs against a stock `docker compose up -d db` without a
`.env` at all.

| Variable            | Default                 | Purpose                             |
| ------------------- | ----------------------- | ----------------------------------- |
| `POSTGRES_HOST`     | `localhost`             | Database host                       |
| `POSTGRES_PORT`     | `5433`                  | Database port                       |
| `POSTGRES_USER`     | `postgres`              | Database user                       |
| `POSTGRES_PASSWORD` | `postgres`              | Database password                   |
| `POSTGRES_DB`       | `payment_endpoint`      | Application database name           |
| `POSTGRES_TEST_DB`  | `payment_endpoint_test` | Database used by the pytest suite   |

The connection string itself is not configured directly — `Settings` builds it
from those parts with SQLAlchemy's `URL.create()`, exposed as
`settings.database_url` and `settings.test_database_url`. Going through
`URL.create()` rather than an f-string means credentials containing `@`, `/`,
or other reserved characters are percent-encoded correctly.

[docker-compose.yml](docker-compose.yml) reads the same variables (with the
same defaults) for the `db` container and passes them through to `web`,
overriding `POSTGRES_HOST=db` and `POSTGRES_PORT=5432` so the container talks
to Postgres over the compose network instead of the published host port.
`WEB_PORT` (`8000`), `PGADMIN_PORT` (`5051`), `PGADMIN_EMAIL`, and
`PGADMIN_PASSWORD` are configurable the same way.

## API

### `POST /carts/<cart_id>/payments`

No request body. The endpoint charges the cart owner's payment method where
`is_default = TRUE`.

```bash
curl -X POST http://127.0.0.1:5000/carts/eb1167b3-67a9-4378-bc65-c1e582e2e662/payments
```

```json
{
  "amount": "139.78",
  "cart_id": "eb1167b3-67a9-4378-bc65-c1e582e2e662",
  "currency": "USD",
  "failure_reason": null,
  "id": "187bc376-d242-4eb3-8236-d6a6bb413adf",
  "provider_reference": "mock_txn_fadf70e2-5e0d-472f-ad48-5374f3188ab0",
  "status": "succeeded"
}
```

| Case                                | Status | Body                                                   |
| ----------------------------------- | ------ | ------------------------------------------------------ |
| Charge succeeded                    | 201    | payment resource, `status: "succeeded"`                 |
| Charge declined by the provider     | 402    | payment resource, `status: "failed"`, `failure_reason`  |
| Cart doesn't exist                  | 404    | `{"error": "cart_not_found"}`                           |
| Cart already paid                   | 409    | `{"error": "cart_already_paid", "payment": {...}}`      |
| Cart is abandoned                   | 409    | `{"error": "cart_abandoned"}`                           |
| Cart has no items                   | 422    | `{"error": "cart_empty"}`                               |
| User has no default payment method  | 422    | `{"error": "no_default_payment_method"}`                |
| Provider raised an unexpected error | 502    | `{"error": "provider_unavailable"}`                     |

## Mock payment provider

[app/payment_provider.py](app/payment_provider.py) charges deterministically
rather than randomly, so behaviour is reproducible in tests and by hand:

- any `provider_token` **except** `tok_test_decline` succeeds, returning a
  `mock_txn_<uuid>` reference;
- `tok_test_decline` always declines with `failure_reason: "card_declined"`.

To see a decline, set a payment method's `provider_token` to
`tok_test_decline` and repeat the request — it returns `402` with
`"status": "failed"`.

## Database

Six tables: `users`, `products`, `carts`, `cart_items`,
`user_payment_methods`, and `payments`. The models in
[app/models.py](app/models.py) carry the full schema — CHECK constraints,
foreign keys with `ON DELETE CASCADE`, and the partial unique index on
`payments` — via `__table_args__`, and the migrations are Alembic
autogenerated from them (`flask db migrate` against the current models
reports no changes).

```bash
uv run flask db upgrade      # apply migrations
uv run flask db downgrade    # roll back one revision
uv run flask db migrate -m "message"
```

The third migration seeds one user, one product, one cart with a single item,
and one default payment method, so the endpoint is usable immediately after
`flask db upgrade`. All seed values — including the row IDs — come from Faker
with a fixed seed (`Faker.seed(0)`), which is why the cart ID and the
`139.78` total above are exactly what you'll get on a fresh database.

### Browsing the database

`docker compose up` also starts pgAdmin on http://127.0.0.1:5051. It runs in
desktop mode (`PGADMIN_CONFIG_SERVER_MODE: "False"`), so it opens straight
into the browser UI with no login. `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` are
still required by the image at startup, but you won't be asked for them.

A `payment-endpoint` server pointing at the `db` container is provisioned
automatically from [pgadmin/servers.json](pgadmin/servers.json), which is
mounted into the container. Expand it and enter the Postgres password
(`POSTGRES_PASSWORD`, `postgres` by default) when prompted — pgAdmin stores
the connection, not the password.

pgAdmin imports `servers.json` **only on first start**, while its
`pgadmin_data` volume is still empty. If you edit that file, or you changed
`POSTGRES_USER` / `POSTGRES_DB` after pgAdmin had already started, reset the
volume to re-import:

```bash
docker compose down -v && docker compose up -d
```

To add the connection by hand instead — *Register → Server*, then:

| Field           | Value                                          |
| --------------- | ---------------------------------------------- |
| Name            | anything                                        |
| Host            | `db` (the compose service, not `localhost`)     |
| Port            | `5432` (the in-network port, not `POSTGRES_PORT`) |
| Maintenance DB  | `POSTGRES_DB` (`payment_endpoint`)              |
| Username        | `POSTGRES_USER` (`postgres`)                    |
| Password        | `POSTGRES_PASSWORD` (`postgres`)                |

## Tests

```bash
uv run pytest
```

The suite runs against a separate `payment_endpoint_test` database on the
same Postgres instance (created automatically on first run) and never touches
your development data. Each test truncates the app tables afterwards, and
rows are built with the factory_boy factories in
[tests/factories.py](tests/factories.py).

## Development

`uv sync` installs the `dev` dependency group (pytest, factory_boy, ruff,
black) alongside the runtime dependencies.

```bash
uv sync                        # install everything, create .venv
uv add <package>               # add a runtime dependency, updates uv.lock
uv add --dev <package>         # add a dev dependency
uv run ruff check .            # lint
uv run black .                 # format
uv run pytest                  # tests
```

Both linters target `py312`, configured in [pyproject.toml](pyproject.toml).

After changing a model in [app/models.py](app/models.py), generate the
matching migration and review it before committing:

```bash
uv run flask db migrate -m "describe the change"
uv run flask db upgrade
```

Flask finds the app through its `app` package / `create_app()` convention, so
no `FLASK_APP` environment variable is needed.

## Troubleshooting

**`connection refused` on port 5433** — the database container isn't running
(`docker compose up -d db`), or `POSTGRES_PORT` in your `.env` doesn't match
the port compose published. Check with `docker compose ps`.

**Port 5433 or 8000 already in use** — set `POSTGRES_PORT` or `WEB_PORT` in
`.env`; both compose and the app pick the new value up.

**`relation "carts" does not exist`** — migrations haven't been applied. Run
`uv run flask db upgrade` (the Docker `web` service does this automatically on
start).

**Code changes don't show up under `docker compose up`** — the image copies
the source at build time and there's no bind mount, so rebuild with
`docker compose up -d --build`, or use Option B for iteration.

**pgAdmin has no server configured** — `servers.json` is imported only on
pgAdmin's first start. Run `docker compose down -v && docker compose up -d` to
reset its volume, or add the server manually; see
[Browsing the database](#browsing-the-database).

**pgAdmin can't connect to `localhost:5433`** — that's the host-side address.
From inside the compose network, use host `db` and port `5432`.
