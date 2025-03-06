# ClipperTV

ClipperTV is a Streamlit-based dashboard for visualizing Clipper card transit data. It provides insights into transit usage patterns, costs, and trends.

## Features

- Upload and process Clipper card activity PDFs
- Manually add transit trips
- View monthly and yearly transit statistics
- Compare transit usage between riders
- Visualize transit usage with interactive charts
- Store data in Supabase or Google Cloud Storage

## Project Structure

```
clippertv/
├── src/
│   └── clippertv/
│       ├── app.py         # Main Streamlit app
│       ├── config.py      # Configuration management
│       ├── data/
│       │   ├── models.py         # Data models
│       │   ├── store.py          # GCS data storage
│       │   ├── supabase_store.py # Supabase data storage
│       │   ├── factory.py        # Data store factory
│       │   ├── schema.py         # Database schema
│       │   └── migrate_to_supabase.py # Migration tool
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
2. Install the package:

```bash
pip install -e .
```

3. Configure environment:
   - Copy `.env.example` to `.env` and update with your credentials
   - For Streamlit Cloud, set up the secrets in `.streamlit/secrets.toml`

## Supabase Integration

ClipperTV now supports storing data in Supabase, a modern PostgreSQL database with a REST API. 

To use Supabase:

1. Create a Supabase project at https://supabase.com
2. Set your Supabase URL and API key in the environment or secrets
3. Set `CLIPPERTV_STORAGE=supabase` to use Supabase instead of GCS
4. Run the migration script to transfer existing data:

```bash
python -m clippertv.data.migrate_to_supabase
```

## Usage

Run the application with:

```bash
python -m streamlit run -m clippertv.app
```

or use the script entry point:

```bash
clippertv
```

## Configuration

The application can be configured with:

### Environment Variables
- `CLIPPERTV_STORAGE`: Set to `supabase` or `gcs` to choose backend
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_API_KEY`: Your Supabase API key

### Streamlit Secrets
Store the following in `.streamlit/secrets.toml`:

```toml
# For Google Cloud Storage
gcs_key = '''{ "GCS JSON credentials" }'''

# For Supabase
supabase_url = "your-project-url.supabase.co"
supabase_key = "your-supabase-api-key"

# App protection
password = "your-password-for-adding-trips"
```
