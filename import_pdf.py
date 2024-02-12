#!/usr/bin/env python3

from io import BytesIO
import json
import sys

import camelot
import numpy as np
import pandas as pd
import paramiko
import streamlit as st

from analyze_trips import load_data

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def read_pdf_section(filename, pages, table_areas):
    tables = camelot.read_pdf(filename,
                            pages=pages,
                            flavor='stream',
                            table_areas=table_areas)
    # [camelot.plot(tables[table], kind='contour').show() for table in tables] # to check table_areas 
    dfs = [table.df for table in tables]
    for df in dfs:
        df.columns = df.iloc[0].str.title()
        df.drop(df.index[0], inplace=True)
    return pd.concat(dfs) if tables else None

def get_trips(filename):
    df_import = read_pdf_section(filename, '1', ['0,500,800,100']) # first page
    df_import = pd.concat([df_import, read_pdf_section(filename, '2-end', ['0,560,800,90'])])
    return df_import.reset_index(drop=True).replace('', np.nan)

def categorize(df_import):
       df_import.loc[df_import['Location'] == 'ACT bus', 'Category'] = 'AC Transit'
       df_import.loc[df_import['Transaction Type'] == 'Dual-tag entry transaction, no fare deduction', 'Category'] = 'BART Entrance'
       df_import.loc[df_import['Transaction Type'] == 'Dual-tag exit transaction, fare payment', 'Category'] = 'BART Exit'
       df_import.loc[df_import['Route'] == 'CC60', 'Category'] = 'Cable Car'
       df_import.loc[(df_import['Transaction Type'] == 'Dual-tag entry transaction, maximum fare deducted (purse debit)') &
              (df_import['Route'].isna()), 'Category'] = 'Caltrain Entrance'
       df_import.loc[(df_import['Transaction Type'] == 'Dual-tag exit transaction, fare adjustment (purse rebate)') &
              (df_import['Route'].isna()), 'Category'] = 'Caltrain Exit'
       df_import.loc[(df_import['Transaction Type'] == 'Dual-tag entry transaction, maximum fare deducted (purse debit)') &
              (df_import['Route'] == 'FERRY'), 'Category'] = 'Ferry Entrance'
       df_import.loc[df_import['Location'].str[-5:] == '(GGF)', 'Category'] = 'Ferry Entrance'
       df_import.loc[(df_import['Transaction Type'] == 'Dual-tag exit transaction, fare adjustment (purse rebate)') &
              (df_import['Route'] == 'FERRY'), 'Category'] = 'Ferry Exit'
       df_import.loc[df_import['Location'] == 'SFM bus', 'Category'] = 'Muni Bus'
       df_import.loc[df_import['Route'] == 'NONE', 'Category'] = 'Muni Metro'
       df_import.loc[df_import['Location'] == 'SAM bus', 'Category'] = 'SamTrans'
       df_import.loc[(df_import['Transaction Type'] == 'Threshold auto-load at a TransLink Device') |
              (df_import['Transaction Type'] == 'Add value at TOT or TVM'), 'Category'] = 'Reload'

       return df_import

def check_category(df_import):
    if df_import['Category'].isna().any():
        raise ValueError('Some transactions are not categorized')

def clean_up(df_import):
    df_import['Transaction Date'] = pd.to_datetime(df_import['Transaction Date'])
    
    for col in ['Debit', 'Credit', 'Balance']:
        if df_import[col].any():
            df_import[col] = df_import[col].str.replace('$', '').astype(float)
    
    return df_import

def add_trips_to_database(df, df_import):
    df = pd.concat([df, df_import]).sort_values('Transaction Date', ascending=False).reset_index(drop=True)
    return df
    
def upload_pdf(pdf, filename):
    ssh.connect(hostname=st.secrets['connections']['ccrma']['hostname'],
                username=st.secrets['connections']['ccrma']['username'],
                password=st.secrets['connections']['ccrma']['password'])
    sftp = ssh.open_sftp()
    sftp.putfo(BytesIO(pdf.read()), st.secrets['connections']['ccrma']['filepath']
               + filename)
    sftp.close()
    ssh.close()
    
def save_to_gcs(rider, df):
    df.to_csv('gcs://clippertv_data/data_' + rider.lower() + '.csv',
                                index=False,
                                storage_options={'token':
                                                json.loads(st.secrets['gcs_key'])})

def main():
    filename = sys.argv[1]

    df = load_data()
    df_import = get_trips(filename)
    df_import = categorize(clean_up(df_import))
    check_category(df_import)
    df = add_trips_to_database(df, df_import)
    save_to_gcs(df)

if __name__ == '__main__':
    main()