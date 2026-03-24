# ClipperTV Development Guide

## Quick Commands
```bash
# Run FastAPI app
uv sync --extra web
uv run uvicorn clippertv.web.main:app --reload --host 0.0.0.0

# Download and ingest Clipper card transactions
clipper-download --last-month --ingest

# Tests
uv run pytest                        # All tests
uv run pytest -k test_name           # Specific test

# DB migration
uv run python migrations/run_migration.py
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
- `pipeline.py` - Orchestrates parsing, categorization, and DB storage
- `categories.py` - Operator-based transit category detection

### Data Layer (`src/clippertv/data/`)
- `models.py` - Pydantic models (User, ClipperCard, AuthToken)
- `turso_store.py` - Transaction storage with trip_id dedup and load-time normalization
- `user_store.py` - User/ClipperCard CRUD operations
- `turso_client.py` - Database connection management and schema migrations
- `factory.py` - Data store factory

### Authentication (`src/clippertv/auth/`)
- `service.py` - AuthService (JWT tokens, password hashing with bcrypt)
- `crypto.py` - CredentialEncryption (Fernet encryption for Clipper credentials)

### Visualization (`src/clippertv/viz/`)
- `data_processing.py` - Pivot tables and summary stats for the dashboard

### Web UI (`src/clippertv/web/`)
- `main.py` - FastAPI app entry point
- `routes.py` - Dashboard and API endpoints (dynamic rider list from DB)
- `templates/` - Jinja2 templates with Chart.js

### Configuration (`src/clippertv/config.py`)
- `AppConfig` - App settings (transit categories, colors)
- `EnvConfig` - Environment variables (DB, JWT, encryption keys)

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
- Ingest: `tests/ingest/` (categories, CSV parsing, pipeline)
- Auth: `tests/test_auth.py`
- User store: `tests/test_user_store.py`
- Dashboard: `tests/viz/test_dashboard.py`
- Use pytest fixtures for DB client, auth service, crypto
