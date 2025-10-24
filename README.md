# ClipperTV

ClipperTV is a Streamlit-based dashboard for visualizing Clipper card transit data. It provides insights into transit usage patterns, costs, and trends.

## Features

- Upload and process Clipper card activity PDFs
- Manually add transit trips
- View monthly and yearly transit statistics
- Compare transit usage between riders
- Visualize transit usage with interactive charts
- Store data in Turso (default) or Supabase

## Project Structure

```
clippertv/
├── src/
│   └── clippertv/
│       ├── app.py         # Main Streamlit app
│       ├── config.py      # Configuration management
│       ├── data/
│       │   ├── factory.py        # Data store factory
│       │   ├── migrate_to_turso.py # Supabase → Turso migration
│       │   ├── models.py         # Data models
│       │   ├── schema.py         # Database schema
│       │   ├── store.py          # Legacy GCS data storage
│       │   ├── turso_client.py   # Turso connection helpers
│       │   └── turso_store.py    # Turso data storage
│       ├── pdf/
│       │   ├── extractor.py   # PDF extraction logic
│       │   └── processor.py   # Processing logic
│       └── viz/
│           ├── charts.py      # Chart creation
│           └── dashboard.py   # Dashboard components
└── tests/
```

## Installation

1. Clone the repository
2. Install dependencies with [uv](https://github.com/astral-sh/uv)
3. Set required secrets in `.streamlit/secrets.toml`

## Supabase Integration

ClipperTV can still read from Supabase snapshots when needed.

To use Supabase:

1. Create a Supabase project at https://supabase.com
2. Set your Supabase URL and API key in the environment or secrets
3. Set `CLIPPERTV_STORAGE=supabase` to use Supabase instead of Turso
4. Run the migration script to transfer existing data:

```bash
uv run python -m clippertv.data.migrate_to_turso supabase_export.backup
```

## Usage

Run the application with:

```bash
uv run streamlit run src/clippertv/app.py
```
