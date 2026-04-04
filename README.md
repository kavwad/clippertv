# ClipperTV

Transit dashboard for Bay Area Clipper card riders. Download your transaction history, visualize spending patterns, and compare usage across cards.

## Features

- **CSV ingestion** from clippercard.com API with automatic categorization
- **Interactive dashboard** with Chart.js visualizations and HTMX interactions
- **Multi-user auth** with per-user Clipper card management
- **Scheduled ingestion** via launchd or CLI

## Quick Start

```bash
# Install
uv sync --extra web

# Set up environment
cp .env.example .env  # then fill in values

# Run dashboard
uv run uvicorn clippertv.web.main:app --reload --host 0.0.0.0

# Download and ingest transactions
clipper-download --last-month --ingest

# Scheduled ingestion (all accounts, last 30 days)
uv run clippertv-ingest --days 30 -v
```

## Project Structure

```
clippertv/
├── src/clippertv/
│   ├── ingest/            # CSV download, parsing, storage
│   ├── data/              # Models, Turso storage, DB client, user store
│   ├── auth/              # JWT auth, credential encryption
│   ├── analytics/         # Pass costs, categories, comparison, summary
│   ├── scheduler/         # Platform-agnostic ingestion runner
│   ├── web/               # FastAPI app, auth middleware, routes, templates
│   └── config.py          # App and environment config
├── migrations/            # SQL and Python database migrations
├── scheduler/             # launchd plist + shell wrapper
├── tests/                 # Test suite
└── .env                   # Environment configuration
```

## Development

See [CLAUDE.md](CLAUDE.md) for development guidelines, commands, and architecture details.

```bash
uv run pytest              # Run tests
```
