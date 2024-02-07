import pandas as pd
import plotly.express as px
import streamlit as st

TRIP_TABLE_CATEGORIES = ['Muni Bus', 'Muni Metro', 'BART Entrance', 'Cable Car',
                         'Caltrain Entrance', 'Ferry Entrance', 'AC Transit', 'SamTrans']

COST_TABLE_CATEGORIES = ['Muni Bus', 'Muni Metro', 'BART Exit', 'Cable Car',
                         'Caltrain', 'Ferry', 'AC Transit', 'SamTrans']

COLOR_MAP = {'Muni Bus': '#BA0C2F', 'Muni Metro': '#FDB813', 'BART': '#0099CC',
             'Cable Car': 'brown', 'Caltrain': '#6C6C6C', 'AC Transit': '#00A55E',
             'Ferry': '#008080', 'SamTrans': '#D3D3D3'}

def load_data():
    df = pd.read_csv('data_k.csv', parse_dates=['Transaction Date'])
    return df

def process_data(df):
    pivot_year = create_pivot_year(df)
    pivot_month = create_pivot_month(df)
    pivot_year_cost = create_pivot_year_cost(df)
    pivot_month_cost = create_pivot_month_cost(df)
    free_xfers = ((df['Transaction Type'] == 'Single-tag fare payment') & (df['Debit'].isna())).sum()
    return pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers

def create_pivot_year(df):
    pivot_year = (df.pivot_table(index=df['Transaction Date'].dt.year,
                                        columns='Category',
                                        values='Transaction Date',
                                        aggfunc='count',
                                        fill_value=0
                                        ))

    # Sort by date and rename index
    pivot_year.sort_index(ascending=False, inplace=True)
    pivot_year.index.name = 'Year'

    # Reorder columns and remove 'Entrance' from column names
    pivot_year = pivot_year.reindex(columns=TRIP_TABLE_CATEGORIES).fillna(0).astype(int)
    pivot_year.columns = [c.replace(' Entrance', '') for c in pivot_year.columns]

    return pivot_year

def create_pivot_month(df):
    pivot_month = (df.groupby([pd.Grouper(key='Transaction Date', freq='M'), 'Category'])
                .size()
                .unstack(fill_value=0)
                )

    # Sort by date and rename index to month and year
    pivot_month.sort_index(ascending=False, inplace=True)
    pivot_month.index = pivot_month.index.strftime('%b %Y')
    pivot_month.index.name = 'Month'

    # Reorder columns and remove 'Entrance' from column names
    pivot_month = pivot_month.reindex(columns=TRIP_TABLE_CATEGORIES).fillna(0).astype(int)
    pivot_month.columns = [c.replace(' Entrance', '') for c in pivot_month.columns]

    return pivot_month

def create_pivot_year_cost(df):
    pivot_year_cost = (df.pivot_table(index=df['Transaction Date'].dt.year,
                                    columns='Category',
                                    values=['Debit', 'Credit'],
                                    aggfunc='sum',
                                    fill_value=0
                                    ))

    # Calculate net values for BART, Caltrain, and Ferry
    pivot_year_cost[('Debit', 'Caltrain')] = (pivot_year_cost[('Debit', 'Caltrain Entrance')] -
                                        pivot_year_cost[('Credit', 'Caltrain Exit')])
    pivot_year_cost[('Debit', 'Ferry')] = (pivot_year_cost[('Debit', 'Ferry Entrance')] +
                                    pivot_year_cost[('Debit', 'Ferry Exit')] -
                                    pivot_year_cost[('Credit', 'Ferry Exit')])

    # Drop credit columns
    pivot_year_cost = pivot_year_cost['Debit']

    # Sort by date and rename index
    pivot_year_cost.sort_index(ascending=False, inplace=True)
    pivot_year_cost.index.name = 'Year'

    # Reorder columns and remove 'Entrance' from column names
    pivot_year_cost = (pivot_year_cost.reindex(columns=COST_TABLE_CATEGORIES)
                .fillna(0))
    pivot_year_cost.rename(columns={'BART Exit': 'BART'}, inplace=True)

    return pivot_year_cost

def create_pivot_month_cost(df):
    # Create pivot table by month and category
    pivot_month_cost = (df.groupby([pd.Grouper(key='Transaction Date', freq='M'), 'Category'])[['Debit', 'Credit']]
                    .sum()
                    .unstack(fill_value=0)
                    )

    # Calculate net values for BART, Caltrain, and Ferry
    pivot_month_cost[('Debit', 'Caltrain')] = (pivot_month_cost[('Debit', 'Caltrain Entrance')] -
                                            pivot_month_cost[('Credit', 'Caltrain Exit')])
    pivot_month_cost[('Debit', 'Ferry')] = (pivot_month_cost[('Debit', 'Ferry Entrance')] +
                                            pivot_month_cost[('Debit', 'Ferry Exit')] -
                                            pivot_month_cost[('Credit', 'Ferry Exit')])

    # Drop credit columns
    pivot_month_cost = pivot_month_cost['Debit']


    # Sort by date and rename index to month and year
    pivot_month_cost.sort_index(ascending=False, inplace=True)
    pivot_month_cost.index = pivot_month_cost.index.strftime('%b %Y')
    pivot_month_cost.index.name = 'Month'

    # Reorder columns and remove 'Entrance' from column names
    pivot_month_cost = pivot_month_cost.reindex(columns=COST_TABLE_CATEGORIES).fillna(0)
    pivot_month_cost.rename(columns={'BART Exit': 'BART'}, inplace=True)

    return pivot_month_cost

