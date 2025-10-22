"""Migration script from Supabase backup to Turso database."""

import argparse
import sys
from pathlib import Path

from clippertv.data.turso_client import get_turso_client, initialize_database


def parse_copy_value(val: str):
    """Parse a PostgreSQL COPY value."""
    if val == "\\N":
        return None
    # Remove quotes if present
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    # Try to convert to number
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val


def migrate_from_backup(backup_file: Path, dry_run: bool = False) -> None:
    """Migrate data from Supabase backup file to Turso.

    Args:
        backup_file: Path to Supabase backup file (.backup)
        dry_run: If True, print what would be done without executing
    """
    if not backup_file.exists():
        print(f"Error: Backup file not found: {backup_file}")
        sys.exit(1)

    print(f"Reading backup file: {backup_file}")

    # Initialize Turso database
    if not dry_run:
        print("Initializing Turso database...")
        initialize_database()
        conn = get_turso_client()
    else:
        print("[DRY RUN] Would initialize Turso database")
        conn = None

    # Track what we're inserting
    stats = {"riders": 0, "transit_modes": 0, "trips": 0}

    # Read and process backup file
    current_table = None
    with open(backup_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip("\n")

            # Check for COPY statements
            if line.startswith("COPY public.riders"):
                current_table = "riders"
                print(f"Found riders data at line {line_num}")
                continue
            elif line.startswith("COPY public.transit_modes"):
                current_table = "transit_modes"
                print(f"Found transit_modes data at line {line_num}")
                continue
            elif line.startswith("COPY public.trips"):
                current_table = "trips"
                print(f"Found trips data at line {line_num}")
                continue

            # Check for end of COPY data
            if line == "\\.":
                print(f"Completed {current_table}")
                if not dry_run and current_table == "trips":
                    # Commit after each table
                    conn.commit()
                current_table = None
                continue

            # Process data lines
            if current_table:
                values = [parse_copy_value(v) for v in line.split("\t")]

                if current_table == "riders":
                    # riders: id, name, email, created_at, updated_at
                    rider_id, name, email = values[0], values[1], values[2]
                    if dry_run:
                        print(f"  [DRY RUN] Would insert rider: {rider_id}")
                    else:
                        try:
                            conn.execute(
                                "INSERT OR IGNORE INTO riders (id, name, email) VALUES (?, ?, ?)",
                                [rider_id, name, email]
                            )
                            stats["riders"] += 1
                        except Exception as e:
                            print(f"  Error inserting rider {rider_id}: {e}")

                elif current_table == "transit_modes":
                    # transit_modes: id, name, display_name, color, created_at, updated_at
                    tm_id, name, display_name, color = values[0], values[1], values[2], values[3]
                    if dry_run:
                        print(f"  [DRY RUN] Would insert transit mode: {name}")
                    else:
                        try:
                            conn.execute(
                                "INSERT OR REPLACE INTO transit_modes (id, name, display_name, color) VALUES (?, ?, ?, ?)",
                                [tm_id, name, display_name, color]
                            )
                            stats["transit_modes"] += 1
                        except Exception as e:
                            print(f"  Error inserting transit mode {name}: {e}")

                elif current_table == "trips":
                    # trips: id, rider_id, transit_id, transaction_type, transaction_date,
                    #        location, route, debit, credit, balance, product, created_at, updated_at
                    (trip_id, rider_id, transit_id, transaction_type, transaction_date,
                     location, route, debit, credit, balance, product) = values[:11]

                    if dry_run:
                        if stats["trips"] < 5:  # Only print first 5
                            print(f"  [DRY RUN] Would insert trip for rider {rider_id} on {transaction_date}")
                    else:
                        try:
                            conn.execute("""
                                INSERT OR IGNORE INTO trips (
                                    rider_id, transit_id, transaction_type, transaction_date,
                                    location, route, debit, credit, balance, product
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, [rider_id, transit_id, transaction_type, transaction_date,
                                  location, route, debit, credit, balance, product])
                            stats["trips"] += 1

                            # Commit every 100 trips for performance and progress update
                            if stats["trips"] % 100 == 0:
                                conn.commit()
                                print(f"  Migrated {stats['trips']} trips...")
                        except Exception as e:
                            print(f"  Error inserting trip {trip_id}: {e}")

    # Final commit
    if not dry_run:
        print("\nCommitting to Turso...")
        conn.commit()

    # Print summary
    print("\n" + "=" * 50)
    print("Migration Summary:")
    print(f"  Riders inserted: {stats['riders']}")
    print(f"  Transit modes inserted: {stats['transit_modes']}")
    print(f"  Trips inserted: {stats['trips']}")
    print("=" * 50)

    if dry_run:
        print("\n[DRY RUN] No data was actually written to Turso")
    else:
        print("\n✓ Migration complete!")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate data from Supabase backup to Turso"
    )
    parser.add_argument(
        "backup_file",
        nargs="?",
        default="db_cluster-25-03-2025@15-23-49.backup",
        help="Path to Supabase backup file (default: db_cluster-25-03-2025@15-23-49.backup)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test run without actually writing to Turso"
    )

    args = parser.parse_args()

    backup_path = Path(args.backup_file)
    migrate_from_backup(backup_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
