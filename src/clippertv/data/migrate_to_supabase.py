"""Migration script to transfer data from GCS to Supabase."""

import argparse
import json
import os
import sys
import time
import signal
from contextlib import contextmanager
from typing import List, Optional, Dict, Tuple

import pandas as pd
from tqdm import tqdm

from clippertv.config import config
from clippertv.data.store import DataStore as GCSDataStore
from clippertv.data.supabase_client import initialize_database, get_supabase_client
from clippertv.data.schema import (
    CREATE_RIDERS_TABLE,
    CREATE_TRANSIT_MODES_TABLE,
    CREATE_TRIPS_TABLE,
    TransactionType,
)


def check_supabase_connection():
    """Check if Supabase connection is properly configured."""
    print("Checking Supabase connection...")
    
    # Check environment variables
    if 'SUPABASE_URL' not in os.environ and 'SUPABASE_API_KEY' not in os.environ:
        print("Warning: No Supabase environment variables detected")
        print("Checking for credentials in Streamlit secrets...")
    
    try:
        # Try to connect
        client = get_supabase_client()
        print("✅ Successfully connected to Supabase")
        return True
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        print("\nMake sure you've configured your Supabase credentials:")
        print("1. Set SUPABASE_URL and SUPABASE_API_KEY environment variables")
        print("   OR")
        print("2. Add credentials to .streamlit/secrets.toml")
        return False


def setup_tables(interactive=True):
    """Guide the user through setting up required tables.
    
    Args:
        interactive (bool): Whether to ask for user confirmation
        
    Returns:
        bool: Whether to proceed with migration
    """
    print("\nTo proceed with migration, you need the following tables in your Supabase project:")
    
    tables = [
        ("riders", CREATE_RIDERS_TABLE),
        ("transit_modes", CREATE_TRANSIT_MODES_TABLE),
        ("trips", CREATE_TRIPS_TABLE),
    ]
    
    print("\nCopy and run these SQL statements in your Supabase SQL Editor:")
    for table_name, create_sql in tables:
        print(f"\n--- {table_name} table ---")
        print(create_sql)
    
    if not interactive:
        print("\nPlease create these tables in your Supabase dashboard before migrating data.")
        return False
        
    try:
        proceed = input("\nHave you created all the tables? (yes/no): ")
        return proceed.lower() in ("yes", "y")
    except EOFError:
        # Handle non-interactive environments
        print("\nNon-interactive mode detected. Please run with --setup-only to see instructions.")
        return False


def migrate_rider_data(rider_id: str, gcs_store: GCSDataStore, supabase_client=None) -> int:
    """Migrate a single rider's data from GCS to Supabase.
    
    Args:
        rider_id (str): The rider's ID
        gcs_store (GCSDataStore): The GCS data store
        supabase_client: Optional pre-initialized Supabase client
        
    Returns:
        int: Number of transactions migrated
    """
    try:
        print(f"  Loading data for rider {rider_id} from GCS...")
        # Load data from GCS
        df = gcs_store.load_data(rider_id)
        
        if df.empty:
            print(f"  No data for rider {rider_id}")
            return 0
            
        print(f"  Loaded {len(df)} transactions from GCS")
        
        # Use the provided client or create a new one
        client = supabase_client or get_supabase_client()
        
        print(f"  Ensuring rider {rider_id} exists in Supabase...")
        # Ensure rider exists
        _ensure_rider_exists(client, rider_id)
        
        print(f"  Getting transit mode IDs...")
        # Process the dataframe into trips
        transit_ids = _get_transit_mode_ids(client)
        
        print(f"  Saving {len(df)} transactions to Supabase...")
        # Save to Supabase directly without creating a SupabaseStore
        _save_rider_data(client, rider_id, df, transit_ids)
        
        print(f"  Successfully migrated {len(df)} transactions for rider {rider_id}")
        return len(df)
    except Exception as e:
        print(f"Error migrating data for rider {rider_id}: {e}")
        print(f"Details: {str(e)}")
        return 0


def _ensure_rider_exists(client, rider_id: str) -> None:
    """Ensure the rider exists in the database, create if not."""
    result = execute_with_timeout(
        lambda: client.table("riders").select("*").eq("id", rider_id).execute(),
        timeout=10
    )
    
    if result is None:
        print(f"  Timed out checking if rider {rider_id} exists")
        return
    
    if not result.data:
        # Rider doesn't exist, create it
        print(f"  Creating new rider {rider_id}")
        execute_with_timeout(
            lambda: client.table("riders").insert({
                "id": rider_id,
                "name": None,
                "email": None,
            }).execute(),
            timeout=10
        )


