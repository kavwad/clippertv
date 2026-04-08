"""Scheduled ingestion service.

Loads Clipper credentials from the users table, downloads recent
transactions, and ingests them. Can be triggered by launchd,
systemd, cron, Railway cron, or any other scheduler.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta

import requests

from clippertv.ingest.clipper import (
    download_transactions,
    login,
    parse_csv,
)
from clippertv.ingest.pipeline import ingest

log = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    account: str
    new_rows: int
    error: str | None = None


def _build_user_store():
    """Build a UserStore from environment config."""
    from clippertv.data.user_store import UserStore

    return UserStore.from_env()


def run_ingestion(
    *,
    days: int = 30,
    output_dir: str = "downloads",
    dry_run: bool = False,
) -> list[IngestionResult]:
    """Download and ingest recent transactions for all users with credentials.

    Reads Clipper credentials from the users table. Each user corresponds
    to one Clipper account. Downloads all cards' transactions and auto-discovers
    new cards.

    Args:
        days: Number of days to look back.
        output_dir: Directory for downloaded CSVs.
        dry_run: If True, validate login only.

    Returns:
        Per-account results with row counts or errors.
    """
    from clippertv.data.turso_store import TursoStore

    store = _build_user_store()
    users = store.get_all_users_with_credentials()
    if not users:
        log.warning("No users with credentials in database")
        return []

    today = date.today()
    start_date = (today - timedelta(days=days)).isoformat()
    end_date = today.isoformat()

    turso = None if dry_run else TursoStore()
    results: list[IngestionResult] = []

    for user in users:
        creds = store.decrypt_user_credentials(user)
        if not creds:
            log.warning("Failed to decrypt credentials for user %s", user.id)
            continue

        email = creds["username"]
        password = creds["password"]
        log.info("Processing account: %s", email)

        session = requests.Session()
        try:
            login(session, email, password)
            downloads = download_transactions(
                session, output_dir, start_date, end_date, dry_run
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            log.error("Transient network error for %s: %s", email, e)
            results.append(IngestionResult(account=email, new_rows=0, error=str(e)))
            continue
        except Exception as e:
            log.error("Download failed for %s: %s", email, e)
            try:
                store.set_needs_reauth(user.id, True)
            except Exception:
                log.exception("Failed to set needs_reauth for user %s", user.id)
            results.append(IngestionResult(account=email, new_rows=0, error=str(e)))
            continue

        if dry_run:
            results.append(IngestionResult(account=email, new_rows=0))
            continue

        # Collect all account numbers from downloaded CSVs and ingest
        total = 0
        all_account_numbers: set[str] = set()
        for download in downloads:
            df = parse_csv(download["content"])
            if df.empty:
                continue
            for acct_num, card_df in df.groupby("account_number"):
                acct_str = str(acct_num)
                all_account_numbers.add(acct_str)
                assert turso is not None
                total += ingest(
                    card_df,
                    account_number=acct_str,
                    user_id=None,
                    store=turso,
                )

        # Auto-discover new cards from this download
        if all_account_numbers:
            store.discover_and_sync_cards(user.id, sorted(all_account_numbers))

        log.info("%s: %d new transactions", email, total)
        results.append(IngestionResult(account=email, new_rows=total))

    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for scheduled ingestion."""
    import argparse

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run scheduled Clipper CSV ingestion for all accounts."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days to look back (default: 30)",
    )
    parser.add_argument("--output", default="downloads", help="Download directory")
    parser.add_argument("--dry-run", action="store_true", help="Validate login only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    results = run_ingestion(
        days=args.days,
        output_dir=args.output,
        dry_run=args.dry_run,
    )

    total_new = 0
    failures = 0
    for r in results:
        if r.error:
            failures += 1
            log.error("FAIL %s: %s", r.account, r.error)
        else:
            total_new += r.new_rows
            log.info("OK   %s: %d new rows", r.account, r.new_rows)

    log.info(
        "Done: %d account(s), %d new rows, %d failure(s)",
        len(results),
        total_new,
        failures,
    )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
