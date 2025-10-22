"""Chart creation functions for ClipperTV."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from clippertv.config import config


def create_trip_chart(pivot_month):
    """Create chart showing monthly trips by category."""
    # Convert index to datetime for proper display
    pivot_month = pivot_month.copy()
    pivot_month.index = pd.to_datetime(pivot_month.index, format='%b %Y')
    
    # Create bar chart
    trip_chart = px.bar(
        pivot_month, 
        color_discrete_map=config.transit_categories.color_map
    )

    # Update layout
    trip_chart.update_layout(
        title_text="Monthly trips",
        xaxis_title='',
        yaxis_title='Number of trips',
        legend_title='',
        bargap=0.1
    )

    # Update hover template
    trip_chart.update_traces(hovertemplate='<b>%{x|%B %Y}</b>: %{y}')
    
    return trip_chart


def create_cost_chart(pivot_month_cost):
    """Create chart showing monthly costs by category."""
    # Convert index to datetime for proper display
    pivot_month_cost = pivot_month_cost.copy()
    pivot_month_cost.index = pd.to_datetime(pivot_month_cost.index, format='%b %Y')
    
    # Create bar chart
    cost_chart = px.bar(
        pivot_month_cost, 
        color_discrete_map=config.transit_categories.color_map
    )

    # Update layout
    cost_chart.update_layout(
        title_text="Monthly transit cost",
        xaxis_title='',
        yaxis_title='Cost in $',
        legend_title='',
        bargap=0.1
    )

    # Update hover template
    cost_chart.update_traces(hovertemplate='<b>%{x|%B %Y}</b>: $%{y}')
    
    return cost_chart


def create_bike_walk_chart():
    """Create chart showing biking and walking distance by month."""
    # This is a placeholder for future implementation
    # Will use health data to show active transportation metrics
    return None


def create_comparison_chart(riders, data_store):
    """Create chart comparing total trips between riders.

    Args:
        riders: List of rider IDs to compare
        data_store: Data store instance to load rider data from
    """
    comparison_chart = go.Figure()
    
    start_date = None
    latest_date = None
    
    # Find the overall date range across all riders
    for rider in riders:
        df = data_store.load_data(rider)
        rider_first_date = df['Transaction Date'].min()
        rider_last_date = df['Transaction Date'].max()
        
        if start_date is None or rider_first_date < start_date:
            start_date = rider_first_date
        if latest_date is None or rider_last_date > latest_date:
            latest_date = rider_last_date
    
    # Adjust start_date to beginning of month and latest_date to end of month
    start_date = start_date.to_period('M').to_timestamp(how='start')
    latest_date = latest_date.to_period('M').to_timestamp(how='end')
    
    # Create complete monthly index from start to latest month
    complete_index = pd.date_range(start=start_date, end=latest_date, freq='MS')
    
    # Add a trace for each rider
    chart_colors = {'K': config.transit_categories.color_map['Muni Metro'], 
                   'B': config.transit_categories.color_map['AC Transit']}
                   
    for rider in riders:
        df = data_store.load_data(rider)
        
        # Create monthly pivot table
        pivot_month = (df.groupby([pd.Grouper(key='Transaction Date', freq='ME'), 'Category'])
                      .size()
                      .unstack(fill_value=0))
                      
        # Calculate total trips per month
        total_rides_per_month = pivot_month.sum(axis=1)
        
        # Convert index to datetime and reindex to ensure all months are included
        total_rides_per_month.index = (total_rides_per_month.index
                                      .to_period('M')
                                      .to_timestamp(how='start'))
        total_rides_per_month = total_rides_per_month.reindex(complete_index, fill_value=0)

        # Add trace to chart
        comparison_chart.add_trace(
            go.Scatter(
                x=total_rides_per_month.index,
                y=total_rides_per_month,
                mode='lines',
                name=rider,
                line_color=chart_colors.get(rider, '#000000'),
                line_shape='spline'
            )
        )

    # Update layout
    comparison_chart.update_layout(
        title_text='Trips per month',
        yaxis_title='Trips',
        hovermode='x unified',
        xaxis={'hoverformat': '%b %Y'}
    )

    # Update hover template
    comparison_chart.update_traces(hovertemplate='<b>%{y}</b>')

    return comparison_chart