def _get_transit_mode_ids(client) -> Dict[str, int]:
    """Get mapping of transit mode names to IDs."""
    result = execute_with_timeout(
        lambda: client.table("transit_modes").select("id,name").execute(),
        timeout=10
    )
    
    if result is None:
        print("  Timed out getting transit mode IDs")
        return {}
        
    return {item["name"]: item["id"] for item in result.data}


def _get_transit_id(transit_ids: Dict[str, int], transit_name: str) -> Optional[int]:
    """Get the transit mode ID for a given name.
    
    Handles variations of transit mode names like 'BART Exit' and 'BART Entrance'.
    The dashboard displays these entries with the base transit name (e.g., 'BART'),
    but the raw data contains the specific entry/exit variations.
    """
    # Direct match
    if transit_name in transit_ids:
        return transit_ids[transit_name]
    
    # Handle Entry/Exit variations
    for prefix in ['BART', 'Caltrain', 'Ferry', 'Muni', 'AC Transit', 'SamTrans', 'Cable Car']:
        if transit_name.startswith(f'{prefix} '):
            if prefix in transit_ids:
                return transit_ids[prefix]
    
    # For other transit modes, try to find a partial match
    for db_name, db_id in transit_ids.items():
        # Skip checking if the db_name is just a substring like "BART" in "BART Exit"
        # This prevents false matches
        if len(db_name.split()) == 1 and len(transit_name.split()) > 1:
            continue
            
        if db_name in transit_name or transit_name in db_name:
            return db_id
    
    # No match found
    print(f"    Warning: No transit ID found for '{transit_name}'")
    return None


def _infer_transit_mode(row: pd.Series, transit_ids: Dict[str, int]) -> Optional[int]:
    """Infer the transit mode from row data.
    
    This function is designed to work with both:
    1. Data that includes a Category column (from existing CSVs)
    2. Data without a Category column (from future OCR'd PDFs)
    
    Args:
        row: The row from the dataframe
        transit_ids: Dictionary of transit mode names to IDs
        
    Returns:
        The transit mode ID or None if it can't be determined
    """
    # First check if Category is available and valid
    if not pd.isna(row.get('Category')):
        category = row['Category']
        
        # Skip transaction types that aren't transit modes
        if category in ['Reload', 'Pass Purchase']:
            return None
            
        # Try to get transit ID from category
        for transit_name, transit_id in transit_ids.items():
            # Check if the transit name is in the category
            if transit_name in category:
                return transit_id
                
            # Handle special cases like "BART Exit" -> "BART"
            if category.startswith(f"{transit_name} "):
                return transit_id
    
    # If no category or no match, try to infer from location
    if not pd.isna(row.get('Location')):
        location = row['Location']
        
        # Check for specific location patterns
        if 'BART' in location:
            return transit_ids.get('BART')
        if 'SFM bus' in location:
            return transit_ids.get('Muni Bus')
        if 'Muni' in location:
            return transit_ids.get('Muni Metro')
        if 'Caltrain' in location or '4th and King' in location or 'Palo Alto' in location:
            return transit_ids.get('Caltrain')
        if 'Ferry' in location:
            return transit_ids.get('Ferry')
        if 'AC Transit' in location:
            return transit_ids.get('AC Transit')
        if 'SamTrans' in location:
            return transit_ids.get('SamTrans')
        if 'Cable Car' in location:
            return transit_ids.get('Cable Car')
        
        # Check for transit mode names in location as a fallback
        for transit_name, transit_id in transit_ids.items():
            if transit_name in location:
                return transit_id
    
    # If still no match, try to infer from transaction type and other fields
    transaction_type = row.get('Transaction Type', '')
    
    # Check for reload transactions
    if 'reload' in transaction_type.lower():
        return None  # Reloads don't have a transit mode
        
    # Check for specific transaction patterns
    if 'fare payment' in transaction_type.lower():
        if 'SFM' in row.get('Location', ''):
            return transit_ids.get('Muni Bus')
    
    # Check product field as a last resort
    if not pd.isna(row.get('Product')):
        product = row['Product']
        if 'BART' in product:
            return transit_ids.get('BART')
        if 'Caltrain' in product:
            return transit_ids.get('Caltrain')
    
    return None


def _map_transaction_type(row: pd.Series) -> str:
    """Map the raw transaction data to a standardized TransactionType enum value.
    
    Args:
        row: A row from the transaction dataframe
        
    Returns:
        A standardized transaction type from the TransactionType enum
    """
    transaction_type = row.get('Transaction Type', '')
    category = row.get('Category', '')
    
    # Handle reload transactions first
    if 'reload' in transaction_type.lower() or (not pd.isna(category) and 'reload' in category.lower()):
        return TransactionType.RELOAD
    
    # Handle pass purchases
    if 'pass' in transaction_type.lower() or (not pd.isna(category) and 'pass' in category.lower()):
        return TransactionType.PASS_PURCHASE
    
    # Handle entry transactions
    if 'entry transaction' in transaction_type.lower() or (not pd.isna(category) and 'entrance' in category.lower()):
        return TransactionType.ENTRY
    
    # Handle exit transactions
    if 'exit transaction' in transaction_type.lower() or (not pd.isna(category) and 'exit' in category.lower()):
        return TransactionType.EXIT
    
    # Handle single-tag fare payments (common for Muni Bus, etc.)
    if 'single-tag fare payment' in transaction_type.lower():
        return TransactionType.ENTRY
    
    # Handle manual entry transactions
    if 'manual' in transaction_type.lower():
        return TransactionType.MANUAL
    
    # Default to manual if we can't determine
    return TransactionType.MANUAL


