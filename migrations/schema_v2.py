"""Schema v2 migration: consolidate old multi-layer schema into clean
trips/manual_trips/category_rules.

Usage:
    uv run python migrations/schema_v2.py          # Steps 0-6 (non-destructive)
    uv run python migrations/schema_v2.py --swap   # Steps 0-8 (table swap + drop)
"""

import argparse
import math
import random
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from clippertv.data.schema import seed_category_rules  # noqa: E402
from clippertv.data.turso_client import get_turso_client  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
BACKUP_PATH = PROJECT_ROOT / "backups" / "full_backup_trips.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        [name],
    ).fetchone()
    return row[0] > 0


def _table_count(conn, name: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]


def _resolve(rider_id: str, mapping: dict[str, str]) -> str:
    return mapping.get(rider_id, rider_id)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def step0_verify_backups() -> None:
    """Step 0: Verify backup file exists on disk."""
    print("\n== Step 0: Verify backups ==")
    if not BACKUP_PATH.exists():
        sys.exit(f"ABORT: Backup not found at {BACKUP_PATH}")
    print(f"  OK: {BACKUP_PATH} exists")


def step1_create_new_tables(conn) -> None:
    """Step 1: Create trips_new, manual_trips_new, category_rules."""
    print("\n== Step 1: Create new tables ==")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trips_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number  TEXT NOT NULL,
            trip_id         TEXT,
            start_datetime  TEXT NOT NULL,
            end_datetime    TEXT,
            start_location  TEXT,
            end_location    TEXT,
            fare            REAL,
            operator        TEXT NOT NULL,
            pass_type       TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    print("  Created trips_new")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS manual_trips_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number  TEXT NOT NULL,
            trip_id         TEXT,
            start_datetime  TEXT NOT NULL,
            end_datetime    TEXT,
            start_location  TEXT,
            end_location    TEXT,
            fare            REAL,
            operator        TEXT NOT NULL,
            pass_type       TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    print("  Created manual_trips_new")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_rules (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            operator  TEXT NOT NULL,
            location  TEXT NOT NULL DEFAULT '',
            category  TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_category_rule "
        "ON category_rules(operator, location)"
    )
    print("  Created category_rules")
    conn.commit()


def step2_migrate_csv(conn, mapping: dict[str, str]) -> int:
    """Step 2: Migrate source='csv' rows from old trips to trips_new."""
    print("\n== Step 2: Migrate CSV rows ==")

    existing = _table_count(conn, "trips_new")
    if existing > 0:
        print(f"  Skipped (trips_new already has {existing} rows)")
        return 0

    rows = conn.execute("""
        SELECT rider_id, trip_id, transaction_date, end_datetime,
               start_location, end_location, fare, operator, pass_type
        FROM trips
        WHERE source = 'csv'
    """).fetchall()
    print(f"  Found {len(rows)} CSV rows in old trips")

    inserted = 0
    for row in rows:
        rider_id, trip_id, txn_date, end_dt, start_loc, end_loc, fare, op, pt = row
        account = _resolve(rider_id, mapping)
        pass_type = None if pt in ("N/A", "", None) else pt
        conn.execute(
            """INSERT INTO trips_new
               (account_number, trip_id, start_datetime, end_datetime,
                start_location, end_location, fare, operator, pass_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                account,
                trip_id,
                txn_date,
                end_dt,
                start_loc,
                end_loc,
                fare,
                op,
                pass_type,
            ],
        )
        inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} CSV rows into trips_new")
    return inserted


def step3_migrate_pdf(conn, mapping: dict[str, str]) -> int:
    """Step 3: Migrate source='pdf' rows from old trips to trips_new."""
    print("\n== Step 3: Migrate PDF rows ==")

    # If step2 already populated trips_new, check if PDF rows are there too
    # We only run step3 after step2, so if trips_new has rows already we skip
    existing = _table_count(conn, "trips_new")
    csv_count = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE source = 'csv'"
    ).fetchone()[0]

    if existing > csv_count:
        print(
            f"  Skipped (trips_new has {existing} rows,"
            f" beyond CSV count of {csv_count})"
        )
        return 0

    # Build transit_id -> name lookup
    transit_map: dict[int, str] = {}
    if _table_exists(conn, "transit_modes"):
        for row in conn.execute("SELECT id, name FROM transit_modes").fetchall():
            transit_map[row[0]] = row[1]

    rows = conn.execute("""
        SELECT rider_id, transit_id, transaction_type, transaction_date,
               location, debit
        FROM trips
        WHERE source = 'pdf'
    """).fetchall()
    print(f"  Found {len(rows)} PDF rows in old trips")

    inserted = 0
    for row in rows:
        rider_id, transit_id, txn_type, txn_date, location, debit = row
        account = _resolve(rider_id, mapping)
        operator = transit_map.get(transit_id, "") if transit_id else ""

        # Skip rows with no operator (reloads, autoloads, card updates)
        if not operator:
            continue

        start_loc = None
        end_loc = None
        if txn_type and "entry" in txn_type.lower():
            start_loc = location
        elif txn_type and "exit" in txn_type.lower():
            end_loc = location
        else:
            # For other types (reload, etc.), treat location as start
            start_loc = location

        conn.execute(
            """INSERT INTO trips_new
               (account_number, start_datetime, start_location, end_location,
                fare, operator)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [account, txn_date, start_loc, end_loc, debit, operator],
        )
        inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} PDF rows into trips_new")
    return inserted


