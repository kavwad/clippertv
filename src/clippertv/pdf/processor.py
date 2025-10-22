"""PDF processing functions for ClipperTV."""

import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import IO, Optional, Union, Iterable, List

import pandas as pd

from clippertv.config import config
from clippertv.data.factory import get_data_store
from clippertv.pdf.extractor import extract_trips_from_pdf, clean_up_extracted_data


def categorize_trips(df_import):
    """Categorize trips based on transaction type and location."""
    # AC Transit
    df_import.loc[df_import['Location'] == 'ACT bus', 'Category'] = 'AC Transit'
    
    # BART
    df_import.loc[
        df_import['Transaction Type'] == 'Dual-tag entry transaction, no fare deduction', 
        'Category'
    ] = 'BART Entrance'
    
    df_import.loc[
        df_import['Transaction Type'] == 'Dual-tag exit transaction, fare payment', 
        'Category'
    ] = 'BART Exit'
    
    # Cable Car
    df_import.loc[df_import['Route'] == 'CC60', 'Category'] = 'Cable Car'
    
    # Caltrain
    df_import.loc[
        (df_import['Transaction Type'] == 'Dual-tag entry transaction, maximum fare deducted (purse debit)') &
        (df_import['Route'].isna()), 
        'Category'
    ] = 'Caltrain Entrance'
    
    df_import.loc[
        (df_import['Transaction Type'] == 'Dual-tag exit transaction, fare adjustment (purse rebate)') &
        (df_import['Route'].isna()), 
        'Category'
    ] = 'Caltrain Exit'
    
    # Ferry
    df_import.loc[
        (df_import['Transaction Type'] == 'Dual-tag entry transaction, maximum fare deducted (purse debit)') &
        (df_import['Route'] == 'FERRY'), 
        'Category'
    ] = 'Ferry Entrance'
    
    df_import.loc[
        df_import['Location'].str[-5:] == '(GGF)', 
        'Category'
    ] = 'Ferry Entrance'
    
    df_import.loc[
        (df_import['Transaction Type'] == 'Dual-tag exit transaction, fare adjustment (purse rebate)') &
        (df_import['Route'] == 'FERRY'), 
        'Category'
    ] = 'Ferry Exit'
    
    # Muni
    df_import.loc[df_import['Location'] == 'SFM bus', 'Category'] = 'Muni Bus'
    df_import.loc[df_import['Route'] == 'NONE', 'Category'] = 'Muni Metro'
    
    # SamTrans
    df_import.loc[df_import['Location'] == 'SAM bus', 'Category'] = 'SamTrans'
    
    # Reloads
    df_import.loc[
        (df_import['Transaction Type'] == 'Threshold auto-load at a TransLink Device') |
        (df_import['Transaction Type'] == 'Add value at TOT or TVM') |
        (df_import['Transaction Type'] == 'Remote create of new pass'), 
        'Category'
    ] = 'Reload'
    
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
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = f"{timestamp}-{index+1}"
        pdf_path = _persist_pdf(pdf_file, storage_dir, suffix)
        
        # Extract and process data
        try:
            df_import = extract_trips_from_pdf(str(pdf_path))
        except Exception as exc:
            print(f"Failed to extract data from {pdf_path}: {exc}", file=sys.stderr)
            continue
        df_import = clean_up_extracted_data(df_import)
        df_import['Transaction Date'] = (
            pd.to_datetime(df_import['Transaction Date'], utc=True)
            .dt.tz_convert(None)
        )
        df_import = categorize_trips(df_import)
        
        # Validate categories
        validate_categories(df_import)
        
        # Add to combined DataFrame
        if combined_df is None:
            combined_df = df_import
        else:
            combined_df = pd.concat([combined_df, df_import])
    
    # If no data was successfully imported, return None
    if combined_df is None or combined_df.empty:
        return None
    
    # Add the imported data to the database
    data_store = get_data_store()
    updated_df = data_store.add_transactions(rider_id, combined_df)

    return updated_df
