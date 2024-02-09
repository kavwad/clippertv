#!/usr/bin/env python3

import pandas as pd
import streamlit as st

from analyze_trips import create_charts, load_data, process_data
from import_pdf import get_trips, categorize, clean_up, check_category, add_trips_to_database, save_to_gcs

DISP_CATEGORIES = ['Muni Bus', 'Muni Metro', 'BART', 'Cable Car',
                   'Caltrain', 'Ferry', 'AC Transit', 'SamTrans']

SUBMIT_CATEGORIES = {'Muni Bus': 'Muni Bus', 'Muni Metro': 'Muni Metro',
                     'BART': 'BART Entrance', 'Cable Car': 'Cable Car',
                     'Caltrain': 'Caltrain Entrance', 'Ferry': 'Ferry Entrance',
                     'AC Transit': 'AC Transit', 'SamTrans': 'SamTrans'}

# Set up the page
st.set_page_config(page_title="Kaveh’s transit trips")
st.title('Kaveh’s transit trips', anchor=False)
# st.sidebar.markdown('# Kaveh')
# st.sidebar.markdown('# Bree')

# Load and process data
df = load_data()
pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers = process_data(df)
trip_chart, cost_chart = create_charts(pivot_month, pivot_month_cost)

# Display summary
trips_this_month = pivot_month.iloc[0].sum()
cost_this_month = pivot_month_cost.iloc[0].sum().round().astype(int)

trip_diff = pivot_month.iloc[1].sum() - pivot_month.iloc[0].sum()
trip_diff_text = "more" if trip_diff >= 0 else "fewer"
cost_diff = (pivot_month_cost.iloc[1].sum()
             - pivot_month_cost.iloc[0].sum()).round().astype(int)
cost_diff_text = "more" if cost_diff >= 0 else "less"

# Create formatted strings
f"#### You took **:red[{trips_this_month}]** trips in\
    {pivot_month.index[0].strftime('%B')}, which cost\
    **:red[${cost_this_month}]**."
f"You rode **{pivot_month.iloc[0].idxmax()}** most, at\
    **{pivot_month.iloc[0][pivot_month.iloc[0].idxmax()]}** times.\
    Altogether, you took {abs(trip_diff)} {trip_diff_text} trips and paid\
        ${abs(cost_diff)} {cost_diff_text} than the previous month."
f"Since 2021, you've gotten **{free_xfers}** free transfers!"

if pivot_month.iloc[0].sum() > pivot_year.iloc[0].sum():
    f"This year, he's taken **{pivot_year.iloc[0].sum()}** trips,\
        costing **${pivot_year_cost.iloc[0].sum().round().astype(int)}**."

# Display charts
st.plotly_chart(trip_chart, use_container_width=True)
st.plotly_chart(cost_chart, use_container_width=True)

# Set up tabs and tables
annual_tab, monthly_tab = st.tabs(['Annual stats', 'Monthly stats'])
column_config = {
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
                    column_config=column_config)

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
                    column_config=column_config)

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
                    column_config=column_config)

st.divider()

# Display add trips expander
with st.expander('Add trips'):
    
    import_tab, manual_tab = st.tabs(['Import from pdf', 'Add manually'])
    
    with import_tab:
        pdfs = st.file_uploader('Upload Clipper activity pdf',
                                type='pdf',
                                accept_multiple_files=True)
        
        if pdfs: # submit appears only after upload
            for pdf in pdfs:
                df_import = categorize(clean_up(get_trips(pdf.name)))
                check_category(df_import)
                st.write(pdf.name, ':', df_import)
            if st.button('Upload all'):
                for pdf in pdfs:
                    df = add_trips_to_database(df, df_import)
                if not df_import.empty:
                    st.write(df.sort_values('Transaction Date', ascending=False).reset_index(drop=True))
                    # save_to_gcs(df)
                    f':green[Uploaded len(df_import) rides!]'
    
    with manual_tab:
        # Form elements
        col1, col2, col3 = st.columns(3)
        with col1:
            transaction_date = st.date_input('Date:', format='MM/DD/YYYY')
        with col2:
            category = st.selectbox('Mode:', options=DISP_CATEGORIES)
        with col3:
            rides = st.number_input('Rides:', min_value=1, step=1)

        # Initialize new_rows in session state
        if 'new_rows' not in st.session_state:
            st.session_state.new_rows = pd.DataFrame(columns=['Transaction Date',
                                                              'Transaction Type',
                                                              'Category'])

        button_col1, button_col2 = st.columns([1,5])
        
        # Add rides button
        with button_col1:
            if st.button('Add ride(s)'):
                for i in range(rides):
                    new_row = pd.DataFrame({
                        'Transaction Date': [pd.Timestamp(transaction_date)],
                        'Transaction Type': ['Manual entry'],
                        'Category': [SUBMIT_CATEGORIES[category]]
                    })
                    st.session_state.new_rows = pd.concat([st.session_state.new_rows, new_row])
        
        # Undo button
        with button_col2:
            if st.button('Undo'):
                st.session_state.new_rows = st.session_state.new_rows.iloc[:-1]

        # Display new_rows and submit button
        if not st.session_state.new_rows.empty:
            with st.container(border=True):
                st.markdown(':rotating_light: :red[for K & B use only!] :rotating_light:')
                
                st.data_editor(st.session_state.new_rows,
                            column_config={
                                '_index': None,
                                'Transaction Date': st.column_config.DateColumn(
                                    label='Date',
                                    format='MM/DD/YYYY'),
                                'Transaction Type': None,
                                'Category': 'Mode'},
                            )

                # Submit button
                if st.button('Submit all'):
                    df = (pd.concat([df, st.session_state.new_rows]).
                            sort_values('Transaction Date', ascending=False).
                            reset_index)(drop=True)
                    
                    save_to_gcs(df)

                    st.session_state.new_rows = pd.DataFrame(columns=['Transaction Date',
                                                                      'Transaction Type',
                                                                      'Category'])
                    
                    st.rerun()