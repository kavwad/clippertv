# ClipperTV

ClipperTV is a Streamlit-based dashboard for visualizing Clipper card transit data. It provides insights into transit usage patterns, costs, and trends.

## Features

- Upload and process Clipper card activity PDFs
- Manually add transit trips
- View monthly and yearly transit statistics
- Compare transit usage between riders
- Visualize transit usage with interactive charts

## Project Structure

```
clippertv/
├── src/
│   └── clippertv/
│       ├── app.py         # Main Streamlit app
│       ├── config.py      # Configuration management
│       ├── data/
│       │   ├── models.py  # Data models
│       │   ├── store.py   # Data access layer
│       │   └── schema.py  # Database schema
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

The application requires configuration for:
- Google Cloud Storage access for data storage
- CCRMA server access for PDF processing
- Password protection for adding trips

Store your credentials in `.streamlit/secrets.toml`.
