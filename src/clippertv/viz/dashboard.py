"""Dashboard component functions for ClipperTV."""

import pandas as pd
import streamlit as st

from ..config import config
from .charts import (
    create_trip_chart,
    create_cost_chart,
    create_bike_walk_chart,
    create_comparison_chart
)


def create_pivot_year(df):
    """Create yearly pivot table of trips by category."""
    pivot_year = (df.pivot_table(
        index=df['Transaction Date'].dt.year,
        columns='Category',
        values='Transaction Date',
        aggfunc='count',
        fill_value=0
    ))

    # Sort by date and rename index
    pivot_year.sort_index(ascending=False, inplace=True)
    pivot_year.index.name = 'Year'

    # Reorder columns and remove 'Entrance' from column names
    pivot_year = pivot_year.reindex(
        columns=config.transit_categories.trip_table_categories
    ).fillna(0).astype(int)
    
    pivot_year.columns = [c.replace(' Entrance', '')
                         for c in pivot_year.columns]

    return pivot_year


def create_pivot_month(df):
    """Create monthly pivot table of trips by category."""
    pivot_month = (df.groupby([pd.Grouper(key='Transaction Date', freq='ME'), 'Category'])
                  .size()
                  .unstack(fill_value=0)
                  )

    # Sort by date and rename index
    pivot_month.sort_index(ascending=False, inplace=True)
    pivot_month.index.name = 'Month'

    # Reorder columns and remove 'Entrance' from column names
    pivot_month = pivot_month.reindex(
        columns=config.transit_categories.trip_table_categories
    ).fillna(0).astype(int)
    
    pivot_month.columns = [c.replace(' Entrance', '')
                          for c in pivot_month.columns]

    return pivot_month


def create_pivot_year_cost(df):
    """Create yearly pivot table of costs by category."""
    # Create pivot table by year and category
    pivot_year_cost = (df.pivot_table(
        index=df['Transaction Date'].dt.year,
        columns='Category',
        values=['Debit', 'Credit'],
        aggfunc='sum',
        fill_value=0
    ))

    if 'Caltrain Adult 3 Zone Monthly Pass' in df['Product'].unique():
        # Calculate annual cost for Caltrain monthly pass
        caltrain_pass_yearly = df.pivot_table(
            index=df['Transaction Date'].dt.year,
            columns='Product',
            values='Debit',
            aggfunc='sum',
            fill_value=0
        )[['Caltrain Adult 3 Zone Monthly Pass']]

        caltrain_pass_yearly.columns = pd.MultiIndex.from_tuples([('Debit', 'Caltrain Pass')])

        # Add Caltrain pass cost to pivot table
        pivot_year_cost = pivot_year_cost.join(
            caltrain_pass_yearly, on='Transaction Date'
        ).fillna(0)

        # Calculate net values for Caltrain
        pivot_year_cost[('Debit', 'Caltrain')] = (
            pivot_year_cost.get(('Debit', 'Caltrain Entrance'), 0) +
            pivot_year_cost.get(('Debit', 'Caltrain Pass'), 0) -
            pivot_year_cost.get(('Credit', 'Caltrain Exit'), 0)
        )
    else:
        pivot_year_cost[('Debit', 'Caltrain')] = (
            pivot_year_cost.get(('Debit', 'Caltrain Entrance'), 0) -
            pivot_year_cost.get(('Credit', 'Caltrain Exit'), 0)
        )

    # Calculate net values for Ferry
    pivot_year_cost[('Debit', 'Ferry')] = (
        pivot_year_cost.get(('Debit', 'Ferry Entrance'), 0) +
        pivot_year_cost.get(('Debit', 'Ferry Exit'), 0) -
        pivot_year_cost.get(('Credit', 'Ferry Exit'), 0)
    )

    # Drop credit columns
    pivot_year_cost = pivot_year_cost['Debit']

    # Sort by date and rename index
    pivot_year_cost.sort_index(ascending=False, inplace=True)
    pivot_year_cost.index.name = 'Year'

    # Reorder columns and rename BART Exit to BART
    pivot_year_cost = pivot_year_cost.reindex(
        columns=config.transit_categories.cost_table_categories
    ).fillna(0)
    
    pivot_year_cost.rename(columns={'BART Exit': 'BART'}, inplace=True)

    return pivot_year_cost


