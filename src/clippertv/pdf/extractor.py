"""PDF extraction functions for ClipperTV."""

from io import BytesIO
import numpy as np
import pandas as pd
import camelot

from clippertv.config import config


def read_pdf_section(filename, pages, table_areas):
    """Read a section of a PDF file using camelot."""
    tables = camelot.read_pdf(
        filename,
        pages=pages,
        flavor='stream',
        row_tol=15,
        table_areas=table_areas
    )
    
    # Return empty DataFrame if no tables found
    if not tables:
        return pd.DataFrame()
    
    # Process each table
    dfs = []
    for table in tables:
        df = table.df
        
        # Use first row as column headers
        df.columns = df.iloc[0].str.title()
        df.drop(df.index[0], inplace=True)
        dfs.append(df)
    
    # Combine all tables
    return pd.concat(dfs) if dfs else pd.DataFrame()


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
    
    # Clean up the DataFrame
    return df_import.reset_index(drop=True).replace('', np.nan)


def clean_up_extracted_data(df_import):
    """Clean up and format extracted PDF data."""
    # Convert date strings to datetime
    df_import['Transaction Date'] = pd.to_datetime(
        df_import['Transaction Date'], 
        format='%m-%d-%Y %I:%M %p'
    )
    
    # Convert currency columns to float
    for col in ['Debit', 'Credit', 'Balance']:
        if col in df_import.columns and df_import[col].any():
            df_import[col] = df_import[col].str.replace('$', '').astype(float)
    
    return df_import
