# Payment Endpoint

Take-home task: the payment part of an online shop. A user adds products to a
cart; this service charges the user's saved card for that cart via a mock
payment provider.

## What's here

- A `payments` table, added to the employer-provided base schema.
- `POST /carts/<cart_id>/payments` — starts payment for a cart.
- A deterministic mock payment provider (no real payment integration).
- A pytest suite covering the endpoint's success, error, and edge-case paths.

## Requirements

- Docker
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

There are two ways to run this: everything in Docker (one command, no local
Python setup), or just Postgres in Docker with the app run locally via `uv`
(faster iteration — no image rebuild between code changes).

## Option A: everything in Docker

```bash
docker compose up -d --build
```

This builds the app image and starts three containers:

| Service   | URL                            | What it is |
| --------- | ------------------------------- | ---------- |
| `web`     | http://127.0.0.1:8000           | the Flask app, served by gunicorn |
| `db`      | localhost:5433                  | Postgres |
| `pgadmin` | http://127.0.0.1:5051            | a DB browser, pre-configured with a `payment-endpoint` connection to `db` (login `admin@example.com` / `admin`; the Postgres password is `postgres`) |

`web`'s entrypoint ([docker-entrypoint.sh](docker-entrypoint.sh)) runs
`flask db upgrade` before starting gunicorn, so migrations are always applied
on startup — no separate migration step needed with this option.

```bash
curl -X POST http://127.0.0.1:8000/carts/eb1167b3-67a9-4378-bc65-c1e582e2e662/payments
```

## Option B: Postgres in Docker, app run locally

```bash
docker compose up -d db        # starts Postgres on localhost:5433
uv sync                        # creates .venv and installs dependencies
cp .env.example .env
uv run flask db upgrade        # applies all migrations to the dev database
uv run flask run               # serves on http://127.0.0.1:5000
```

> Postgres is mapped to port **5433**, not the default 5432, in case another
> Postgres instance is already running locally.

The seed migration creates one user with a default payment method and one
cart (`eb1167b3-67a9-4378-bc65-c1e582e2e662`) holding a single item, so you
can try the endpoint immediately. Names, emails, and the product's price are
[Faker](https://faker.readthedocs.io/)-generated but seeded (`Faker.seed(0)`),
so the amount below (an unglamorous but deterministic `139.78`) is exactly
what you'll see too:

```bash
curl -X POST http://127.0.0.1:5000/carts/eb1167b3-67a9-4378-bc65-c1e582e2e662/payments
```

```json
{
  "id": "...",
  "cart_id": "eb1167b3-67a9-4378-bc65-c1e582e2e662",
  "status": "succeeded",
  "amount": "139.78",
  "currency": "USD",
  "provider_reference": "mock_txn_...",
  "failure_reason": null
}
```

To see a decline, give a payment method `provider_token = 'tok_test_decline'`
(the mock provider always declines this token — see "Mock payment provider"
below) and the same request returns `402` with `"status": "failed"`.

### Responses

| Case                                  | Status | Body                                            |
| -------------------------------------- | ------ | ------------------------------------------------ |
| Charge succeeded                       | 201    | payment resource, `status: "succeeded"`           |
| Charge declined by the provider        | 402    | payment resource, `status: "failed"`, `failure_reason` |
| Cart doesn't exist                     | 404    | `{"error": "cart_not_found"}`                     |
| Cart already paid                      | 409    | `{"error": "cart_already_paid", "payment": {...}}` |
| Cart is abandoned                      | 409    | `{"error": "cart_abandoned"}`                     |
| Cart has no items                      | 422    | `{"error": "cart_empty"}`                         |
| User has no default payment method     | 422    | `{"error": "no_default_payment_method"}`          |
| Provider raised an unexpected error    | 502    | `{"error": "provider_unavailable"}`               |

## Running tests

```bash
uv run pytest
```

Tests run against a separate `payment_endpoint_test` database on the same
Postgres container (created automatically on first run) and don't touch your
dev data.

## Mock payment provider

`app/payment_provider.py` charges deterministically instead of randomly, so
behavior is reproducible in tests and manual testing:

- Any `provider_token` **except** `tok_test_decline` succeeds.
- `provider_token = "tok_test_decline"` always declines with
  `failure_reason: "card_declined"`.

## Assumptions

Requirements the task left open, and the choice made for each:

1. **Which payment method gets charged.** The endpoint takes only `cart_id`
   — no `payment_method_id` in the request. It charges the user's payment
   method where `is_default = TRUE`. If none exists, the request fails with
   `422 no_default_payment_method`.
2. **Repeat calls for the same cart.** Cart status is the source of truth
   for idempotency. Calling the endpoint again for an already-`checked_out`
   cart returns `409` with the prior payment instead of charging twice.
   Calling it for an `abandoned` cart is also rejected (`409`). A `payments`
   partial unique index (`cart_id` where `status` is `pending` or
   `succeeded`) backs this at the database level too, so a race between two
   concurrent requests for the same cart can't double-charge it.
3. **Total to charge.** Computed as `sum(quantity * unit_price)` over the
   cart's items, using the price already snapshotted on `cart_items` at
   add-to-cart time — this task doesn't need to reproduce the shop's real
   pricing/tax logic.
4. **Currency.** Taken from the first cart item's product. The schema (and
   its seed data) only has one shop-wide currency (`USD`), so this doesn't
   handle a hypothetical mixed-currency cart.
