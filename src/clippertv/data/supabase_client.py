"""Supabase client for ClipperTV."""

import os
from functools import lru_cache
from typing import Dict, Any, Optional, List

import streamlit as st
import supabase

from clippertv.data.schema import (
    CREATE_RIDERS_TABLE,
    CREATE_TRANSIT_MODES_TABLE,
    CREATE_TRIPS_TABLE,
    TransitMode,
)


@lru_cache(maxsize=1)
def get_supabase_client():
    """Get a cached Supabase client instance.
    
    Returns:
        Client: Configured Supabase client
    """
    # Check if credentials are in Streamlit secrets
    if "supabase_url" in st.secrets and "supabase_key" in st.secrets:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
    # Fallback to environment variables
    else:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_API_KEY"]
    
    return supabase.create_client(url, key)


def initialize_database() -> None:
    """Initialize the Supabase database with required tables.
    
    This creates tables if they don't exist and populates reference data.
    """
    client = get_supabase_client()
    
    # Create tables using raw SQL (Supabase doesn't provide schema creation in Python client)
    tables = [
        ("riders", CREATE_RIDERS_TABLE),
        ("transit_modes", CREATE_TRANSIT_MODES_TABLE),
        ("trips", CREATE_TRIPS_TABLE),
    ]
    
    print("Checking if tables exist and creating if needed...")
    
    for table_name, create_sql in tables:
        try:
            # Check if table exists before creating
            client.table(table_name).select("*").limit(1).execute()
            print(f"- Table '{table_name}' exists")
        except Exception as e:
            # Table likely doesn't exist, create it
            print(f"- Table '{table_name}' needs to be created, but automatic creation isn't supported")
            print(f"  Please run this SQL in your Supabase dashboard: {create_sql[:60]}...")
    
    try:
        # Check if transit_modes table exists and has data
        result = client.table("transit_modes").select("*").execute()
        if len(result.data) == 0:
            print("Populating transit modes table...")
            _populate_transit_modes(client)
    except Exception as e:
        print(f"Couldn't check transit_modes table: {e}")
        print("Please create the required tables manually in the Supabase dashboard")


def _populate_transit_modes(client) -> None:
    """Populate the transit_modes table with initial data."""
    # Get transit modes from schema enum
    transit_modes = [
        {
            "name": mode.value,
            "display_name": mode.value,
            "color": _get_color_for_transit_mode(mode.value),
        }
        for mode in TransitMode
    ]
    
    # Insert transit modes
    for mode in transit_modes:
        client.table("transit_modes").insert(mode).execute()


def _get_color_for_transit_mode(mode_name: str) -> str:
    """Get the color for a transit mode."""
    # Import here to avoid circular imports
    from clippertv.config import config
    
    # Map the mode name to the color
    color_map = config.transit_categories.color_map
    return color_map.get(mode_name, "#808080")  # Default gray if not found