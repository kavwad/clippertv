"""Dashboard component functions for ClipperTV Streamlit app."""

import streamlit as st

from ..config import config
from .charts import (
    create_trip_chart,
    create_cost_chart,
    create_bike_walk_chart,
    create_comparison_chart
)
from .data_processing import (
    process_data,
    calculate_summary_stats,
    create_pivot_year,
    create_pivot_month,
    create_pivot_year_cost,
    create_pivot_month_cost,
)

# Re-export for backwards compatibility
__all__ = [
    'process_data',
    'calculate_summary_stats',
    'create_pivot_year',
    'create_pivot_month',
    'create_pivot_year_cost',
    'create_pivot_month_cost',
    'display_summary',
    'display_charts',
    'setup_dashboard_tabs',
]


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
