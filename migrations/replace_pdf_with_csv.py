"""One-time migration: replace PDF data (2023+) with CSV downloads.

Re-runnable: each step checks if already completed before executing.
Requires env vars: TURSO_DATABASE_URL, TURSO_AUTH_TOKEN
"""

import csv
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clippertv.data.turso_client import (  # noqa: E402
    get_turso_client,
    initialize_database,
)

# Pattern 1: Midnight placeholder rows (Caltrain pass days, one-off transit entries)
_MIDNIGHT_PLACEHOLDER_QUERY = """
    SELECT * FROM trips
    WHERE TIME(transaction_date) = '00:00:00'
      AND location IS NULL
      AND debit IS NULL
      AND credit IS NULL
      AND product IS NULL
      AND source = 'pdf'
"""

# Pattern 2: Unique transaction_type='manual' rows
# (hand-entered rides with no entry twin)
_UNIQUE_MANUAL_TYPE_QUERY = """
    SELECT * FROM trips m
    WHERE m.transaction_type = 'manual'
      AND m.source = 'pdf'
      AND NOT EXISTS (
          SELECT 1 FROM trips e
          WHERE e.rider_id = m.rider_id
            AND e.transaction_date = m.transaction_date
            AND e.location = m.location
            AND e.transaction_type = 'entry'
      )
"""

EXPECTED_MANUAL_COUNT = 74  # 67 midnight placeholders + 7 unique manual-type rows
EXPECTED_PDF_2023_COUNT = 4204
BACKUP_PATH = Path(__file__).parent.parent / "backups" / "pdf_trips_2023_plus.csv"


def get_column_names(conn) -> list[str]:
    """Get column names from trips table."""
    return [row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()]


def _query_all_manual_rows(conn) -> list:
    """Query both patterns of manual rows, deduplicated by id."""
    midnight_rows = conn.execute(_MIDNIGHT_PLACEHOLDER_QUERY).fetchall()
    unique_manual_rows = conn.execute(_UNIQUE_MANUAL_TYPE_QUERY).fetchall()
    # Deduplicate by id (column 0) in case any row matches both patterns
    seen = set()
    result = []
    for row in midnight_rows + unique_manual_rows:
        if row[0] not in seen:
            seen.add(row[0])
            result.append(row)
    return result


def step0_preflight(conn) -> bool:
    """Pre-flight checks: verify manual row count and check for anomalies.

    Adapts to post-deletion state: if PDF 2023+ rows are already gone
    (Step 4 ran), skips those checks since manual_trips backup exists.
    """
    print("\n=== Step 0: Pre-flight checks ===")

    pdf_2023_count = conn.execute(
        "SELECT COUNT(*) FROM trips"
        " WHERE source = 'pdf' AND transaction_date >= '2023-01-01'"
    ).fetchone()[0]
    already_deleted = pdf_2023_count == 0

    if already_deleted:
        try:
            manual_backup = conn.execute(
                "SELECT COUNT(*) FROM manual_trips"
            ).fetchone()[0]
            print(f"  Post-deletion re-run: manual_trips has {manual_backup} rows")
            if manual_backup != EXPECTED_MANUAL_COUNT:
                print(f"  ERROR: Expected {EXPECTED_MANUAL_COUNT}")
                return False
            print("  OK: Skipping PDF checks (already deleted)")
            return True
        except Exception:
            print("  ERROR: PDF rows deleted but manual_trips table missing!")
            return False

    # First run: full pre-flight checks
    manual_rows = _query_all_manual_rows(conn)
    print(f"  Manual rows found: {len(manual_rows)}")
    if len(manual_rows) != EXPECTED_MANUAL_COUNT:
        print(f"  ERROR: Expected {EXPECTED_MANUAL_COUNT}, got {len(manual_rows)}")
        return False
    print(f"  OK: {EXPECTED_MANUAL_COUNT} manual rows match expected count")

    anomalies = conn.execute("""
        SELECT transaction_type, COUNT(*) FROM trips
        WHERE source = 'pdf' AND transaction_date >= '2023-01-01'
          AND transaction_type NOT IN (
              'entry', 'exit', 'reload', 'manual',
              'Single-tag fare payment',
              'Dual-tag entry transaction, maximum fare deducted (purse debit)'
          )
        GROUP BY transaction_type
    """).fetchall()
    if anomalies:
        print("  WARNING: Unexpected transaction types in 2023+ PDF data:")
        for row in anomalies:
            print(f"    {row[0]}: {row[1]} rows")
        return False
    print("  OK: No anomalous transaction types")

    print(f"  PDF rows 2023+: {pdf_2023_count}")
    if pdf_2023_count != EXPECTED_PDF_2023_COUNT:
        print(f"  WARNING: Expected {EXPECTED_PDF_2023_COUNT}, got {pdf_2023_count}")
        print("  Update EXPECTED_PDF_2023_COUNT if this is correct, then re-run")
        return False
    print(f"  OK: {EXPECTED_PDF_2023_COUNT} PDF rows match expected count")

    return True