def _save_rider_data(client, rider_id: str, df: pd.DataFrame, transit_ids: Dict[str, int]) -> None:
    """Save a rider's data to Supabase."""
    # Get existing trip data to determine what to insert/update
    print(f"    Getting existing trips for rider {rider_id}...")
    existing_trips = _get_existing_trips(client, rider_id)
    print(f"    Found {len(existing_trips)} existing trips")
    
    # Process the dataframe into trips
    print(f"    Processing {len(df)} transactions...")
    
    # Add a progress counter
    processed = 0
    errors = 0
    
    # Process in smaller batches to avoid overwhelming the API
    BATCH_SIZE = 20
    total_rows = len(df)
    
    for batch_start in range(0, total_rows, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_rows)
        print(f"    Processing batch {batch_start//BATCH_SIZE + 1}/{(total_rows + BATCH_SIZE - 1)//BATCH_SIZE}...")
        
        batch_df = df.iloc[batch_start:batch_end]
        
        for _, row in batch_df.iterrows():
            # Skip if transaction date is missing
            if pd.isna(row['Transaction Date']):
                continue
                
            # Get the transit ID
            transit_id = _infer_transit_mode(row, transit_ids)
            
            # Create trip record
            trip = {
                "rider_id": rider_id,
                "transit_id": transit_id,
                "transaction_type": row.get('Transaction Type', ''),
                "transaction_date": row['Transaction Date'].isoformat(),
                "location": None if pd.isna(row.get('Location')) else row.get('Location'),
                "route": None if pd.isna(row.get('Route')) else row.get('Route'),
                "debit": None if pd.isna(row.get('Debit')) else row.get('Debit'),
                "credit": None if pd.isna(row.get('Credit')) else row.get('Credit'),
                "balance": None if pd.isna(row.get('Balance')) else row.get('Balance'),
                "product": None if pd.isna(row.get('Product')) else row.get('Product'),
            }
            
            # Check if trip already exists by matching transaction date and type
            transaction_date = row['Transaction Date'].isoformat()
            transaction_type = row.get('Transaction Type', '')
            
            existing_id = existing_trips.get((transaction_date, transaction_type))
            
            try:
                if existing_id:
                    # Update existing trip
                    result = execute_with_timeout(
                        lambda: client.table("trips").update(trip).eq("id", existing_id).execute(),
                        timeout=10
                    )
                else:
                    # Insert new trip
                    result = execute_with_timeout(
                        lambda: client.table("trips").insert(trip).execute(),
                        timeout=10
                    )
                
                if result:
                    processed += 1
                    if processed % 10 == 0:
                        print(f"    Processed {processed}/{total_rows} transactions...")
                else:
                    print(f"    Timed out processing transaction: {transaction_date}")
                    errors += 1
            except Exception as e:
                print(f"    Error processing transaction {transaction_date}: {e}")
                errors += 1
    
    print(f"    Completed processing {processed}/{total_rows} transactions with {errors} errors")
    return processed


def _get_existing_trips(client, rider_id: str) -> Dict[Tuple[str, str], int]:
    """Get existing trips with their IDs for a rider."""
    result = execute_with_timeout(
        lambda: client.table("trips")
                .select("id, transaction_date, transaction_type")
                .eq("rider_id", rider_id)
                .execute(),
        timeout=15
    )
    
    if result is None:
        print(f"    Timed out getting existing trips for rider {rider_id}")
        return {}
    
    # Map (transaction_date, transaction_type) -> id
    return {
        (trip['transaction_date'], trip['transaction_type']): trip['id']
        for trip in result.data
    }