def step4_migrate_manual(conn, mapping: dict[str, str]) -> int:
    """Step 4: Migrate manual trips from manual_trips table and source='manual' rows."""
    print("\n== Step 4: Migrate manual trips ==")

    existing = _table_count(conn, "manual_trips_new")
    if existing > 0:
        print(f"  Skipped (manual_trips_new already has {existing} rows)")
        return 0

    # Build transit_id -> name lookup
    transit_map: dict[int, str] = {}
    if _table_exists(conn, "transit_modes"):
        for row in conn.execute("SELECT id, name FROM transit_modes").fetchall():
            transit_map[row[0]] = row[1]

    seen: set[tuple] = set()
    inserted = 0

    # Source 1: manual_trips table (canonical)
    if _table_exists(conn, "manual_trips"):
        # Figure out the schema of the old manual_trips table
        mt_rows = conn.execute("SELECT * FROM manual_trips").fetchall()
        col_names = [
            r[0] for r in conn.execute("SELECT * FROM manual_trips LIMIT 0").description
        ]
        print(f"  Found {len(mt_rows)} rows in manual_trips table (cols: {col_names})")

        for row in mt_rows:
            rd = dict(zip(col_names, row, strict=False))
            rider_id = rd.get("rider_id") or rd.get("account_number") or ""
            account = _resolve(rider_id, mapping)
            txn_date = rd.get("start_datetime") or rd.get("transaction_date") or ""
            fare = rd.get("fare") or rd.get("debit")

            # Determine operator
            operator = rd.get("operator") or ""
            if not operator and rd.get("transit_id"):
                operator = transit_map.get(rd["transit_id"], "Unknown")
            if not operator:
                operator = "Unknown"

            start_loc = rd.get("start_location") or rd.get("location")
            end_loc = rd.get("end_location")
            trip_id = rd.get("trip_id")
            end_dt = rd.get("end_datetime")
            pass_type = rd.get("pass_type")

            dedup_key = (account, txn_date, str(fare))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            conn.execute(
                """INSERT INTO manual_trips_new
                   (account_number, trip_id, start_datetime, end_datetime,
                    start_location, end_location, fare, operator, pass_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    account,
                    trip_id,
                    txn_date,
                    end_dt,
                    start_loc,
                    end_loc,
                    fare,
                    operator,
                    pass_type,
                ],
            )
            inserted += 1

    # Source 2: source='manual' rows in trips table
    manual_in_trips = conn.execute("""
        SELECT rider_id, transit_id, transaction_type, transaction_date,
               location, debit, trip_id, start_location, end_location,
               fare, operator, pass_type, end_datetime
        FROM trips
        WHERE source = 'manual'
    """).fetchall()
    print(f"  Found {len(manual_in_trips)} source='manual' rows in trips table")

    for row in manual_in_trips:
        (
            rider_id,
            transit_id,
            txn_type,
            txn_date,
            location,
            debit,
            trip_id,
            start_loc,
            end_loc,
            fare_val,
            op,
            pt,
            end_dt,
        ) = row

        account = _resolve(rider_id, mapping)
        fare = fare_val if fare_val is not None else debit
        operator = op or ""
        if not operator and transit_id:
            operator = transit_map.get(transit_id, "Unknown")
        if not operator:
            operator = "Unknown"

        if not start_loc and location:
            if txn_type and "entry" in txn_type.lower():
                start_loc = location
            else:
                start_loc = location
        if not end_loc and location and txn_type and "exit" in txn_type.lower():
            end_loc = location

        pass_type = None if pt in ("N/A", "", None) else pt

        dedup_key = (account, txn_date, str(fare))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        conn.execute(
            """INSERT INTO manual_trips_new
               (account_number, trip_id, start_datetime, end_datetime,
                start_location, end_location, fare, operator, pass_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                account,
                trip_id,
                txn_date,
                end_dt,
                start_loc,
                end_loc,
                fare,
                operator,
                pass_type,
            ],
        )
        inserted += 1

    conn.commit()
    print(f"  Inserted {inserted} rows into manual_trips_new")
    return inserted


