"""PDF processing functions for ClipperTV."""

import datetime
import os
import re
import shutil
import sys
from pathlib import Path
from typing import IO, Optional, Union, Iterable, List

import pandas as pd

from clippertv.config import config
from clippertv.data.factory import get_data_store
from clippertv.pdf.categories import SORTED_CATEGORIZATION_RULES
from clippertv.pdf.extractor import extract_trips_from_pdf, clean_up_extracted_data


def categorize_trips(df_import: pd.DataFrame) -> pd.DataFrame:
    """Categorize trips using declarative regex-driven rules."""
    df_import['Category'] = None
    uncategorized_mask = df_import['Category'].isna()

    for rule in SORTED_CATEGORIZATION_RULES:
        if not uncategorized_mask.any():
            break

        matches = rule.build_mask(df_import)
        applicable = matches & uncategorized_mask
        if applicable.any():
            df_import.loc[applicable, 'Category'] = rule.category
            uncategorized_mask = df_import['Category'].isna()

    return df_import


def validate_categories(df_import):
    """Check if all transactions are categorized."""
    uncategorized = df_import['Category'].isna().sum()
    if uncategorized > 0:
        # For future: log this information or raise warning
        return False
    return True


PDFSource = Union[str, os.PathLike, IO[bytes]]


def _sanitize_name(name: str) -> str:
    """Return a filesystem-safe stem derived from the provided name."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return stem or "clipper-statement"


def _persist_pdf(source: PDFSource, destination_dir: Path, suffix: str) -> Path:
    """Persist a PDF to the local cache directory and return its path."""
    destination_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(source, (str, os.PathLike)):
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"PDF source does not exist: {source_path}")
        stem = _sanitize_name(source_path.stem)
        destination = destination_dir / f"{stem}-{suffix}.pdf"
        if source_path.resolve() == destination.resolve():
            data = destination.read_bytes()
        else:
            shutil.copy2(source_path, destination)
            data = destination.read_bytes()
    else:
        name = getattr(source, "name", "clipper-statement")
        stem = _sanitize_name(Path(name).stem)
        destination = destination_dir / f"{stem}-{suffix}.pdf"
        data = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
        if not data:
            raise ValueError(f"PDF '{name}' is empty")
        destination.write_bytes(data)

    if not data.startswith(b"%PDF"):
        destination.unlink(missing_ok=True)
        raise ValueError(f"Invalid PDF content saved to {destination}")

    return destination


def process_pdf_statements(pdf_files: Iterable[PDFSource], rider_id: str):
    """Process multiple PDF statements and add to database."""
    pdf_list = list(pdf_files)
    if not pdf_list:
        return None
    
    # Create combined DataFrame for all imported transactions
    combined_df = None
    storage_dir = Path(config.pdf_local_cache_dir)
    
    # Process each PDF file
    for index, pdf_file in enumerate(pdf_list):
        print(f"[{index+1}/{len(pdf_list)}] Processing PDF...", file=sys.stderr)

        # Generate unique filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = f"{timestamp}-{index+1}"
        print(f"  Persisting PDF to cache...", file=sys.stderr)
        pdf_path = _persist_pdf(pdf_file, storage_dir, suffix)

        # Extract and process data
        try:
            print(f"  Extracting data from {pdf_path.name}...", file=sys.stderr)
            df_import = extract_trips_from_pdf(str(pdf_path))
            print(f"  Extracted {len(df_import)} rows", file=sys.stderr)
        except Exception as exc:
            print(f"  Failed to extract data from {pdf_path}: {exc}", file=sys.stderr)
            continue

        print(f"  Cleaning data...", file=sys.stderr)
        df_import = clean_up_extracted_data(df_import)

        print(f"  Converting timestamps...", file=sys.stderr)
        df_import['Transaction Date'] = (
            pd.to_datetime(df_import['Transaction Date'], utc=True)
            .dt.tz_convert(None)
        )

        print(f"  Categorizing trips...", file=sys.stderr)
        df_import = categorize_trips(df_import)

        # Validate categories
        print(f"  Validating categories...", file=sys.stderr)
        validate_categories(df_import)

        # Add to combined DataFrame
        print(f"  Combining with previous data...", file=sys.stderr)
        if combined_df is None:
            combined_df = df_import
        else:
            # Use outer join to handle any missing columns
            combined_df = pd.concat([combined_df, df_import], ignore_index=True, join='outer')
    
    # If no data was successfully imported, return None
    if combined_df is None or combined_df.empty:
        print("  No data was successfully imported", file=sys.stderr)
        return None

    # Add the imported data to the database
    print(f"\nSaving {len(combined_df)} transactions to database...", file=sys.stderr)
    data_store = get_data_store()
    updated_df = data_store.add_transactions(rider_id, combined_df)
    print(f"Database updated successfully!", file=sys.stderr)

    return updated_df