def clear_trips_table(client, rider_ids=None):
    """Clear the trips table for specified riders or all riders.
    
    Args:
        client: Supabase client
        rider_ids (Optional[List[str]]): List of rider IDs to clear, or None for all
    """
    try:
        if rider_ids:
            print(f"Clearing trips for riders: {', '.join(rider_ids)}")
            for rider_id in rider_ids:
                print(f"  Clearing trips for rider {rider_id}...")
                result = execute_with_timeout(
                    lambda: client.table("trips").delete().eq("rider_id", rider_id).execute(),
                    timeout=30
                )
                if result:
                    print(f"  Deleted {len(result.data)} trips for rider {rider_id}")
                else:
                    print(f"  Timed out deleting trips for rider {rider_id}")
        else:
            print("Clearing all trips from the database...")
            try:
                # Supabase requires a WHERE clause for DELETE operations
                # Use a condition that's always true to delete all records
                result = execute_with_timeout(
                    lambda: client.table("trips").delete().neq("id", 0).execute(),
                    timeout=60
                )
                if result:
                    print(f"Deleted {len(result.data)} trips")
                else:
                    print("Timed out deleting trips")
            except Exception as e:
                print(f"Operation failed: {e}")
                print("Trying alternative approach...")
                
                # Get all rider IDs and delete trips for each rider
                riders_result = client.table("riders").select("id").execute()
                if riders_result and riders_result.data:
                    for rider in riders_result.data:
                        rider_id = rider['id']
                        print(f"  Clearing trips for rider {rider_id}...")
                        try:
                            result = execute_with_timeout(
                                lambda: client.table("trips").delete().eq("rider_id", rider_id).execute(),
                                timeout=30
                            )
                            if result:
                                print(f"  Deleted {len(result.data)} trips for rider {rider_id}")
                            else:
                                print(f"  Timed out deleting trips for rider {rider_id}")
                        except Exception as e:
                            print(f"  Error deleting trips for rider {rider_id}: {e}")
                else:
                    print("Could not retrieve rider IDs. Delete operation failed.")
                    return False
    except Exception as e:
        print(f"Error clearing trips: {e}")
        return False
    
    return True


def migrate_all_riders(riders: Optional[List[str]] = None, clear_tables: bool = False) -> None:
    """Migrate all riders' data from GCS to Supabase.
    
    Args:
        riders (Optional[List[str]]): List of rider IDs to migrate, or None for all
        clear_tables (bool): Whether to clear existing trips before migration
    """
    # Check connection and setup
    if not check_supabase_connection():
        print("Migration aborted due to connection issues.")
        return
    
    # Initialize the Supabase database once
    print("Initializing database (one-time setup)...")
    initialize_database()
    
    # Get a single client to use for all operations
    client = get_supabase_client()
    
    # Clear tables if requested
    if clear_tables:
        if not clear_trips_table(client, riders):
            print("Failed to clear trips table. Aborting migration.")
            return
    
    # Create GCS store
    gcs_store = GCSDataStore()
    
    # Use riders from config if none provided
    if riders is None:
        riders = config.riders
    
    print(f"Starting migration for {len(riders)} riders: {', '.join(riders)}")
    
    # Migrate each rider's data
    total_transactions = 0
    for rider_id in tqdm(riders, desc="Migrating riders"):
        print(f"\nProcessing rider: {rider_id}")
        transactions = migrate_rider_data(rider_id, gcs_store, supabase_client=client)
        total_transactions += transactions
        # Small pause to avoid overwhelming the API
        time.sleep(0.5)
    
    print(f"Migration complete. Migrated {total_transactions} transactions for {len(riders)} riders.")


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(description="Migrate data from GCS to Supabase")
    parser.add_argument(
        "--riders", 
        nargs="+", 
        help="Rider IDs to migrate (defaults to all riders in config)"
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only show setup instructions without attempting migration"
    )
    parser.add_argument(
        "--clear-tables",
        action="store_true",
        help="Clear existing trips before migration"
    )
    args = parser.parse_args()
    
    if args.setup_only:
        check_supabase_connection()
        setup_tables(interactive=False)
        return 0
        
    # For interactive mode, guide the user through setup
    interactive_mode = sys.stdout.isatty()  # Check if running in a terminal
    if interactive_mode:
        setup_result = setup_tables(interactive=True)
        if not setup_result:
            print("Migration aborted. Please create the required tables first.")
            print("Run with --setup-only to see setup instructions.")
            return 1
    else:
        # In non-interactive mode, assume tables are set up
        print("Non-interactive mode: assuming tables are already set up")
    
    # Migrate all riders
    migrate_all_riders(args.riders, clear_tables=args.clear_tables)
    return 0


class TimeoutException(Exception):
    pass

@contextmanager
def time_limit(seconds):
    """Context manager to limit execution time of a block of code."""
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def execute_with_timeout(operation, timeout=30):
    """Execute a Supabase operation with a timeout.
    
    Args:
        operation: A callable that performs a Supabase operation
        timeout: Timeout in seconds
        
    Returns:
        The result of the operation or None if it times out
    """
    try:
        with time_limit(timeout):
            return operation()
    except TimeoutException:
        print(f"Operation timed out after {timeout} seconds!")
        return None
    except Exception as e:
        print(f"Operation failed: {e}")
        return None


if __name__ == "__main__":
    sys.exit(main())