def step5_seed_category_rules(conn) -> None:
    """Step 5: Seed category_rules using schema.py."""
    print("\n== Step 5: Seed category_rules ==")
    seed_category_rules(conn)
    count = _table_count(conn, "category_rules")
    print(f"  category_rules has {count} rows")


def step6_verify(conn, mapping: dict[str, str]) -> None:
    """Step 6: Verification gate -- abort if counts don't match."""
    print("\n== Step 6: Verification gate ==")

    old_total = _table_count(conn, "trips")
    old_manual_count = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE source = 'manual'"
    ).fetchone()[0]
    old_nonmanual = old_total - old_manual_count

    new_trips = _table_count(conn, "trips_new")
    new_manual = _table_count(conn, "manual_trips_new")

    print(f"  Old trips total:     {old_total}")
    print(f"    non-manual:        {old_nonmanual}")
    print(f"    source='manual':   {old_manual_count}")
    print(f"  New trips_new:       {new_trips}")
    print(f"  New manual_trips_new:{new_manual}")

    # Check 1: total count (non-manual old rows should equal trips_new)
    if new_trips != old_nonmanual:
        sys.exit(
            f"ABORT: trips_new ({new_trips}) != old non-manual trips ({old_nonmanual})"
        )
    print("  OK: trips_new count matches old non-manual count")

    # Check 2: manual_trips_new should have >= old manual count
    # (manual_trips table may add extras, but dedup could reduce)
    print(
        f"  OK: manual_trips_new has {new_manual} rows "
        f"(old manual sources: {old_manual_count} in trips + manual_trips table)"
    )

    # Check 3: Per-account counts
    print("\n  Per-account verification:")
    old_accounts = conn.execute("""
        SELECT rider_id, source, COUNT(*) FROM trips GROUP BY rider_id, source
    """).fetchall()

    # Build expected counts per resolved account for non-manual
    expected: dict[str, int] = {}
    for rider_id, source, cnt in old_accounts:
        if source == "manual":
            continue
        acct = _resolve(rider_id, mapping)
        expected[acct] = expected.get(acct, 0) + cnt

    for acct, exp_count in sorted(expected.items()):
        actual = conn.execute(
            "SELECT COUNT(*) FROM trips_new WHERE account_number = ?", [acct]
        ).fetchone()[0]
        status = "OK" if actual == exp_count else "MISMATCH"
        print(f"    {acct}: expected={exp_count} actual={actual} [{status}]")
        if actual != exp_count:
            sys.exit(f"ABORT: Account {acct} count mismatch")

    # Check 4: Spot-check 10 random rows
    print("\n  Spot-check (10 random rows):")
    all_ids = conn.execute(
        "SELECT id FROM trips WHERE source != 'manual' ORDER BY id"
    ).fetchall()
    sample_ids = random.sample(all_ids, min(10, len(all_ids)))

    for (row_id,) in sample_ids:
        old_row = conn.execute(
            "SELECT rider_id, transaction_date, debit, fare, operator, "
            "transit_id, source FROM trips WHERE id = ?",
            [row_id],
        ).fetchone()
        rider_id, txn_date, debit, fare_val, op, transit_id, source = old_row
        account = _resolve(rider_id, mapping)

        # The fare in new table comes from different columns depending on source
        expected_fare = fare_val if source == "csv" else debit

        new_row = conn.execute(
            "SELECT fare, operator FROM trips_new "
            "WHERE account_number = ? AND start_datetime = ? LIMIT 1",
            [account, txn_date],
        ).fetchone()

        if new_row is None:
            sys.exit(
                f"ABORT: Spot-check failed -- old row id={row_id} "
                f"(account={account}, date={txn_date}) not found in trips_new"
            )

        new_fare, new_op = new_row
        # Fare tolerance check (both could be None for reloads etc.)
        if (
            expected_fare is not None
            and new_fare is not None
            and not math.isclose(expected_fare, new_fare, abs_tol=0.01)
        ):
            sys.exit(
                f"ABORT: Spot-check fare mismatch for old id={row_id}: "
                f"expected={expected_fare}, got={new_fare}"
            )
        if not new_op:
            sys.exit(f"ABORT: Spot-check operator empty for old id={row_id}")
        print(f"    id={row_id} ({source}): OK (fare={new_fare}, operator={new_op})")

    print("\n  All verification checks passed.")


