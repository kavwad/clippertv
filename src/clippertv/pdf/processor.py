"""PDF processing functions for ClipperTV."""

import datetime
from io import BytesIO
import json
from typing import Optional, List

import pandas as pd
import paramiko
import streamlit as st

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


def upload_pdf_to_ccrma(pdf_file, filename):
    """Upload PDF file to CCRMA server."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect to CCRMA server
        ssh.connect(
            hostname=st.secrets['connections']['ccrma']['hostname'],
            username=st.secrets['connections']['ccrma']['username'],
            password=st.secrets['connections']['ccrma']['password']
        )
        
        # Open SFTP connection and upload file
        sftp = ssh.open_sftp()
        sftp.putfo(
            BytesIO(pdf_file.read()),
            st.secrets['connections']['ccrma']['filepath'] + filename
        )
        
        sftp.close()
        return True
    except Exception as e:
        # Log the error (future enhancement)
        return False
    finally:
        ssh.close()


def process_pdf_statements(pdf_files, rider_id):
    """Process multiple PDF statements and add to database."""
    if not pdf_files:
        return None
    
    # Create combined DataFrame for all imported transactions
    combined_df = None
    filenames = []
    
    # Process each PDF file
    for index, pdf_file in enumerate(pdf_files):
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"{timestamp}_{index+1}.pdf"
        
        # Upload PDF to CCRMA server
        upload_success = upload_pdf_to_ccrma(pdf_file, filename)
        if not upload_success:
            continue
        
        filenames.append(filename)
        
        # Get filepath on CCRMA server
        filepath = st.secrets['connections']['ccrma']['filepath_web'] + filename
        
        # Extract and process data
        df_import = extract_trips_from_pdf(filepath)
        df_import = clean_up_extracted_data(df_import)
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
    rider_df = data_store.load_data(rider_id)
    updated_df = data_store.add_transactions(rider_id, combined_df)

    return updated_df