def step1_export_manual_trips(conn) -> bool:
    """Export manual rows to manual_trips table."""
    print("\n=== Step 1: Export manual trips → manual_trips table ===")

    try:
        existing = conn.execute("SELECT COUNT(*) FROM manual_trips").fetchone()[0]
        if existing == EXPECTED_MANUAL_COUNT:
            print(f"  SKIP: manual_trips already has {existing} rows")
            return True
        elif existing > 0:
            print(
                f"  WARNING: manual_trips has {existing} rows,"
                f" expected {EXPECTED_MANUAL_COUNT}"
            )
            return False
    except Exception:
        pass

    columns = get_column_names(conn)
    col_defs = conn.execute("PRAGMA table_info(trips)").fetchall()
    create_cols = []
    for col in col_defs:
        name, dtype, notnull, default, pk = col[1], col[2], col[3], col[4], col[5]
        parts = [name, dtype]
        if pk:
            parts.append("PRIMARY KEY AUTOINCREMENT")
        if notnull and not pk:
            parts.append("NOT NULL")
        if default is not None and not pk:
            parts.append(f"DEFAULT {default}")
        create_cols.append(" ".join(parts))

    conn.execute(f"CREATE TABLE IF NOT EXISTS manual_trips ({', '.join(create_cols)})")

    manual_rows = _query_all_manual_rows(conn)
    placeholders = ", ".join(["?"] * len(columns))
    for row in manual_rows:
        conn.execute(
            f"INSERT INTO manual_trips ({', '.join(columns)}) VALUES ({placeholders})",
            list(row),
        )
    conn.commit()

    inserted = conn.execute("SELECT COUNT(*) FROM manual_trips").fetchone()[0]
    print(f"  Inserted {inserted} rows into manual_trips")
    if inserted != EXPECTED_MANUAL_COUNT:
        print(f"  ERROR: Expected {EXPECTED_MANUAL_COUNT}")
        return False
    print("  OK: manual_trips verified")
    return True


def step2_export_pdf_backup(conn) -> bool:
    """Export PDF rows (2023+) to CSV backup on disk."""
    print("\n=== Step 2: Export PDF backup → disk ===")

    if BACKUP_PATH.exists():
        with open(BACKUP_PATH) as f:
            reader = csv.reader(f)
            next(reader)
            row_count = sum(1 for _ in reader)
        if row_count == EXPECTED_PDF_2023_COUNT:
            print(f"  SKIP: Backup already exists with {row_count} rows")
            return True
        else:
            print(
                f"  WARNING: Backup exists but has {row_count} rows,"
                f" expected {EXPECTED_PDF_2023_COUNT}"
            )
            return False

    columns = get_column_names(conn)
    rows = conn.execute(
        "SELECT * FROM trips WHERE source = 'pdf' AND transaction_date >= '2023-01-01'"
    ).fetchall()

    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BACKUP_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    with open(BACKUP_PATH) as f:
        reader = csv.reader(f)
        next(reader)
        row_count = sum(1 for _ in reader)

    print(f"  Exported {row_count} rows to {BACKUP_PATH}")
    if row_count != EXPECTED_PDF_2023_COUNT:
        print(f"  ERROR: Expected {EXPECTED_PDF_2023_COUNT}")
        BACKUP_PATH.unlink()
        return False
    print("  OK: Backup verified")
    return True


