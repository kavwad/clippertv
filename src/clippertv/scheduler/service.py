"""Scheduled ingestion service.

Platform-agnostic: call run_ingestion() from launchd, systemd, cron,
or any other trigger. Loads accounts from clipper.toml, downloads
recent transactions, and ingests them.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta

from clippertv.ingest.clipper import (
    _load_config,
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


def run_ingestion(
    *,
    config_path: str = "clipper.toml",
    days: int = 30,
    output_dir: str = "downloads",
    dry_run: bool = False,
) -> list[IngestionResult]:
    """Download and ingest recent transactions for all configured accounts.

    Args:
        config_path: Path to clipper.toml.
        days: Number of days to look back.
        output_dir: Directory for downloaded CSVs.
        dry_run: If True, validate login only.

    Returns:
        Per-account results with row counts or errors.
    """
    import requests

    from clippertv.data.turso_store import TursoStore

    config = _load_config(config_path)
    accounts = config.get("accounts", [])
    if not accounts:
        log.warning("No accounts in %s", config_path)
        return []

    today = date.today()
    start_date = (today - timedelta(days=days)).isoformat()
    end_date = today.isoformat()

    store = None if dry_run else TursoStore()
    results: list[IngestionResult] = []

    for account in accounts:
        name = account["name"]
        log.info("Processing account: %s", name)

        session = requests.Session()
        try:
            login(session, account["email"], account["password"])
            downloads = download_transactions(
                session, output_dir, start_date, end_date, dry_run
            )
        except Exception as e:
            log.error("Download failed for %s: %s", name, e)
            results.append(IngestionResult(account=name, new_rows=0, error=str(e)))
            continue

        if dry_run:
            results.append(IngestionResult(account=name, new_rows=0))
            continue

        total = 0
        for download in downloads:
            df = parse_csv(download["content"])
            if df.empty:
                continue
            for acct_num, card_df in df.groupby("account_number"):
                assert store is not None
                total += ingest(
                    card_df,
                    account_number=str(acct_num),
                    user_id=None,
                    store=store,
                )

        log.info("%s: %d new transactions", name, total)
        results.append(IngestionResult(account=name, new_rows=total))

    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for scheduled ingestion."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run scheduled Clipper CSV ingestion for all accounts."
    )
    parser.add_argument("--config", default="clipper.toml", help="Path to clipper.toml")
    parser.add_argument(
        "--days", type=int, default=30, help="Days to look back (default: 30)"
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
        config_path=args.config,
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