def create_pivot_month_cost(df):
    """Create monthly pivot table of costs by category."""
    # Create pivot table by month and category
    pivot_month_cost = (df.groupby([pd.Grouper(key='Transaction Date', freq='ME'), 'Category'])
                        [['Debit', 'Credit']]
                        .sum()
                        .unstack(fill_value=0)
                        )

    if 'Caltrain Adult 3 Zone Monthly Pass' in df['Product'].unique():
        # Calculate monthly cost for Caltrain pass
        caltrain_pass_monthly = (df[(df['Product'] == 'Caltrain Adult 3 Zone Monthly Pass')
                                 & (df['Category'].str.contains('Reload'))]
                                 .groupby(pd.Grouper(key='Transaction Date', freq='ME'))['Credit']
                                 .sum()
                                 .to_frame(('Debit', 'Caltrain Pass'))
                                 )

        # Add Caltrain pass cost to pivot table
        pivot_month_cost = pivot_month_cost.join(
            caltrain_pass_monthly, on='Transaction Date'
        ).fillna(0)

        # Calculate net values for Caltrain
        pivot_month_cost[('Debit', 'Caltrain')] = (
            pivot_month_cost.get(('Debit', 'Caltrain Entrance'), 0) +
            pivot_month_cost.get(('Debit', 'Caltrain Pass'), 0) -
            pivot_month_cost.get(('Credit', 'Caltrain Exit'), 0)
        )
    else:
        pivot_month_cost[('Debit', 'Caltrain')] = (
            pivot_month_cost.get(('Debit', 'Caltrain Entrance'), 0) -
            pivot_month_cost.get(('Credit', 'Caltrain Exit'), 0)
        )

    # Calculate net values for Ferry
    pivot_month_cost[('Debit', 'Ferry')] = (
        pivot_month_cost.get(('Debit', 'Ferry Entrance'), 0) +
        pivot_month_cost.get(('Debit', 'Ferry Exit'), 0) -
        pivot_month_cost.get(('Credit', 'Ferry Exit'), 0)
    )

    # Drop credit columns
    pivot_month_cost = pivot_month_cost['Debit']

    # Sort by date and rename index
    pivot_month_cost.sort_index(ascending=False, inplace=True)
    pivot_month_cost.index.name = 'Month'

    # Reorder columns and rename BART Exit to BART
    pivot_month_cost = pivot_month_cost.reindex(
        columns=config.transit_categories.cost_table_categories
    ).fillna(0)
    
    pivot_month_cost.rename(columns={'BART Exit': 'BART'}, inplace=True)

    return pivot_month_cost


def process_data(df):
    """Process data into pivot tables for display."""
    pivot_year = create_pivot_year(df)
    pivot_month = create_pivot_month(df)
    pivot_year_cost = create_pivot_year_cost(df)
    pivot_month_cost = create_pivot_month_cost(df)
    
    # Count free transfers
    free_xfers = ((df['Transaction Type'] == 'Single-tag fare payment') 
                 & (df['Debit'].isna())).sum()
    
    return pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers


def calculate_summary_stats(pivot_month, pivot_month_cost, df):
    """Calculate summary statistics for the dashboard."""
    current_month_trips = pivot_month.iloc[0]
    current_month_costs = pivot_month_cost.iloc[0]
    trips_this_month = current_month_trips.sum()
    cost_this_month = current_month_costs.sum().round().astype(int)

    has_previous_month = len(pivot_month) > 1
    previous_month_trips = pivot_month.iloc[1].sum() if has_previous_month else trips_this_month
    previous_month_costs = (pivot_month_cost.iloc[1].sum().round().astype(int)
                            if has_previous_month else cost_this_month)

    trip_diff = previous_month_trips - trips_this_month
    trip_diff_text = "fewer" if trip_diff >= 0 else "more"

    cost_diff = previous_month_costs - cost_this_month
    cost_diff_text = "less" if cost_diff >= 0 else "more"
    
    # Most recent date and data for current month
    most_recent_date = df['Transaction Date'].max()
    this_month = df[
        (df['Transaction Date'].dt.year == most_recent_date.year) &
        (df['Transaction Date'].dt.month == most_recent_date.month)
    ]
    
    # Caltrain pass analysis
    pass_upshot = None
    if 'Caltrain Adult 3 Zone Monthly Pass' in this_month['Product'].values:
        pass_rides = this_month[
            (this_month['Category'].str.contains('Caltrain')).fillna(False) &
            (this_month['Transaction Type'] == 'Manual entry')
        ]
        
        pass_savings = -len(pass_rides) * 7.70
        pass_cost = 184.80
        additional_caltrain_cost = this_month[
            (this_month['Category'].str.contains('Caltrain')).fillna(False)
        ][['Debit', 'Credit']].sum()
        
        additional_caltrain_cost = (additional_caltrain_cost['Debit'] - 
                                   additional_caltrain_cost['Credit'])
        
        pass_upshot = (pass_savings + pass_cost + 
                      additional_caltrain_cost).round(0).astype(int)
    
    return {
        'trips_this_month': trips_this_month,
        'cost_this_month': cost_this_month,
        'trip_diff': trip_diff,
        'trip_diff_text': trip_diff_text,
        'cost_diff': cost_diff,
        'cost_diff_text': cost_diff_text,
        'most_recent_date': most_recent_date,
        'pass_upshot': pass_upshot,
        'most_used_mode': current_month_trips.idxmax()
    }


