#!/usr/bin/env python3

import datetime
import pandas as pd
import streamlit as st
import time

from analyze_trips import load_data, process_data, create_charts
from import_pdf import get_trips, categorize, clean_up, check_category, add_trips_to_database, upload_pdf, save_to_gcs

DISP_CATEGORIES = ['Muni Bus', 'Muni Metro', 'BART', 'Cable Car',
                   'Caltrain', 'Ferry', 'AC Transit', 'SamTrans']

SUBMIT_CATEGORIES = {'Muni Bus': 'Muni Bus', 'Muni Metro': 'Muni Metro',
                     'BART': 'BART Entrance', 'Cable Car': 'Cable Car',
                     'Caltrain': 'Caltrain Entrance', 'Ferry': 'Ferry Entrance',
                     'AC Transit': 'AC Transit', 'SamTrans': 'SamTrans'}

COLUMN_CONFIG = {
    'Year': st.column_config.NumberColumn(format="%d", width=75),
    'Month': st.column_config.DateColumn(format="MMM YYYY", width=75),
    'Muni Bus': st.column_config.NumberColumn(format="$%d"),
    'Muni Metro': st.column_config.NumberColumn(format="$%d"),
    'BART': st.column_config.NumberColumn(format="$%d"),
    'Cable Car': st.column_config.NumberColumn(format="$%d"),
    'Caltrain': st.column_config.NumberColumn(format="$%d"),
    'Ferry': st.column_config.NumberColumn(format="$%d"),
    'AC Transit': st.column_config.NumberColumn(format="$%d"),
    'SamTrans': st.column_config.NumberColumn(format="$%d"),
 }

# Set up the page
st.set_page_config(page_title="ClipperTV", layout='wide')

# Set up title and rider chooser
riders = ['B', 'K']
st.session_state.rider = st.radio('Choose your rider',
                                  riders,
                                  horizontal=True,
                                  label_visibility='hidden')
st.title('Welcome to Clipper TV!', anchor=False)

# Load and process data
df = load_data(st.session_state.rider)
pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers = process_data(df)
trip_chart, cost_chart, bike_walk_chart, comparison_chart = create_charts(pivot_month, pivot_month_cost, riders)

# Caculate summary stats summary
trips_this_month = pivot_month.iloc[0].sum()
cost_this_month = pivot_month_cost.iloc[0].sum().round().astype(int)

trip_diff = pivot_month.iloc[1].sum() - pivot_month.iloc[0].sum()
trip_diff_text = "fewer" if trip_diff >= 0 else "more"

cost_diff = (pivot_month_cost.iloc[1].sum()
             - pivot_month_cost.iloc[0].sum()).round().astype(int)
cost_diff_text = "less" if cost_diff >= 0 else "more"

most_recent_date = df['Transaction Date'].max()
this_month = df[((df['Transaction Date'].dt.year == most_recent_date.year)
                        & (df['Transaction Date'].dt.month == most_recent_date.month))]

if 'Caltrain Adult 3 Zone Monthly Pass' in this_month['Product'].values:
    pass_rides = this_month[(this_month['Category'].str.contains('Caltrain')).fillna(False)
                                   & (this_month['Transaction Type'] == 'Manual entry')]

    pass_savings = - len(pass_rides) * 7.70
    pass_cost = 184.80
    additional_caltrain_cost = this_month[(this_month['Category'].str.contains('Caltrain')).fillna(False)][['Debit', 'Credit']].sum()
    additional_caltrain_cost = additional_caltrain_cost['Debit'] - additional_caltrain_cost['Credit']
    
    pass_upshot = (pass_savings + pass_cost + additional_caltrain_cost).round(0).astype(int)
else:
    pass_upshot = None

# Create formatted strings
f"#### {st.session_state.rider} took **:red[{trips_this_month}]** trips in\
    {pivot_month.index[0].strftime('%B')}, which cost\
    **:red[${cost_this_month}]**."

f"{st.session_state.rider} rode **{pivot_month.iloc[0].idxmax()}** most, at\
    **{pivot_month.iloc[0][pivot_month.iloc[0].idxmax()]}** times.\
    Altogether, {st.session_state.rider} took {abs(trip_diff)} {trip_diff_text} trips and paid\
        ${abs(cost_diff)} {cost_diff_text} than the previous month."

if pass_upshot:
    if pass_upshot < 0:
        f"This month, {st.session_state.rider} saved **${-pass_upshot}** with a Caltrain pass."
    elif pass_upshot > 0:
        f"This month, {st.session_state.rider} spent an extra **${pass_upshot}** by getting a Caltrain pass (!!)."
    else: 
        f"This month, {st.session_state.rider} broke even with a Caltrain pass."

if pivot_month.index[0].strftime('%B') != 'January':
    f"This year, {st.session_state.rider} has taken **{pivot_year.iloc[0].sum()}** trips,\
        costing **${pivot_year_cost.iloc[0].sum().round().astype(int)}**."

# f"Since 2021,{st.session_state.rider} has gotten **{free_xfers}** free transfers!"

# Display charts
st.plotly_chart(trip_chart, use_container_width=True)
st.plotly_chart(cost_chart, use_container_width=True)