def step3_verification_gate(conn) -> bool:
    """Hard gate: verify both exports before proceeding."""
    print("\n=== Step 3: Verification gate ===")

    try:
        manual_count = conn.execute("SELECT COUNT(*) FROM manual_trips").fetchone()[0]
    except Exception:
        print("  ERROR: manual_trips table does not exist")
        return False

    if manual_count != EXPECTED_MANUAL_COUNT:
        print(
            f"  ERROR: manual_trips has {manual_count} rows,"
            f" expected {EXPECTED_MANUAL_COUNT}"
        )
        return False
    print(f"  OK: manual_trips has {manual_count} rows")

    if not BACKUP_PATH.exists():
        print(f"  ERROR: Backup file does not exist at {BACKUP_PATH}")
        return False

    with open(BACKUP_PATH) as f:
        reader = csv.reader(f)
        next(reader)
        row_count = sum(1 for _ in reader)

    if row_count != EXPECTED_PDF_2023_COUNT:
        print(
            f"  ERROR: Backup has {row_count} rows, expected {EXPECTED_PDF_2023_COUNT}"
        )
        return False
    print(f"  OK: Backup file has {row_count} rows")

    print("  GATE PASSED: Safe to proceed with deletion")
    return True


def step4_delete_pdf_rows(conn) -> bool:
    """Delete PDF rows from 2023 onward."""
    print("\n=== Step 4: Delete PDF rows (2023+) ===")

    count_before = conn.execute(
        "SELECT COUNT(*) FROM trips"
        " WHERE source = 'pdf' AND transaction_date >= '2023-01-01'"
    ).fetchone()[0]

    if count_before == 0:
        print("  SKIP: No PDF rows to delete (already done)")
        return True

    conn.execute(
        "DELETE FROM trips WHERE source = 'pdf' AND transaction_date >= '2023-01-01'"
    )
    conn.commit()

    count_after = conn.execute(
        "SELECT COUNT(*) FROM trips"
        " WHERE source = 'pdf' AND transaction_date >= '2023-01-01'"
    ).fetchone()[0]

    print(f"  Deleted {count_before} PDF rows (remaining: {count_after})")
    if count_after != 0:
        print("  ERROR: Some PDF rows remain")
        return False
    print("  OK: All 2023+ PDF rows deleted")
    return True


def step5_download_and_ingest(conn) -> bool:
    """Download CSVs for Jan 2023 - Nov 2025 and ingest.

    Always runs clipper-download — trip_id dedup makes this safe to
    re-run after partial ingestion (e.g., network failure mid-download).
    """
    import subprocess

    print("\n=== Step 5: Download and ingest CSVs ===")

    before_count = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE source = 'csv'"
        " AND transaction_date >= '2023-01-01'"
        " AND transaction_date < '2025-12-01'"
    ).fetchone()[0]
    if before_count > 0:
        print(
            f"  Note: {before_count} CSV rows already exist"
            " in 2023-2025 range (will dedup)"
        )

    project_root = Path(__file__).parent.parent
    result = subprocess.run(
        [
            "uv",
            "run",
            "clipper-download",
            "--start",
            "2023-01-01",
            "--end",
            "2025-11-30",
            "--ingest",
        ],
        cwd=str(project_root),
    )

    if result.returncode != 0:
        print(f"  ERROR: clipper-download exited with code {result.returncode}")
        return False

    after_count = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE source = 'csv'"
        " AND transaction_date >= '2023-01-01'"
        " AND transaction_date < '2025-12-01'"
    ).fetchone()[0]
    print(f"  CSV rows in 2023-2025 range: {after_count} (was {before_count})")
    if after_count == 0:
        print("  ERROR: No rows ingested")
        return False
    print("  OK: CSV ingestion complete")
    return True


