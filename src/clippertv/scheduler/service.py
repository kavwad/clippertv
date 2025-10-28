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

import requests

# Import downloader functions
from clippertv.pdf.downloader import (
    login,
    download_pdfs,
    process_downloaded_pdfs,
)
# Import auth/data services
from clippertv.auth.service import AuthService
from clippertv.auth.crypto import CredentialEncryption
from clippertv.data.user_store import UserStore
from clippertv.data.turso_client import get_turso_client


# Configuration
PDF_DIR = Path("pdfs")
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

        # Initialize database and user store
        logger.info("Connecting to database...")
        try:
            jwt_secret = os.getenv("JWT_SECRET_KEY")
            encryption_key = os.getenv("ENCRYPTION_KEY")

            if not jwt_secret or not encryption_key:
                logger.error("JWT_SECRET_KEY and ENCRYPTION_KEY must be set in environment")
                return

            client = get_turso_client()
            auth = AuthService(secret_key=jwt_secret)
            crypto = CredentialEncryption(encryption_key=encryption_key)
            user_store = UserStore(client, auth, crypto)
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            return

        # Get all users from database
        logger.info("Loading users from database...")
        try:
            # Get all users - we'll need to query the database directly for this
            result = client.execute("SELECT id, email, name FROM users")
            users = result.fetchall()

            if not users:
                logger.error("No users found in database")
                return

            logger.info(f"Found {len(users)} user(s)")
        except Exception as e:
            logger.error(f"Failed to load users: {e}", exc_info=True)
            return

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
        # Build rider_accounts mapping for ingestion
        rider_accounts = {}

        for user_row in users:
            user_id, email, name = user_row[0], user_row[1], user_row[2]
            logger.info(f"Processing user: {name or email}")

            # Get all Clipper cards for this user
            try:
                cards = user_store.get_user_clipper_cards(user_id)

                if not cards:
                    logger.warning(f"No Clipper cards found for {name or email}")
                    continue

                logger.info(f"Found {len(cards)} card(s) for {name or email}")

                # Download PDFs for each card
                for card in cards:
                    # Get decrypted credentials
                    creds = user_store.get_decrypted_credentials(card.id)
                    if not creds:
                        logger.warning(f"No credentials for card {card.card_number}")
                        continue

                    clipper_email = creds.get("username")  # username is the email
                    clipper_password = creds.get("password")

                    logger.info(f"  Downloading for card {card.card_number} ({clipper_email})")

                    session = requests.Session()
                    session.headers.update({"User-Agent": USER_AGENT})

                    try:
                        # Login to Clipper website
                        logger.info(f"    Logging in...")
                        login(session, clipper_email, clipper_password)
                        logger.info("    Login successful")

                        # Download PDFs
                        logger.info("    Downloading PDFs...")
                        saved_files = download_pdfs(
                            session,
                            str(temp_download_dir),
                            start_date,
                            end_date,
                            dry_run=False
                        )

                        # Tag files with card info for ingestion (expected format)
                        for file_info in saved_files:
                            file_info['card'] = {'serial': card.card_number}

                        all_saved_files.extend(saved_files)
                        logger.info(f"    Downloaded {len(saved_files)} PDF(s)")

                        # Build rider_accounts mapping (card_number -> user identifier)
                        # Use first letter of name or email
                        rider_id = (name[0] if name else email[0]).upper()
                        if rider_id not in rider_accounts:
                            rider_accounts[rider_id] = []
                        if card.card_number not in rider_accounts[rider_id]:
                            rider_accounts[rider_id].append(card.card_number)

                    except Exception as e:
                        logger.error(f"    Error downloading for card {card.card_number}: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error processing user {name or email}: {e}", exc_info=True)

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


# NOTE: main() function removed - we use systemd timer instead of APScheduler
# For systemd timer, use: python -m clippertv.scheduler.run_ingestion
# For APScheduler version, see git history
