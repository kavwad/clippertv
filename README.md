# ClipperTV

Transit usage dashboard with multi-user authentication. Track Clipper card activity, visualize spending patterns, and get automated monthly reports.

## Features

- **Multi-user authentication** with JWT tokens
- **Encrypted credential storage** for automated PDF downloads
- **Upload and process** Clipper card activity PDFs
- **Manual trip entry** for missing transactions
- **Interactive visualizations** of transit usage and costs
- **Turso database** with row-level security

## Quick Start

```bash
# Install dependencies
uv sync

# Run database migration
uv run python migrations/run_migration.py

# Validate environment setup
uv run python scripts/test_env.py

# Start the app
uv run streamlit run src/clippertv/app.py
```

## Project Structure

```
clippertv/
├── src/clippertv/
│   ├── app.py              # Main Streamlit app
│   ├── auth/               # Authentication (JWT, encryption)
│   ├── data/               # Data models and storage
│   ├── pdf/                # PDF extraction and processing
│   ├── viz/                # Charts and dashboard components
│   └── scheduler/          # Automated PDF ingestion
├── migrations/             # Database migrations
├── tests/                  # Test suite
└── .env                    # Environment configuration
```

## Development

See [PLAN.md](PLAN.md) for migration roadmap and [CLAUDE.md](CLAUDE.md) for development guidelines.

**Run tests:**
```bash
uv run pytest tests/test_auth.py -v
uv run pytest tests/test_user_store.py -v
```

**Environment:** Configured via `.env` file (see `.env.example`)
