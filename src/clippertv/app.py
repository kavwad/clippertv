"""Main Streamlit app for ClipperTV."""

import datetime
import time
import pandas as pd
import streamlit as st

from clippertv.config import config
from clippertv.data.factory import get_data_store
from clippertv.pdf.processor import process_pdf_statements, categorize_trips
from clippertv.viz.charts import (
    create_trip_chart, 
    create_cost_chart, 
    create_bike_walk_chart,
    create_comparison_chart
)
from clippertv.viz.dashboard import (
    process_data, 
    calculate_summary_stats,
    display_summary, 
    display_charts,
    setup_dashboard_tabs
)


def setup_page():
    """Set up the Streamlit page configuration."""
    st.set_page_config(page_title=config.app_title, layout='wide')


def rider_selector():
    """Display rider selection radio buttons."""
    return st.radio(
        'Choose your rider',
        config.riders,
        horizontal=True,
        label_visibility='hidden'
    )


@st.cache_resource(show_spinner=False)
def get_cached_data_store():
    """Return a cached data store instance for the app runtime."""
    return get_data_store()


def load_and_process_rider_data(rider):
    """Load rider data and process it for display."""
    df = get_cached_data_store().load_data(rider)
    return process_data(df)


def display_add_trips_section(rider):
    """Display the section for adding trips."""
    st.divider()
    with st.expander('Add trips'):
        password = st.text_input('Enter password', type='password')
        configured_password = (
            st.secrets.get("streamlit", {})
            .get("auth", {})
            .get("password")
        )
        is_authorized = False

        if configured_password is None:
            st.info("No admin password configured; access allowed.", icon="ℹ️")
            is_authorized = True
        elif password == configured_password:
            is_authorized = True
        
        if is_authorized:
            import_tab, manual_tab = st.tabs(['Import from pdf', 'Add manually'])
            
            with import_tab:
                display_pdf_import_section(rider)
            
            with manual_tab:
                display_manual_entry_section(rider)


def display_pdf_import_section(rider):
    """Display the PDF import section."""
    data_store = get_cached_data_store()
    pdfs = st.file_uploader(
        'Upload Clipper activity pdf',
        type='pdf',
        accept_multiple_files=True,
        label_visibility='collapsed'
    )
    
    if pdfs:  # Submit appears only after upload
        if st.button('Process all'):
            progress_bar = st.progress(0, 'Uploading PDFs')
            
            # Process PDF statements
            df_import_all = process_pdf_statements(pdfs, rider)
            progress_bar.empty()
            
            if df_import_all is not None:
                st.session_state.df_import_all = df_import_all
                st.write(st.session_state.df_import_all)
        
        if 'df_import_all' in st.session_state and st.button('Submit all', key='import_submit', type='primary'):
            data_store.save_data(rider, st.session_state.df_import_all)
            st.success(f'Uploaded!', icon='🚍')
            time.sleep(3)
            st.rerun()


def display_manual_entry_section(rider):
    """Display the manual entry section."""
    data_store = get_cached_data_store()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        transaction_date = st.date_input('Date:', format='MM/DD/YYYY')
    
    with col2:
        category = st.selectbox(
            'Mode:', 
            options=config.transit_categories.display_categories + ['Caltrain Pass']
        )
    
    with col3:
        rides = st.number_input('Rides:', min_value=1, step=1)
    
    # Initialize new_rows in session state if needed
    if 'new_rows' not in st.session_state:
        st.session_state.new_rows = pd.DataFrame(
            columns=['Transaction Date', 'Transaction Type', 'Category']
        )
    
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
                    'Category': [config.transit_categories.submit_categories[category]]
                })
            
            st.session_state.new_rows = pd.concat(
                [st.session_state.new_rows, new_row]
            )
    
    # Display new_rows and submit button
    if not st.session_state.new_rows.empty:
        with st.container(border=True):
            st.error('for K & B use only!', icon='🚨')
            
            st.data_editor(
                st.session_state.new_rows,
                column_config={
                    '_index': None,
                    'Transaction Date': st.column_config.DateColumn(
                        label='Date',
                        format='MM/DD/YYYY'
                    ),
                    'Transaction Type': None,
                    'Category': 'Mode'
                }
            )
            
            # Undo button
            if st.button('Remove last ride'):
                st.session_state.new_rows = st.session_state.new_rows.iloc[:-1]
            
            # Submit button
            if st.button('Submit all', key='manual_submit', type='primary'):
                df = data_store.load_data(rider)
                
                updated_df = pd.concat(
                    [df, st.session_state.new_rows]
                ).sort_values(
                    'Transaction Date', ascending=False
                ).reset_index(drop=True)
                
                data_store.save_data(rider, updated_df)
                
                # Reset new_rows
                st.session_state.new_rows = pd.DataFrame(
                    columns=['Transaction Date', 'Transaction Type', 'Category']
                )
                
                st.rerun()


def main():
    """Run the ClipperTV Streamlit app."""
    setup_page()
    data_store = get_cached_data_store()
    
    # Select rider
    rider = rider_selector()
    st.title('Welcome to Clipper TV!', anchor=False)
    
    # Load and process data
    pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers = load_and_process_rider_data(rider)
    
    # Create charts
    trip_chart = create_trip_chart(pivot_month)
    cost_chart = create_cost_chart(pivot_month_cost)
    bike_walk_chart = create_bike_walk_chart()
    comparison_chart = create_comparison_chart(config.riders, data_store)
    
    # Calculate summary statistics
    stats = calculate_summary_stats(pivot_month, pivot_month_cost, data_store.load_data(rider))
    
    # Display summary statistics
    display_summary(rider, stats, pivot_month, pivot_year, pivot_year_cost)
    
    # Display charts
    display_charts(trip_chart, cost_chart)
    
    # Set up dashboard tabs
    setup_dashboard_tabs(
        pivot_year, 
        pivot_month, 
        pivot_year_cost, 
        pivot_month_cost, 
        bike_walk_chart, 
        comparison_chart,
        rider
    )
    
    # Display section for adding trips
    display_add_trips_section(rider)


if __name__ == '__main__':
    main()
