#!/usr/bin/env python3

import json
import sys

import camelot
import numpy as np
import pandas as pd
import PyPDF2
import streamlit as st

from analyze_trips import load_data

def get_trips(filename):
    # read first page
    tables = camelot.read_pdf(filename,
                 pages='1',
                 flavor='stream',
                 table_areas=['0,500,800,100'])

    df_import = tables[0].df
    df_import.columns = df_import.iloc[0].str.title()
    df_import = df_import[1:]
    
    # check if more than one page
    with open(filename, 'rb') as file:
        reader = PyPDF2.PdfFileReader(file)
        pages = reader.numPages

    # read next pages if they exist
    if pages > 1:
        tables = camelot.read_pdf(filename,
                                pages='2-end',
                                flavor='stream',
                                table_areas=['0,560,800,90'])

        for i in range(len(tables)):
            next_page = tables[i].df
            next_page.columns = next_page.iloc[0].str.title()
            next_page = next_page[1:]
            df_import = pd.concat([df_import, next_page])
            # camelot.plot(tables[i], kind='contour').show() # to check table_areas 

    # clean up
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
    
def save_to_gcs(df):
    df.to_csv('gcs://clippertv_data/data_k.csv',
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