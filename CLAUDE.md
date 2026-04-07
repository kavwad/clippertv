# ClipperTV Development Guide

## Quick Commands
```bash
# Run FastAPI app
uv sync --extra web
uv run uvicorn clippertv.web.main:app --reload --host 0.0.0.0

# Download and ingest Clipper card transactions
clipper-download --last-month --ingest
clipper-download --days 14 --ingest    # Rolling window

# Scheduled ingestion (all accounts, last 30 days)
uv run clippertv-ingest --days 30 -v

# Tests
uv run pytest                        # All tests
uv run pytest -k test_name           # Specific test

# DB migrations
uv run python migrations/run_migration.py      # run SQL/Python migrations
```

## Dependencies

**Core dependencies** (always installed):
- Database: `libsql` (Turso client)
- Auth: `pyjwt`, `bcrypt`, `cryptography`, `pydantic[email]`
- HTTP: `requests`, `bs4`
- Data: `pandas`

**Optional dependencies** (`--extra web`):
- FastAPI UI: `fastapi`, `jinja2`, `uvicorn`

## Architecture

### Ingestion (`src/clippertv/ingest/`)
- `clipper.py` - CSV downloader and CLI entry point (`clipper-download`)
- `pipeline.py` - Thin orchestrator: parse CSV → store (no category derivation)

### Scheduler (`src/clippertv/scheduler/`)
- `service.py` - Platform-agnostic ingestion runner (`run_ingestion()`, `clippertv-ingest` CLI); reads Clipper credentials from DB
- `__main__.py` - `python -m clippertv.scheduler` support
- `scheduler/` (repo root) - launchd plist + shell wrapper (platform glue)

### Data Layer (`src/clippertv/data/`)
- `domain.py` - Typed dataclasses (Trip, AggregateBucket, RiderSummary, ComparisonPoint)
- `schema.py` - V2 table DDL (trips, manual_trips, category_rules) and seed data
- `queries.py` - SQL query layer with category_rules JOIN, returns typed objects
- `turso_store.py` - CSV transaction storage with trip_id dedup
- `turso_client.py` - Database connection management
- `models.py` - Pydantic models (User, ClipperCard, AuthToken)
- `user_store.py` - User/ClipperCard CRUD operations

### Analytics (`src/clippertv/analytics/`)
- `pass_costs.py` - Caltrain monthly pass cost injection
- `categories.py` - Category collapsing (top N / "Other")
- `comparison.py` - Cross-rider month alignment
- `summary.py` - Dashboard summary stats

### Authentication (`src/clippertv/auth/`)
- `service.py` - AuthService (JWT tokens, password hashing with bcrypt)
- `crypto.py` - CredentialEncryption (Fernet encryption for Clipper credentials)

### Web UI (`src/clippertv/web/`)
- `main.py` - FastAPI app with Starlette `AuthenticationMiddleware`
- `auth.py` - Cookie-based auth backend, `require_auth` dependency
- `auth_routes.py` - Login/logout + Clipper credential validation on signup
- `settings_routes.py` - Card management (add/remove Clipper cards)
- `routes.py` - Dashboard and API endpoints (uses queries + analytics, no pandas)
- `static/` - `dashboard.js`, `style.css`
- `templates/` - Jinja2 templates with Chart.js and HTMX

### Configuration (`src/clippertv/config.py`)
- `AppConfig` - App settings (transit categories, colors)
- `EnvConfig` - Environment variables (DB, JWT, encryption keys)

### Identity Model
Users sign up with a ClipperTV account (email + password). During signup or in settings, they link Clipper cards by providing clippercard.com credentials, which are validated against the Clipper API and stored encrypted. Each user can have multiple cards; the dashboard is scoped to the authenticated user's cards.

### Identifier Conventions
- **account_number** (long, e.g. `100005510894`): canonical Clipper account ID, stored in `trips.account_number` and `clipper_cards.account_number`. This is the join key.
- **card_serial** (short, e.g. `1202425091`): physical card serial number, stored in `clipper_cards.card_serial`. Optional, not used for data linking.
- **rider_name** (display, e.g. `kaveh`): friendly label for a card, stored in `clipper_cards.rider_name`.

### Key Environment Variables
Required in `.env`:
- `TURSO_DATABASE_URL` - Database URL
- `TURSO_AUTH_TOKEN` - Database auth token
- `JWT_SECRET_KEY` - For JWT signing (generate: `openssl rand -hex 32`)
- `ENCRYPTION_KEY` - For credential encryption (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)

## Code Style
- **Imports**: stdlib → third-party → local
- **Types**: Always use type hints
- **Models**: Use Pydantic
- **Naming**: snake_case (variables/functions), CamelCase (classes)
- **Line length**: Max 88 characters

## Testing
- Scheduler: `tests/scheduler/` (service, CLI)
- Data: `tests/data/` (schema, queries)
- Analytics: `tests/analytics/` (pass costs, categories, comparison, summary)
- Ingest: `tests/ingest/` (CSV parsing, pipeline)
- Auth: `tests/test_auth.py`
- User store: `tests/test_user_store.py`
- Use pytest fixtures for DB client, auth service, crypto