def display_summary(rider, stats, pivot_month, pivot_year=None, pivot_year_cost=None):
    """Display summary statistics at the top of the dashboard."""
    # Current month stats
    st.markdown(f"#### {rider} took **:red[{stats['trips_this_month']}]** trips in "
               f"{stats['most_recent_date'].strftime('%B')}, which cost "
               f"**:red[${stats['cost_this_month']}]**.")
    
    # Comparison with previous month
    st.markdown(f"{rider} rode **{stats['most_used_mode']}** most, at "
               f"**{pivot_month.iloc[0][stats['most_used_mode']]}** times. "
               f"Altogether, {rider} took {abs(stats['trip_diff'])} {stats['trip_diff_text']} "
               f"trips and paid ${abs(stats['cost_diff'])} {stats['cost_diff_text']} "
               f"than the previous month.")
    
    # Caltrain pass analysis
    if stats['pass_upshot'] is not None:
        if stats['pass_upshot'] < 0:
            st.markdown(f"This month, {rider} saved **${-stats['pass_upshot']}** "
                       f"with a Caltrain pass.")
        elif stats['pass_upshot'] > 0:
            st.markdown(f"This month, {rider} spent an extra **${stats['pass_upshot']}** "
                       f"by getting a Caltrain pass (!!).")
        else:
            st.markdown(f"This month, {rider} broke even with a Caltrain pass.")
    
    # Year-to-date stats (except for January)
    if stats['most_recent_date'].strftime('%B') != 'January' and pivot_year is not None and pivot_year_cost is not None:
        st.markdown(f"This year, {rider} has taken **{pivot_year.iloc[0].sum()}** trips, "
                   f"costing **${pivot_year_cost.iloc[0].sum().round().astype(int)}**.")
    
    # Free transfers (commented out in original)
    # st.markdown(f"Since 2021, {rider} has gotten **{free_xfers}** free transfers!")


def display_charts(trip_chart, cost_chart):
    """Display the main charts."""
    st.plotly_chart(trip_chart, use_container_width=True)
    st.plotly_chart(cost_chart, use_container_width=True)


def setup_dashboard_tabs(pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, 
                        bike_walk_chart, comparison_chart, rider):
    """Set up and display the dashboard tabs."""
    annual_tab, monthly_tab, bike_walk_tab, comparison_tab = st.tabs([
        'Annual stats',
        'Monthly stats',
        'Active transportation',
        'Tête-à-tête'
    ])
    
    # Annual stats tab
    with annual_tab:
        st.subheader('Annual trips by mode', anchor=False)
        st.dataframe(
            pivot_year,
            width="stretch",
            column_config={'Year': st.column_config.NumberColumn(format="%d", width=75)}
        )
        
        st.subheader('Annual trip cost by mode', anchor=False)
        st.dataframe(
            pivot_year_cost,
            width="stretch",
            column_config=config.column_config
        )
    
    # Monthly stats tab
    with monthly_tab:
        st.subheader('Monthly trips by mode', anchor=False)
        st.dataframe(
            pivot_month,
            width="stretch",
            column_config={'Month': st.column_config.DateColumn(format="MMM YYYY", width=75)}
        )
        
        st.subheader('Monthly trip cost by mode', anchor=False)
        st.dataframe(
            pivot_month_cost,
            width="stretch",
            column_config=config.column_config
        )
    
    # Bike/walk tab
    with bike_walk_tab:
        if rider == 'K':
            # st.plotly_chart(bike_walk_chart, width="stretch",)
            st.write('Coming soon!')
        else:
            st.write('Coming soon!')
    
    # Comparison tab
    with comparison_tab:
        st.plotly_chart(comparison_chart, use_container_width=True)
