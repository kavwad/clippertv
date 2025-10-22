"""PDF extraction functions for ClipperTV."""

from io import BytesIO
import numpy as np
import pandas as pd
import camelot

from clippertv.config import config


def _is_valid_table(df: pd.DataFrame) -> bool:
    """Heuristic to determine if a Camelot extraction produced usable headers."""
    headers = pd.Index(df.columns).astype(str).str.lower().tolist()
    return any("transaction" in h or "txn" in h for h in headers)


def read_pdf_section(filename, pages, table_areas):
    """Read a section of a PDF file using camelot with graceful fallback."""
    attempts = [table_areas, None] if table_areas else [None]
    for areas in attempts:
        try:
            tables = camelot.read_pdf(
                filename,
                pages=pages,
                flavor="stream",
                row_tol=15,
                table_areas=areas,
            )
        except Exception:
            continue

        if not tables:
            continue

        dfs = []
        for table in tables:
            df = table.df
            if df.empty:
                continue
            df.columns = (
                df.iloc[0]
                .astype(str)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
                .str.title()
            )
            df = df.drop(df.index[0])
            dfs.append(df)

        if not dfs:
            continue

        combined = pd.concat(dfs)
        if _is_valid_table(combined):
            return combined

    return pd.DataFrame()


def extract_trips_from_pdf(filename):
    """Extract trip data from a Clipper PDF statement."""
    # Extract first page with different table area
    df_first_page = read_pdf_section(
        filename,
        '1',
        config.pdf_table_areas_first_page
    )

    # Extract remaining pages
    df_other_pages = read_pdf_section(
        filename,
        '2-end',
        config.pdf_table_areas_other_pages
    )

    # Combine all pages
    df_import = pd.concat([df_first_page, df_other_pages])

    # Clean up the DataFrame - replace empty strings with NaN
    df_import = df_import.reset_index(drop=True)
    # Use mask to avoid FutureWarning about downcasting
    df_import = df_import.mask(df_import == '')
    return df_import


def clean_up_extracted_data(df_import):
    """Clean up and format extracted PDF data."""
    # Return empty dataframe if input is empty
    if df_import.empty:
        return df_import

    rename_map = {
        'Transaction Date Time': 'Transaction Date',
        'Txn Date Time': 'Transaction Date',
        'Txn Date': 'Transaction Date',
        'Transaction  Date': 'Transaction Date',
        'Transaction Date ': 'Transaction Date',
        'Transaction\nDate': 'Transaction Date',
        'Txn Date \nTime': 'Transaction Date',
        'Txn Type': 'Transaction Type',
        'Txn Value': 'Debit',
        'Txn \nValue': 'Debit',
        'Remaining Value': 'Balance',
        'Remaining \nValue': 'Balance',
    }

    # Normalize column labels before renaming
    normalized_columns = (
        pd.Index(df_import.columns)
        .astype(str)
        .str.replace("\n", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.title()
    )
    df_import.columns = normalized_columns

    df_import = df_import.rename(columns=rename_map)

    expected_cols = [
        'Transaction Date',
        'Transaction Type',
        'Location',
        'Route',
        'Product',
        'Debit',
        'Credit',
        'Balance',
    ]
    if 'Transaction Date' not in df_import.columns:
        return pd.DataFrame(columns=expected_cols)

    if 'Transaction Date' in df_import.columns:
        df_import['Transaction Date'] = (
            df_import['Transaction Date']
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
        )

    # Convert date strings to datetime
    df_import['Transaction Date'] = pd.to_datetime(
        df_import['Transaction Date'],
        format='%m-%d-%Y %I:%M %p',
        errors='coerce'
    )

    # Convert currency columns to float
    for col in ['Debit', 'Credit', 'Balance']:
        if col in df_import.columns:
            # Check if column has any non-null values before processing
            if df_import[col].notna().any():
                df_import[col] = df_import[col].str.replace('$', '', regex=False).astype(float)

        if col in df_import.columns:
            df_import[col] = (
                df_import[col]
                .astype(str)
                .str.replace('$', '', regex=False)
                .str.replace(',', '', regex=False)
                .str.strip()
            )
            df_import[col] = pd.to_numeric(df_import[col], errors='coerce')
    
    return df_import
