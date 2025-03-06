# ClipperTV Development Guide

## Commands
- Run app: `python run_app.py` or `streamlit run src/clippertv/app.py`
- Install dev: `pip install -e .`
- Run tests: `pytest tests/` (future)
- Run single test: `pytest tests/path_to_test.py::test_function_name` (future)
- Format code: `black src/ tests/`
- Type check: `mypy src/`

### Supabase Commands
- Check Supabase setup: `python -m clippertv.data.supabase_info`
- Show Supabase setup instructions: `python -m clippertv.data.migrate_to_supabase --setup-only`
- Migrate data to Supabase: `python -m clippertv.data.migrate_to_supabase`
- Toggle storage backend: `CLIPPERTV_STORAGE=supabase python run_app.py`

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
  - `store.py`: Google Cloud Storage implementation
  - `supabase_store.py`: Supabase implementation
  - `factory.py`: Data store factory (selects appropriate implementation)
  - `migrate_to_supabase.py`: Migration tool
- PDF processing in `pdf/` module
- Visualization components in `viz/` module
- Main app in `app.py`

## Data Storage
- **Google Cloud Storage**: Original implementation
  - CSV files stored in GCS bucket
  - Each rider has dedicated CSV file
  - Configured via Streamlit secrets
- **Supabase**: New implementation
  - PostgreSQL database with REST API
  - Relational model: Riders, Transit Modes, Trips
  - Configured via environment variables or Streamlit secrets
  - Migration script for transferring data from GCS