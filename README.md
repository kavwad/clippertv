# ClipperTV

Transit dashboard for Bay Area Clipper card riders. Download your transaction history, visualize spending patterns, and compare usage across cards.

## Features

- **CSV ingestion** from clippercard.com API with automatic categorization
- **Interactive dashboard** with
- **Multi-rider support**

## Quick Start

```bash
# Install
uv sync --extra web

# Set up environment
cp .env.example .env  # then fill in values
uv run python scripts/test_env.py

# Download and ingest transactions
clipper-download --last-month --ingest

# Run dashboard
uv run uvicorn clippertv.web.main:app --reload --host 0.0.0.0
```

## Project Structure

```
clippertv/
├── src/clippertv/
│   ├── ingest/            # CSV download, parsing, categorization
│   ├── data/              # Models, Turso storage, DB client
│   ├── auth/              # JWT auth, credential encryption
│   ├── viz/               # Data processing for dashboard
│   ├── web/               # FastAPI routes + Chart.js templates
│   └── config.py          # App and environment config
├── migrations/            # Database migrations
├── tests/                 # Test suite
└── .env                   # Environment configuration
```

## Development

See [CLAUDE.md](CLAUDE.md) for development guidelines, commands, and architecture details.

```bash
uv run pytest              # Run tests
```
