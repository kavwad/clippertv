#!/usr/bin/env python3

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


TRIP_TABLE_CATEGORIES = ['Muni Bus', 'Muni Metro', 'BART Entrance', 'Cable Car',
                         'Caltrain Entrance', 'Ferry Entrance', 'AC Transit', 'SamTrans']

COST_TABLE_CATEGORIES = ['Muni Bus', 'Muni Metro', 'BART Exit', 'Cable Car',
                         'Caltrain', 'Ferry', 'AC Transit', 'SamTrans']

COLOR_MAP = {'Muni Bus': '#BA0C2F', 'Muni Metro': '#FDB813', 'BART': '#0099CC',
             'Cable Car': '#8B4513', 'Caltrain': '#6C6C6C', 'AC Transit': '#00A55E',
             'Ferry': '#4DD0E1', 'SamTrans': '#D3D3D3'}


def load_data(rider):
    df = pd.read_csv('gcs://clippertv_data/data_' + rider.lower() + '.csv',
                     parse_dates=['Transaction Date'],
                     storage_options={'token': json.loads(st.secrets['gcs_key'])})
    return df


def process_data(df):
    pivot_year = create_pivot_year(df)
    pivot_month = create_pivot_month(df)
    pivot_year_cost = create_pivot_year_cost(df)
    pivot_month_cost = create_pivot_month_cost(df)
    free_xfers = ((df['Transaction Type'] ==
                  'Single-tag fare payment') & (df['Debit'].isna())).sum()
    return pivot_year, pivot_month, pivot_year_cost, pivot_month_cost, free_xfers


def create_charts(pivot_month, pivot_month_cost, riders):
    trip_chart = create_trip_chart(pivot_month)
    cost_chart = create_cost_chart(pivot_month_cost)
    rides_chart = create_rides_chart(riders)
    return trip_chart, cost_chart, rides_chart


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
    pivot_year = pivot_year.reindex(
        columns=TRIP_TABLE_CATEGORIES).fillna(0).astype(int)
    pivot_year.columns = [c.replace(' Entrance', '')
                          for c in pivot_year.columns]

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
    pivot_month = pivot_month.reindex(
        columns=TRIP_TABLE_CATEGORIES).fillna(0).astype(int)
    pivot_month.columns = [c.replace(' Entrance', '')
                           for c in pivot_month.columns]

    return pivot_month