5. **`payments.status = 'pending'`.** Included in the schema for
   completeness/future async providers, but unused by the current flow —
   the mock provider always resolves synchronously to `succeeded` or
   `failed` within the same request.
6. **Failed payments are retryable.** A `failed` payment doesn't block a
   later attempt on the same cart (only `pending`/`succeeded` do) — a
   declined card shouldn't permanently lock the cart.

## Notable design/tooling choices

- **Type annotations** are used throughout (SQLAlchemy 2.0 typed
  declarative models, typed function signatures) per PEP 484.
- **`carts.status` and `payments.status`** are `enum.StrEnum` (`CartStatus`,
  `PaymentStatus` in `app/models.py`) mapped through SQLAlchemy's `Enum`
  type with `native_enum=False` — code compares against
  `CartStatus.CHECKED_OUT`/`PaymentStatus.SUCCEEDED` instead of raw string
  literals, but the column stays a plain `VARCHAR` (Postgres computed
  `VARCHAR(11)`/`VARCHAR(9)`, sized to the longest member) rather than a
  native Postgres `ENUM` type, so it's still just a string on the wire —
  no `CREATE TYPE`, no separate migration path for adding a new status
  value later. Since `StrEnum` members are real `str` instances, they
  serialize through `jsonify()` as plain strings (`"succeeded"`, not
  `"PaymentStatus.SUCCEEDED"`) with no extra handling, and the existing
  `CHECK (status IN (...))` constraints still enforce valid values at the
  database level — the enum type is for the Python side, the CHECK
  constraint is still what actually guards the column.
- **`app/payment_service.py`** imports the `payment_provider` module (not
  the bare `charge` function) and calls `payment_provider.charge(...)`.
  This matters for testing: it lets `monkeypatch.setattr(payment_provider,
  "charge", ...)` reliably intercept the call, which wouldn't work if the
  function name were imported directly into `payment_service`'s namespace.
- **Test isolation** truncates all app tables after each test rather than
  the more common "wrap in a SAVEPOINT and roll back" recipe — Flask-
  SQLAlchemy 3.x's `Session.get_bind()` always resolves to the app's real
  engine regardless of any bind configured on the session, which defeats
  that recipe.
- **`tests/factories.py`** uses [factory_boy](https://factoryboy.readthedocs.io/)
  (`SQLAlchemyModelFactory`, with `factory.Faker`-style helpers backed by
  the same `Faker` instance used for names/emails/product names) instead
  of hand-written `make_user`/`make_product`/... fixtures. `CartFactory`
  and `UserPaymentMethodFactory` declare a real `user = factory.SubFactory`
  relationship rather than juggling `user_id` by hand, which is also why
  `Cart.user` and `UserPaymentMethod.user` relationships exist on the
  models — they're not used by any production code path (the service/
  repository layer only ever needs `cart.user_id`), they exist purely so
  tests can write `CartItemFactory(cart=cart)` and
  `UserPaymentMethodFactory(user=cart.user)` instead of threading IDs
  through every call.