# Set up tabs
annual_tab, monthly_tab, bike_walk_tab, comparison_tab = st.tabs(['Annual stats',
                                                                  'Monthly stats',
                                                                  'Active transportation',
                                                                  'Tête-à-tête'])

# Display tables
with annual_tab:
    st.subheader('Annual trips by mode', anchor=False)
    st.dataframe(pivot_year,
                 use_container_width=True,
                 column_config={'Year':
                                st.column_config.NumberColumn(format="%d",
                                                              width=75)})
    st.subheader('Annual trip cost by mode', anchor=False)
    st.dataframe(pivot_year_cost,
                 use_container_width=True,
                 column_config=COLUMN_CONFIG)

with monthly_tab:
    st.subheader('Monthly trips by mode', anchor=False)
    st.dataframe(pivot_month,
                 use_container_width=True,
                 column_config={'Month':
                                st.column_config.DateColumn(format="MMM YYYY",
                                                            width=75)})
    st.subheader('Monthly trip cost by mode', anchor=False)
    st.dataframe(pivot_month_cost,
                 use_container_width=True,
                 column_config=COLUMN_CONFIG)

with bike_walk_tab:
    if st.session_state.rider == 'K':
        # st.plotly_chart(bike_walk_chart, use_container_width=True)
        st.write('Coming soon!')
    else:
        st.write('Coming soon!')

with comparison_tab:
    st.plotly_chart(comparison_chart, use_container_width=True)


st.divider()
with st.expander('Add trips'):
    password = st.text_input('Enter password', type='password')
    if password == st.secrets['password']:
        import_tab, manual_tab = st.tabs(['Import from pdf', 'Add manually'])

        with import_tab:
            pdfs = st.file_uploader('Upload Clipper activity pdf',
                                    type='pdf',
                                    accept_multiple_files=True,
                                    label_visibility='collapsed')

            if pdfs:  # submit appears only after upload
                st.session_state.filenames = []
                df_import = None

                if st.button('Process all'):
                    progress_bar = st.progress(0, 'Uploading PDFs')

                    for index, pdf in enumerate(pdfs):
                        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M')}_{index+1}.pdf"
                        upload_pdf(pdf, filename)
                        progress_bar.progress(
                            (index + 1) / len(pdfs), 'Uploading PDFs')
                        st.session_state.filenames.append(filename)

                    for filename in st.session_state.filenames:
                        filepath = st.secrets['connections']['ccrma']['filepath_web'] + filename
                        df_import = categorize(clean_up(get_trips(filepath)))
                        check_category(df_import)
                        st.session_state.df_import_all = add_trips_to_database(df, df_import)

                    progress_bar.empty()

                    st.write(st.session_state.df_import_all)
                
                if st.button('Submit all', key='import_submit', type='primary'):
                    save_to_gcs(st.session_state.rider,
                                st.session_state.df_import_all)
                    st.success(f'Uploaded!', icon='🚍')
                    time.sleep(3)
                    st.rerun()

        with manual_tab:
            col1, col2, col3 = st.columns(3)
            with col1:
                transaction_date = st.date_input('Date:', format='MM/DD/YYYY')
            with col2:
                category = st.selectbox('Mode:', options=DISP_CATEGORIES + ['Caltrain Pass'])
            with col3:
                rides = st.number_input('Rides:', min_value=1, step=1)

            if 'new_rows' not in st.session_state:
                st.session_state.new_rows = pd.DataFrame(columns=['Transaction Date',
                                                                'Transaction Type',
                                                                'Category'])

            if st.button('Add ride(s)'):
                for i in range(rides):
                    if category == 'Caltrain Pass':
                        new_row = pd.DataFrame({
                            'Transaction Date': [pd.Timestamp(transaction_date)],
                            'Transaction Type': ['Manual entry'],
                            'Product': 'Caltrain Adult 3 Zone Monthly Pass',
                            'Credit': 184.80,
                            'Category': ['Reload']
                        })
                    else:
                        new_row = pd.DataFrame({
                            'Transaction Date': [pd.Timestamp(transaction_date)],
                            'Transaction Type': ['Manual entry'],
                            'Category': [SUBMIT_CATEGORIES[category]]
                        })
                    st.session_state.new_rows = pd.concat(
                        [st.session_state.new_rows, new_row])

            # Display new_rows and submit button
            if not st.session_state.new_rows.empty:
                with st.container(border=True):
                    st.error('for K & B use only!', icon='🚨')

                    st.data_editor(st.session_state.new_rows,
                                column_config={
                                    '_index': None,
                                    'Transaction Date': st.column_config.DateColumn(
                                        label='Date',
                                        format='MM/DD/YYYY'),
                                    'Transaction Type': None,
                                    'Category': 'Mode'})

                    # Undo button
                    if st.button('Remove last ride'):
                        st.session_state.new_rows = st.session_state.new_rows.iloc[:-1]

                    # Submit button
                    if st.button('Submit all', key='manual_submit', type='primary'):
                        df = (pd.concat([df, st.session_state.new_rows]).
                            sort_values('Transaction Date', ascending=False).
                            reset_index)(drop=True)

                        save_to_gcs(st.session_state.rider, df)

                        st.session_state.new_rows = pd.DataFrame(columns=['Transaction Date',
                                                                        'Transaction Type',
                                                                        'Category'])

                        st.rerun()
