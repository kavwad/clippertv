"""Utility script to verify Supabase setup and show database information."""

import argparse
import sys
from typing import List, Dict

from clippertv.data.supabase_client import get_supabase_client, initialize_database


def verify_connection():
    """Verify connection to Supabase."""
    print("Checking Supabase connection...")
    try:
        client = get_supabase_client()
        print("✅ Successfully connected to Supabase")
        return client
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        return None


def check_table(client, table_name: str):
    """Check if a table exists and return its schema and row count."""
    try:
        # Try to get a row to verify table exists
        count_result = client.table(table_name).select("*", count="exact").execute()
        row_count = count_result.count if hasattr(count_result, "count") else 0
        print(f"✅ Table '{table_name}' exists with {row_count} rows")
        return True
    except Exception as e:
        print(f"❌ Table '{table_name}' error: {e}")
        return False


def summarize_data(client):
    """Summarize data in the database."""
    # Check riders
    try:
        riders = client.table("riders").select("id").execute()
        if riders.data:
            print("\nRiders:")
            for rider in riders.data:
                # Get trip count for this rider
                trips = client.table("trips").select("*", count="exact").eq("rider_id", rider["id"]).execute()
                trip_count = trips.count if hasattr(trips, "count") else 0
                print(f"  - {rider['id']}: {trip_count} trips")
        else:
            print("\nNo riders found in the database.")
    except Exception as e:
        print(f"\nCouldn't retrieve rider information: {e}")

    # Check transit modes
    try:
        modes = client.table("transit_modes").select("*").execute()
        if modes.data:
            print("\nTransit Modes:")
            for mode in modes.data:
                print(f"  - {mode['name']}: {mode['display_name']} (color: {mode['color']})")
        else:
            print("\nNo transit modes found in the database.")
    except Exception as e:
        print(f"\nCouldn't retrieve transit mode information: {e}")


def main():
    """Main entry point for the Supabase info script."""
    parser = argparse.ArgumentParser(description="Verify Supabase setup and show database information")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true", 
        help="Show more detailed information"
    )
    args = parser.parse_args()
    
    # Verify connection
    client = verify_connection()
    if not client:
        return 1
    
    # Check tables
    tables = ["riders", "transit_modes", "trips"]
    all_tables_exist = True
    
    print("\nChecking tables:")
    for table in tables:
        if not check_table(client, table):
            all_tables_exist = False
    
    if not all_tables_exist:
        print("\nSome tables are missing. Run the migration script with --setup-only to see setup instructions.")
        return 1
    
    # Show data summary
    summarize_data(client)
    
    print("\n✅ Supabase setup is complete and ready for use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())