def step6_reimport_manual_trips(conn) -> bool:
    """Re-import 2023+ manual rows from manual_trips into trips."""
    print("\n=== Step 6: Re-import manual trips ===")

    # Idempotency guard
    existing_manual = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE source = 'manual'"
    ).fetchone()[0]
    if existing_manual > 0:
        print(
            f"  Clearing {existing_manual} existing source='manual' rows (idempotency)"
        )
        conn.execute("DELETE FROM trips WHERE source = 'manual'")

    columns = get_column_names(conn)
    rows = conn.execute(
        "SELECT * FROM manual_trips WHERE transaction_date >= '2023-01-01'"
    ).fetchall()
    print(f"  Found {len(rows)} manual rows (2023+) to re-import")

    insert_columns = [c for c in columns if c != "id"]
    placeholders = ", ".join(["?"] * len(insert_columns))

    for row in rows:
        values = []
        for i, col in enumerate(columns):
            if col == "id":
                continue
            elif col == "source":
                values.append("manual")
            else:
                values.append(row[i])
        conn.execute(
            f"INSERT INTO trips ({', '.join(insert_columns)}) VALUES ({placeholders})",
            values,
        )
    conn.commit()

    inserted = conn.execute(
        "SELECT COUNT(*) FROM trips WHERE source = 'manual'"
    ).fetchone()[0]
    print(f"  Inserted {inserted} manual rows")
    expected = 65  # 59 midnight placeholders + 6 unique manual-type (2023+)
    if inserted != expected:
        print(f"  WARNING: Expected {expected}, got {inserted}")
        return False
    print("  OK: Manual trips re-imported")
    return True


def step7_post_migration_verification(conn) -> bool:
    """Verify the migration results."""
    print("\n=== Step 7: Post-migration verification ===")

    print("  Source distribution:")
    for row in conn.execute(
        "SELECT source, COUNT(*) FROM trips GROUP BY source ORDER BY source"
    ).fetchall():
        print(f"    {row[0]}: {row[1]}")

    unknowns = conn.execute("""
        SELECT COUNT(*) FROM trips t
        LEFT JOIN transit_modes tm ON t.transit_id = tm.id
        WHERE t.transaction_date >= '2023-01-01'
          AND t.category IS NULL
          AND t.source != 'manual'
          AND tm.name IS NULL
    """).fetchone()[0]
    if unknowns > 0:
        print(f"  WARNING: {unknowns} rows in 2023+ would resolve to 'Unknown'")
    else:
        print("  OK: No 'Unknown' categories in 2023+ CSV data")

    print("\n  Monthly ride counts (2023+, excluding reloads):")
    rows = conn.execute("""
        SELECT strftime('%Y-%m', transaction_date) as month,
               source,
               COUNT(*) as cnt
        FROM trips
        WHERE transaction_date >= '2023-01-01'
          AND transaction_type NOT IN ('reload')
        GROUP BY month, source
        ORDER BY month, source
    """).fetchall()
    current_month = None
    for row in rows:
        if row[0] != current_month:
            if current_month is not None:
                print()
            current_month = row[0]
            print(f"    {current_month}:", end="")
        print(f" {row[1]}={row[2]}", end="")
    print()

    print("\n  OK: Post-migration verification complete")
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Proceed with deletion and re-ingestion (Steps 4-7)",
    )
    args = parser.parse_args()

    initialize_database()
    conn = get_turso_client()

    if not step0_preflight(conn):
        print("\nABORTED: Pre-flight checks failed")
        return 1

    if not step1_export_manual_trips(conn):
        print("\nABORTED: Manual trips export failed")
        return 1

    if not step2_export_pdf_backup(conn):
        print("\nABORTED: PDF backup export failed")
        return 1

    if not step3_verification_gate(conn):
        print("\nABORTED: Verification gate failed")
        return 1

    if not args.delete:
        print("\n=== Steps 0-3 complete. Ready for deletion + ingestion. ===")
        print("Run with --delete to proceed to Steps 4-7.")
        return 0

    if not step4_delete_pdf_rows(conn):
        print("\nABORTED: PDF deletion failed")
        return 1

    if not step5_download_and_ingest(conn):
        print("\nERROR: CSV download/ingest failed")
        print("Re-run with --delete to retry (idempotent)")
        return 1

    if not step6_reimport_manual_trips(conn):
        print("\nERROR: Manual trip re-import failed")
        return 1

    if not step7_post_migration_verification(conn):
        print("\nWARNING: Post-migration verification has warnings")
        return 1

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