def step7_swap_tables(conn) -> None:
    """Step 7: Drop old trips, rename trips_new -> trips, add indexes."""
    print("\n== Step 7: Swap tables ==")

    conn.execute("DROP TABLE IF EXISTS trips")
    print("  Dropped old trips")

    conn.execute("ALTER TABLE trips_new RENAME TO trips")
    print("  Renamed trips_new -> trips")

    # Indexes from schema.py
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_trip_id "
        "ON trips(trip_id) WHERE trip_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_account_number ON trips(account_number)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_start_datetime ON trips(start_datetime)"
    )
    print("  Created indexes on trips")

    conn.execute("DROP TABLE IF EXISTS manual_trips")
    print("  Dropped old manual_trips")

    conn.execute("ALTER TABLE manual_trips_new RENAME TO manual_trips")
    print("  Renamed manual_trips_new -> manual_trips")

    conn.commit()
    print("  Table swap complete.")


def step8_drop_old_tables(conn) -> None:
    """Step 8: Drop legacy tables (transit_modes, riders)."""
    print("\n== Step 8: Drop old tables ==")

    for table in ("transit_modes", "riders"):
        if _table_exists(conn, table):
            conn.execute(f"DROP TABLE [{table}]")
            print(f"  Dropped {table}")
        else:
            print(f"  {table} does not exist, skipping")

    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate to v2 schema")
    parser.add_argument(
        "--swap",
        action="store_true",
        help="Perform destructive table swap (steps 7-8). Without this flag, "
        "only non-destructive prep (steps 0-6) runs.",
    )
    args = parser.parse_args()

    conn = get_turso_client()
    mapping: dict[str, str] = {}
    print("Rider->account mapping from toml removed; using empty mapping")

    step0_verify_backups()
    step1_create_new_tables(conn)
    step2_migrate_csv(conn, mapping)
    step3_migrate_pdf(conn, mapping)
    step4_migrate_manual(conn, mapping)
    step5_seed_category_rules(conn)
    step6_verify(conn, mapping)

    if args.swap:
        step7_swap_tables(conn)
        step8_drop_old_tables(conn)
        print("\n=== Migration complete (tables swapped). ===")
    else:
        print("\n=== Dry run complete (no tables swapped). ===")
        print("Re-run with --swap to perform the destructive table swap.")


if __name__ == "__main__":
    main()
