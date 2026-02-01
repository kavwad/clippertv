"""Data processing functions for ClipperTV dashboards.

These functions are used by both the Streamlit and FastAPI versions of the app.
"""

import pandas as pd

from ..config import config


def _attribute_pass_costs_to_first_use(df):
    """Attribute pass purchase costs to the month of first pass-covered ride.

    Finds pass purchases and attributes their cost to the month when the pass
    was first used (first exit covered by the pass). If no pass-covered rides
    exist, attributes to the purchase month.

    Returns:
        DataFrame with columns [Transaction Date, Pass Cost] where Transaction Date
        is set to the first pass-covered ride's date (or purchase date if no rides)
    """
    # Find pass purchases (any Caltrain pass product)
    pass_purchases = df[
        (df['Category'] == 'Reload') &
        (df['Product'].str.contains('Caltrain', na=False)) &
        (df['Product'].str.contains('Pass', na=False)) &
        (df['Credit'] > 100)
    ].copy()

    if pass_purchases.empty:
        return pd.DataFrame(columns=['Transaction Date', 'Pass Cost'])

    # Find pass-covered rides (any Caltrain pass product)
    pass_rides = df[
        (df['Product'].str.contains('Caltrain', na=False)) &
        (df['Product'].str.contains('Pass', na=False)) &
        (df['Category'].str.contains('Caltrain', na=False)) &
        (df['Transaction Type'] == 'exit')
    ].copy()

    attributed_costs = []

    for _, purchase in pass_purchases.iterrows():
        purchase_date = purchase['Transaction Date']
        pass_cost = purchase['Credit']

        # Find first pass-covered ride after purchase
        subsequent_rides = pass_rides[pass_rides['Transaction Date'] >= purchase_date]

        if not subsequent_rides.empty:
            # Use the date of the first pass-covered ride
            first_ride_date = subsequent_rides['Transaction Date'].min()
            attributed_costs.append({
                'Transaction Date': first_ride_date,
                'Pass Cost': pass_cost
            })
        else:
            # No pass-covered rides found, use purchase date
            attributed_costs.append({
                'Transaction Date': purchase_date,
                'Pass Cost': pass_cost
            })

    return pd.DataFrame(attributed_costs)


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

    # Attribute pass costs to month of first use
    pass_costs_attributed = _attribute_pass_costs_to_first_use(df)

    if not pass_costs_attributed.empty:
        # Group attributed pass costs by year
        caltrain_pass_yearly = (pass_costs_attributed
                                .groupby(pass_costs_attributed['Transaction Date'].dt.year)['Pass Cost']
                                .sum()
                                .to_frame(('Debit', 'Caltrain Pass'))
                                )

        # Add Caltrain pass cost to pivot table
        pivot_year_cost = pivot_year_cost.join(
            caltrain_pass_yearly
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

    # Attribute pass costs to month of first use
    pass_costs_attributed = _attribute_pass_costs_to_first_use(df)

    if not pass_costs_attributed.empty:
        # Group attributed pass costs by month
        caltrain_pass_monthly = (pass_costs_attributed
                                 .groupby(pd.Grouper(key='Transaction Date', freq='ME'))['Pass Cost']
                                 .sum()
                                 .to_frame(('Debit', 'Caltrain Pass'))
                                 )

        # Add Caltrain pass cost to pivot table
        pivot_month_cost = pivot_month_cost.join(
            caltrain_pass_monthly
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
