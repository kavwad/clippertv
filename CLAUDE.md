# ClipperTV Development Guide

## Commands
- Run app: `python run_app.py` or `streamlit run src/clippertv/app.py`
- Install dev: `pip install -e .`
- Run tests: `pytest tests/` (future)
- Run single test: `pytest tests/path_to_test.py::test_function_name` (future)
- Format code: `black src/ tests/`
- Type check: `mypy src/`

### Turso Commands
- Migrate from Supabase backup: `python -m clippertv.data.migrate_to_turso [backup_file]`
- Dry run migration: `python -m clippertv.data.migrate_to_turso --dry-run`
- Toggle storage backend: `CLIPPERTV_STORAGE=turso python run_app.py`
- Required env vars: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`

## Code Style
- **Imports**: Group imports in order: standard library, third-party, local
- **Types**: Use type hints with all function signatures (typing module)
- **Docstrings**: Use triple-quoted docstrings for all modules, classes, and functions
- **Classes**: Prefer Pydantic models for structured data
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Error handling**: Use specific exceptions with meaningful messages
- **Modules**: Keep modules focused on single responsibility
- **Functions**: Keep functions small, under 30 lines when possible
- **Line length**: Max 88 characters per line

## Architecture
- Data layer (models, storage) in `data/` module
  - `models.py`: Pydantic data models
  - `schema.py`: Database schema definitions
  - `store.py`: Google Cloud Storage implementation (legacy)
  - `turso_store.py`: Turso implementation (current)
  - `turso_client.py`: Turso connection management
  - `factory.py`: Data store factory (selects appropriate implementation)
  - `migrate_to_turso.py`: Migration tool
- PDF processing in `pdf/` module
- Visualization components in `viz/` module
- Main app in `app.py`

## Data Storage
- **Google Cloud Storage**: Legacy CSV-based implementation
  - CSV files stored in GCS bucket
  - Each rider has dedicated CSV file
  - Configured via Streamlit secrets
- **Turso**: LibSQL/SQLite-based implementation (CURRENT)
  - Edge database built on SQLite
  - Relational model: Riders, Transit Modes, Trips
  - No auto-pause on free tier
  - 5GB storage, 500M row reads/month free
  - Configured via `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`
  - Direct remote connection for simplicity