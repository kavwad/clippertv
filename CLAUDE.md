# ClipperTV Development Guide

## Commands
- Run app: `uv run python run_app.py` or `uv run streamlit run src/clippertv/app.py`
- Install dev: `uv sync`
- Run tests: `pytest tests/` (future)
- Run single test: `uv run pytest tests/path_to_test.py::test_function_name` (future)
- Format code: `uv run black src/ tests/`
- Type check: `uv run mypy src/`

### Turso Commands
- Migrate from Supabase backup: `uv run python -m clippertv.data.migrate_to_turso [backup_file]`
- Dry run migration: `uv run python -m clippertv.data.migrate_to_turso --dry-run`
- Toggle storage backend: `CLIPPERTV_STORAGE=turso uv run python run_app.py`
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
