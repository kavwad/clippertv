# ClipperTV Development Guide

## Quick Commands
```bash
# Run FastAPI app (mobile-friendly, recommended)
uv sync --extra web
uv run uvicorn clippertv.web.main:app --reload --host 0.0.0.0

# Run Streamlit app (desktop-focused)
uv sync --extra dashboard
uv run streamlit run src/clippertv/app.py

# Tests
uv run pytest                        # All tests
uv run pytest tests/test_auth.py -v  # Auth tests
uv run pytest -k test_name           # Specific test

# Environment
uv run python scripts/test_env.py    # Validate env setup
uv run python migrations/run_migration.py  # Run DB migration

# Formatting
uv run black src/ tests/
uv run mypy src/
```

## Dependencies

**Core dependencies** (always installed):
- PDF processing: `camelot-py`, `pdfminer-six`, `pypdf`
- Database: `libsql` (Turso client)
- Auth: `pyjwt`, `bcrypt`, `cryptography`, `pydantic[email]`
- HTTP: `requests`, `bs4`

**Optional dependencies** (`--extra dashboard`):
- Streamlit UI: `streamlit`

**Optional dependencies** (`--extra web`):
- FastAPI UI: `fastapi`, `jinja2`, `uvicorn`

The Raspberry Pi scheduler only needs core dependencies (no UI packages).

## Architecture

### Data Layer (`src/clippertv/data/`)
- `models.py` - Pydantic models (TransitTransaction, User, ClipperCard, etc.)
- `turso_store.py` - Transaction storage with optional user_id filtering
- `user_store.py` - User/ClipperCard CRUD operations
- `turso_client.py` - Database connection management
- `factory.py` - Data store factory

### Authentication (`src/clippertv/auth/`)
- `service.py` - AuthService (JWT tokens, password hashing with bcrypt)
- `crypto.py` - CredentialEncryption (Fernet encryption for Clipper credentials)

### Visualization (`src/clippertv/viz/`)
- `data_processing.py` - Pivot tables and stats (shared by both UIs)
- `dashboard.py` - Streamlit display functions
- `charts.py` - Plotly charts for Streamlit

### Web UI (`src/clippertv/web/`)
- `main.py` - FastAPI app entry point
- `routes.py` - Dashboard and API endpoints
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
- **Docstrings**: All modules, classes, functions
- **Models**: Use Pydantic
- **Naming**: snake_case (variables/functions), CamelCase (classes)
- **Line length**: Max 88 characters

## Testing
- Auth: `tests/test_auth.py` (13 tests)
- User store: `tests/test_user_store.py` (14 tests)
- Use pytest fixtures for DB client, auth service, crypto

## Phase 1 Status ✅
Multi-user backend complete. See [PLAN.md](PLAN.md) for next steps.