def create_pivot_year_cost(df):
    # Create pivot table by year and category
    pivot_year_cost = (df.pivot_table(index=df['Transaction Date'].dt.year,
                                      columns='Category',
                                      values=['Debit', 'Credit'],
                                      aggfunc='sum',
                                      fill_value=0
                                      ))

    if 'Caltrain Adult 3 Zone Monthly Pass' in df['Product'].unique():
        # Calculate annual cost for Caltrain monthly pass
        caltrain_pass_yearly = df.pivot_table(index=df['Transaction Date'].dt.year,
                                            columns='Product',
                                            values='Debit',
                                            aggfunc='sum',
                                            fill_value=0)[['Caltrain Adult 3 Zone Monthly Pass']]
        caltrain_pass_yearly.columns = pd.MultiIndex.from_tuples([('Debit', 'Caltrain Pass')])

        # Add Caltrain pass cost to pivot table
        pivot_year_cost = pivot_year_cost.join(
            caltrain_pass_yearly, on='Transaction Date').fillna(0)

        # Calculate net values for BART, Caltrain, and Ferry
        pivot_year_cost[('Debit', 'Caltrain')] = (pivot_year_cost[('Debit', 'Caltrain Entrance')]
                                                  + pivot_year_cost[('Debit', 'Caltrain Pass')]
                                                  - pivot_year_cost[('Credit', 'Caltrain Exit')])

    else:
        pivot_year_cost[('Debit', 'Caltrain')] = (pivot_year_cost[('Debit', 'Caltrain Entrance')]
                                                  - pivot_year_cost[('Credit', 'Caltrain Exit')])

    pivot_year_cost[('Debit', 'Ferry')] = (pivot_year_cost[('Debit', 'Ferry Entrance')]
                                           + pivot_year_cost[('Debit', 'Ferry Exit')]
                                           - pivot_year_cost[('Credit', 'Ferry Exit')])

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

    if 'Caltrain Adult 3 Zone Monthly Pass' in df['Product'].unique():
        # Calculate monthly cost for Caltrain pass
        caltrain_pass_monthly = (df[df['Product'] == 'Caltrain Adult 3 Zone Monthly Pass']
                                .groupby(pd.Grouper(key='Transaction Date', freq='M'))['Debit']
                                .sum().to_frame(('Debit', 'Caltrain Pass')))

        # Add Caltrain pass cost to pivot table
        pivot_month_cost = pivot_month_cost.join(
            caltrain_pass_monthly, on='Transaction Date').fillna(0)

        # Calculate net values for BART, Caltrain, and Ferry
        pivot_month_cost[('Debit', 'Caltrain')] = (pivot_month_cost[('Debit', 'Caltrain Entrance')]
                                                + pivot_month_cost[('Debit', 'Caltrain Pass')]
                                                - pivot_month_cost[('Credit', 'Caltrain Exit')])
    
    else:
        pivot_month_cost[('Debit', 'Caltrain')] = (pivot_month_cost[('Debit', 'Caltrain Entrance')]
                                                   - pivot_month_cost[('Credit', 'Caltrain Exit')])
    
    pivot_month_cost[('Debit', 'Ferry')] = (pivot_month_cost[('Debit', 'Ferry Entrance')]
                                            + pivot_month_cost[('Debit', 'Ferry Exit')]
                                            - pivot_month_cost[('Credit', 'Ferry Exit')])

    # Drop credit columns
    pivot_month_cost = pivot_month_cost['Debit']

    # Sort by date and rename index to month and year
    pivot_month_cost.sort_index(ascending=False, inplace=True)
    pivot_month_cost.index = pivot_month_cost.index.strftime('%b %Y')
    pivot_month_cost.index.name = 'Month'

    # Reorder columns and remove 'Entrance' from column names
    pivot_month_cost = pivot_month_cost.reindex(
        columns=COST_TABLE_CATEGORIES).fillna(0)
    pivot_month_cost.rename(columns={'BART Exit': 'BART'}, inplace=True)

    return pivot_month_cost


def create_trip_chart(pivot_month):
    pivot_month.index = pd.to_datetime(pivot_month.index, format='%b %Y')
    trip_chart = px.bar(pivot_month,
                        color_discrete_map=COLOR_MAP,
                        )

    trip_chart.update_layout(
        title_text="Monthly trips",
        xaxis_title='',
        yaxis_title='Number of trips',
        legend_title='',
        bargap=0.1)

    trip_chart.update_traces(hovertemplate='<b>%{x|%B %Y}</b>: %{y}')
    return trip_chart


def create_cost_chart(pivot_month_cost):
    pivot_month_cost.index = pd.to_datetime(
        pivot_month_cost.index, format='%b %Y')
    cost_chart = px.bar(pivot_month_cost,
                        color_discrete_map=COLOR_MAP,
                        )

    cost_chart.update_layout(
        title_text="Monthly transit cost",
        xaxis_title='',
        yaxis_title='Cost in $',
        legend_title='',
        bargap=0.1)

    cost_chart.update_traces(hovertemplate='<b>%{x|%B %Y}</b>: $%{y}')
    return cost_chart


def create_rides_chart(riders):
    comparison_chart = go.Figure()
    for rider in riders:
        df = load_data(rider)
        total_rides_per_month = create_pivot_month(df).sum(axis=1)
        total_rides_per_month.index = pd.to_datetime(
            total_rides_per_month.index, format='%b %Y')

        chart_colors = {
            'K': COLOR_MAP['Muni Metro'], 'B': COLOR_MAP['AC Transit']}
        comparison_chart.add_trace(go.Scatter(x=total_rides_per_month.index,
                                              y=total_rides_per_month,
                                              mode='lines',
                                              name=rider,
                                              line_color=chart_colors[rider],
                                              line_shape='spline'))

    comparison_chart.update_layout(title_text='Trips per month',
                                   yaxis_title='Trips',
                                   hovermode='x unified',
                                   xaxis={'hoverformat': '%b %Y'}
                                   )

    comparison_chart.update_traces(hovertemplate='<b>%{y}</b>')

    return comparison_chart
