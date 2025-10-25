#!/usr/bin/env python3
"""
ClipperTV Monthly Ingestion Scheduler

Runs monthly PDF downloads and ingestion with deduplication and archiving.
Designed to run as a systemd service on Raspberry Pi.
"""

import hashlib
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Import downloader functions
from clippertv.pdf.downloader import (
    load_config,
    login,
    download_pdfs,
    process_downloaded_pdfs,
)
import requests


# Configuration
PDF_DIR = Path("pdfs")
CONFIG_FILE = ".streamlit/secrets.toml"
LOG_DIR = Path("logs")
USER_AGENT = "clipper-pdf-scheduler/1.0"

# Optional: Healthchecks.io monitoring
# Set HEALTHCHECK_URL environment variable to enable
HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL")


def setup_logging():
    """Configure logging to both file and console."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "scheduler.log"

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler (INFO level)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logging.getLogger(__name__)


def ping_healthcheck(endpoint: str = "", log_output: Optional[str] = None):
    """
    Ping Healthchecks.io to report job status.

    Args:
        endpoint: /start, /fail, or "" for success
        log_output: Optional log message to send
    """
    if not HEALTHCHECK_URL:
        return

    url = f"{HEALTHCHECK_URL.rstrip('/')}{endpoint}"
    logger = logging.getLogger(__name__)

    try:
        if log_output:
            requests.post(url, data=log_output.encode('utf-8'), timeout=10)
        else:
            requests.get(url, timeout=10)
        logger.debug(f"Healthcheck ping sent: {endpoint or 'success'}")
    except Exception as e:
        logger.warning(f"Failed to ping healthcheck: {e}")


def compute_pdf_hash(pdf_path: Path) -> str:
    """Compute SHA256 hash of PDF file."""
    sha256 = hashlib.sha256()
    with open(pdf_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def deduplicate_and_archive_pdfs(pdf_files: List[dict], logger: logging.Logger) -> List[dict]:
    """
    Deduplicate PDFs and save with month in filename.

    Returns list of unique PDFs that were processed.
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    archived = []
    seen_hashes = {}

    # Load existing hashes from all PDFs
    logger.info(f"Scanning existing PDFs: {PDF_DIR}")
    for existing_pdf in PDF_DIR.glob("*.pdf"):
        try:
            pdf_hash = compute_pdf_hash(existing_pdf)
            seen_hashes[pdf_hash] = existing_pdf
        except Exception as e:
            logger.warning(f"Could not hash existing PDF {existing_pdf}: {e}")

    logger.info(f"Found {len(seen_hashes)} existing PDFs")

    # Get current month for filename
    month_suffix = datetime.now().strftime("%Y-%m")

    # Process new PDFs
    for item in pdf_files:
        pdf_path = Path(item['path'])
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            continue

        try:
            pdf_hash = compute_pdf_hash(pdf_path)

            if pdf_hash in seen_hashes:
                logger.info(
                    f"Duplicate PDF detected: {pdf_path.name} "
                    f"(matches {seen_hashes[pdf_hash].name})"
                )
                # Remove duplicate from temp directory
                pdf_path.unlink()
            else:
                # Create filename with month: clipper-transactions-12345-2025-01.pdf
                stem = pdf_path.stem  # e.g., "clipper-transactions-12345"
                new_filename = f"{stem}-{month_suffix}.pdf"
                archive_path = PDF_DIR / new_filename

                # Handle unlikely filename conflicts (if running multiple times same month)
                counter = 1
                while archive_path.exists():
                    new_filename = f"{stem}-{month_suffix}_{counter}.pdf"
                    archive_path = PDF_DIR / new_filename
                    counter += 1

                shutil.move(str(pdf_path), str(archive_path))
                seen_hashes[pdf_hash] = archive_path
                archived.append({
                    'path': str(archive_path),
                    'card': item['card']
                })
                logger.info(f"Saved PDF: {archive_path.name}")

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")

    logger.info(f"Saved {len(archived)} unique PDFs to {PDF_DIR}")
    return archived


