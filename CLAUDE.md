# ClipperTV Development Guide

## Commands
- Run app: `python run_app.py` or `streamlit run src/clippertv/app.py`
- Install dev: `pip install -e .`
- Run tests: `pytest tests/` (future)
- Run single test: `pytest tests/path_to_test.py::test_function_name` (future)
- Format code: `black src/ tests/`
- Type check: `mypy src/`

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
- PDF processing in `pdf/` module
- Visualization components in `viz/` module
- Main app in `app.py`