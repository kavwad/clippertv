"""Scheduled ingestion service.

Loads Clipper credentials from the database, downloads recent
transactions, and ingests them. Can be triggered by launchd,
systemd, cron, Railway cron, or any other scheduler.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

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
    """Download and ingest recent transactions for all accounts with credentials.

    Reads Clipper credentials from the database (clipper_cards table).
    Groups cards by their Clipper login email to avoid duplicate logins.

    Args:
        days: Number of days to look back.
        output_dir: Directory for downloaded CSVs.
        dry_run: If True, validate login only.

    Returns:
        Per-account results with row counts or errors.
    """
    import requests

    from clippertv.data.turso_store import TursoStore

    store = _build_user_store()
    cards = store.get_all_cards_with_credentials()
    if not cards:
        log.warning("No cards with credentials in database")
        return []

    # Decrypt credentials and group by Clipper login email
    # (one login downloads CSVs for all cards under that account)
    accounts_by_email: dict[str, dict] = {}
    card_account_numbers: dict[str, list[str]] = defaultdict(list)

    for card in cards:
        creds = store.decrypt_card_credentials(card)
        if not creds:
            log.warning("Failed to decrypt credentials for card %s", card.id)
            continue
        email = creds["username"]
        if email not in accounts_by_email:
            accounts_by_email[email] = {
                "email": email,
                "password": creds["password"],
                "label": email,
            }
        card_account_numbers[email].append(card.account_number)

    today = date.today()
    start_date = (today - timedelta(days=days)).isoformat()
    end_date = today.isoformat()

    turso = None if dry_run else TursoStore()
    results: list[IngestionResult] = []

    for email, account in accounts_by_email.items():
        log.info("Processing account: %s", email)

        session = requests.Session()
        try:
            login(session, account["email"], account["password"])
            downloads = download_transactions(
                session, output_dir, start_date, end_date, dry_run
            )
        except Exception as e:
            log.error("Download failed for %s: %s", email, e)
            results.append(IngestionResult(account=email, new_rows=0, error=str(e)))
            continue

        if dry_run:
            results.append(IngestionResult(account=email, new_rows=0))
            continue

        total = 0
        known_accounts = set(card_account_numbers[email])
        for download in downloads:
            df = parse_csv(download["content"])
            if df.empty:
                continue
            for acct_num, card_df in df.groupby("account_number"):
                acct_str = str(acct_num)
                if acct_str not in known_accounts:
                    log.debug(
                        "Skipping unknown account %s from %s",
                        acct_str,
                        email,
                    )
                    continue
                assert turso is not None
                total += ingest(
                    card_df,
                    account_number=acct_str,
                    user_id=None,
                    store=turso,
                )

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