- **`app/models.py`** owns the `db` instance and every SQLAlchemy model.
  **`app/repository.py`** owns data access: a `Repository` class
  constructed with a `Session` (`Repository(session)`, methods use
  `self.session`) rather than free functions closing over a global —
  closer to a plain constructor-injected data-access object than to
  Flask-SQLAlchemy's usual `db.session` singleton style. **`app/session.py`**
  owns the session lifecycle: a `session_scope()` context manager — commit
  on success, roll back on any exception — that `payment_service.py` wraps
  around the whole unit of work (`with session_scope() as session: repo =
  Repository(session)`), so the service layer never has to remember to roll
  back on each individual failure path. The concurrent-double-charge race
  (a unique constraint violation on commit) surfaces as a plain
  `sqlalchemy.exc.IntegrityError`, which `payment_service.py` catches and
  turns into the domain-level `CartAlreadyPaid`.
  (Note: this file is named `session.py`, not `db.py` — naming it `db.py`
  collides with the `db` object imported from `app.models` into
  `app/__init__.py`: importing the `app.db` submodule anywhere causes
  Python to overwrite that `db` name in the package namespace with the
  submodule itself, so `db.init_app(app)` fails with `AttributeError`.)
- **`app/errors.py`** owns every domain exception (`CartNotFound`,
  `CartAlreadyPaid`, ...) alongside the Flask handlers that map them to HTTP
  responses, so the exception type and its status code live next to each
  other instead of in two files.
- **The Docker image** (`Dockerfile`) installs with `uv sync --locked
  --no-dev` before copying app code, so dependency layers stay cached across
  code-only changes. `docker-entrypoint.sh` runs migrations before starting
  gunicorn, so `docker compose up --build` alone leaves you with a fully
  migrated, running app — not just a container that immediately 500s on a
  missing table.
- **Migrations are Alembic-autogenerated from `app/models.py`**, not
  hand-written raw SQL — `migrations/versions/..._base_schema.py` (all six
  tables, including `payments`) was produced by `flask db migrate`, with
  only the `CREATE EXTENSION "pgcrypto"` line added by hand (Alembic has no
  op for Postgres extensions). This means the models carry the full schema
  — CHECK constraints, the partial unique index on `payments`, `ON DELETE
  CASCADE` — via `__table_args__`, rather than those living only in the
  migration. Running `flask db migrate` again against the current models
  reports "No changes in schema detected," confirming the two stay in
  sync. The second migration, `..._seed_base_schema_data.py`, seeds one
  user, one product, one cart with one item, and one default payment
  method — via `op.bulk_insert()` against the models' own `__table__`
  (e.g. `User.__table__`), not a hand-redeclared shadow table. Alembic's
  own docs recommend redeclaring tables with `sa.table()`/`sa.column()` in
  data migrations, so a migration keeps working even if the ORM models
  change later — a real property for a long-lived app, but more ceremony
  than this project needs. Names, emails, tokens, the product's price, and
  even the row IDs themselves all come from
  [Faker](https://faker.readthedocs.io/) (`fake.uuid4(cast_to=None)`), no
  hand-picked literals anywhere. This only works because Faker is seeded
  (`Faker.seed(0)`) and the IDs are generated once at module import time,
  before `upgrade()`/`downgrade()` run — since `flask db upgrade` and
  `flask db downgrade` are separate process invocations, each one imports
  this file fresh, and the fixed seed reproduces the exact same sequence
  of "random" values every time. That's what lets `downgrade()` reference
  `USER_ID`/`CART_ID`/etc. and reliably find the same rows `upgrade()`
  inserted, potentially in a completely different run days later, and
  it's also why this README's example output stays accurate across every
  fresh `docker compose up --build`.