def run_monthly_ingestion():
    """Execute monthly PDF download, deduplication, archiving, and ingestion."""
    logger = logging.getLogger(__name__)

    # Signal job start
    ping_healthcheck("/start")

    try:
        logger.info("=" * 60)
        logger.info("Starting monthly Clipper PDF ingestion")
        logger.info("=" * 60)

        # Load configuration
        logger.info(f"Loading configuration from {CONFIG_FILE}")
        try:
            config_data = load_config(CONFIG_FILE)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return

        clipper_cfg = config_data.get("clipper", {})
        users = clipper_cfg.get("users", {})
        rider_accounts = clipper_cfg.get("rider_accounts", {})

        if not users:
            logger.error("No users configured in config file")
            return

        logger.info(f"Found {len(users)} configured user(s)")

        # Calculate last month's date range
        today = datetime.now().date()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        start_date = last_month_start.strftime("%Y-%m-%d")
        end_date = last_month_end.strftime("%Y-%m-%d")

        logger.info(f"Downloading PDFs for date range: {start_date} to {end_date}")

        # Create temporary download directory
        temp_download_dir = Path("tmp/downloads")
        temp_download_dir.mkdir(parents=True, exist_ok=True)

        # Download PDFs for all users
        all_saved_files = []

        for username, user_config in users.items():
            email = user_config.get("email")
            password = user_config.get("password")

            if not email or not password:
                logger.warning(f"Skipping user {username}: missing credentials")
                continue

            logger.info(f"Processing user: {username} ({email})")

            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})

            try:
                # Login
                logger.info(f"Logging in as {username}...")
                login(session, email, password)
                logger.info("Login successful")

                # Download PDFs
                logger.info("Downloading PDFs...")
                saved_files = download_pdfs(
                    session,
                    str(temp_download_dir),
                    start_date,
                    end_date,
                    dry_run=False
                )

                all_saved_files.extend(saved_files)
                logger.info(f"Downloaded {len(saved_files)} PDF(s) for {username}")

            except Exception as e:
                logger.error(f"Error processing user {username}: {e}", exc_info=True)

        if not all_saved_files:
            logger.warning("No PDFs were downloaded")
            return

        logger.info(f"Total PDFs downloaded: {len(all_saved_files)}")

        # Deduplicate and archive PDFs
        logger.info("Deduplicating and archiving PDFs...")
        unique_pdfs = deduplicate_and_archive_pdfs(all_saved_files, logger)

        if not unique_pdfs:
            logger.info("No new unique PDFs to process")
            return

        # Process archived PDFs and ingest to database
        logger.info("Processing PDFs and ingesting to database...")
        try:
            process_downloaded_pdfs(unique_pdfs, rider_accounts)
            logger.info("Ingestion completed successfully")
        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)

        logger.info("=" * 60)
        logger.info("Monthly ingestion completed")
        logger.info("=" * 60)

        # Signal success
        ping_healthcheck()

    except Exception as e:
        logger.error(f"Unexpected error during monthly ingestion: {e}", exc_info=True)

        # Signal failure with error details
        error_msg = f"Monthly ingestion failed: {e}"
        ping_healthcheck("/fail", log_output=error_msg)

        raise


def main():
    """Main scheduler entry point."""
    logger = setup_logging()
    logger.info("ClipperTV PDF Scheduler starting...")

    # Create scheduler
    scheduler = BlockingScheduler()

    # Schedule monthly job: 2nd of month at 2 AM
    scheduler.add_job(
        run_monthly_ingestion,
        CronTrigger(day=2, hour=2, minute=0),
        id='monthly_clipper_ingestion',
        name='Monthly Clipper PDF Ingestion',
        misfire_grace_time=3600,  # Allow 1 hour grace period if Pi was offline
    )

    logger.info("Scheduled monthly ingestion: 2nd of month at 2:00 AM")
    logger.info("Press Ctrl+C to exit")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