def create_charts(pivot_month, pivot_month_cost):
    trip_chart = create_trip_chart(pivot_month)
    cost_chart = create_cost_chart(pivot_month_cost)
    return trip_chart, cost_chart

def create_trip_chart(pivot_month):
    pivot_month.index = pd.to_datetime(pivot_month.index)
    trip_chart = px.bar(pivot_month,
                        color_discrete_map=COLOR_MAP,
                        )

    trip_chart.update_layout(
        title_text="Monthly trips",
        xaxis_title='',
        yaxis_title='Number of trips',
        legend_title='',
        bargap=0.1)

    trip_chart.update_traces(hovertemplate= '<b>%{x|%B %Y}</b>: %{y}')
    return trip_chart

def create_cost_chart(pivot_month_cost):
    pivot_month_cost.index = pd.to_datetime(pivot_month_cost.index)
    cost_chart = px.bar(pivot_month_cost,
                        color_discrete_map=COLOR_MAP,
                        )

    cost_chart.update_layout(
        title_text="Monthly transit cost",
        xaxis_title='',
        yaxis_title='Cost in $',
        legend_title='',
        bargap=0.1)

    cost_chart.update_traces(hovertemplate= '<b>%{x|%B %Y}</b>: $%{y}')
    return cost_chart

def streamlit_setup():
    st.set_page_config(page_title="Kaveh’s transit trips", layout='wide')
    st.title('Kaveh’s transit trips', anchor=False)
    # st.sidebar.markdown('# Kaveh')
    # st.sidebar.markdown('# Bree')

def main():
    df = load_data()
    pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers = process_data(df)
    trip_chart, cost_chart = create_charts(pivot_month, pivot_month_cost)
    
    # Set up the page
    streamlit_setup()
    
    # Display summary
    st.markdown(f'Kaveh took **{pivot_month.iloc[0].sum()}** trips last month,\
                which cost **${pivot_month_cost.iloc[0].sum().round().astype(int)}**.')
    if pivot_month.iloc[0].sum() > pivot_year.iloc[0].sum():
        st.markdown(f"This year, he's taken **{pivot_year.iloc[0].sum()}** trips,\
                    costing **${pivot_year_cost.iloc[0].sum().round().astype(int)}**.")
    
    # Display charts
    st.plotly_chart(trip_chart, use_container_width=True)
    st.plotly_chart(cost_chart, use_container_width=True)
    
    # Display tables
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

    monthly_tab, annual_tab, add_trips_tab = st.tabs(['Monthly stats', 'Annual stats', 'Add trips'])

    with monthly_tab:
        st.subheader('Monthly trips by mode', anchor=False)
        st.dataframe(pivot_month,
                        use_container_width=True,
                        column_config={'Month': st.column_config.DateColumn(format="MMM YYYY", width=75)})
        st.subheader('Monthly trip cost by mode', anchor=False)
        st.dataframe(pivot_month_cost,
                        use_container_width=True,
                        column_config=column_config)
    
    with annual_tab:
        st.subheader('Annual trips by mode', anchor=False)
        st.dataframe(pivot_year,
                        use_container_width=True,
                        column_config={'Year': st.column_config.NumberColumn(format="%d", width=75)})
        st.subheader('Annual trip cost by mode', anchor=False)
        st.dataframe(pivot_year_cost,
                        use_container_width=True,
                        column_config=column_config)
        
    st.divider()

    # Display add_trips widget
    with st.expander('Add trips'):
        '## Missed connections'

        # Form elements
        col1, col2, col3 = st.columns(3)
        with col1:
            transaction_date = st.date_input('Date:', format='MM/DD/YYYY')
        with col2:
            category = st.selectbox('Mode:', options=DISP_CATEGORIES)
        with col3:
            rides = st.number_input('Rides:', min_value=1, max_value=10, value=1, step=1)

        # Initialize new_rows in session state
        if 'new_rows' not in st.session_state:
            st.session_state.new_rows = pd.DataFrame(columns=['Transaction Date', 'Transaction Type', 'Category'])

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

        # Show rows to be added
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
                if st.button(':green[Submit all]'):
                    df = (pd.concat([df, st.session_state.new_rows]).
                            sort_values('Transaction Date', ascending=False).
                            reset_index)(drop=True)
                    df.to_csv('data_k.csv', index=False)
                    st.session_state.new_rows = pd.DataFrame()
                    
if __name__ == "__main__":
    main()