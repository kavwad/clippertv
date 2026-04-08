#!/usr/bin/env python3
"""
Clipper CSV downloader and parser.

Download CSV transaction reports from clippercard.com and parse them into
normalized DataFrames.
"""

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from io import StringIO

from dotenv import load_dotenv

load_dotenv()

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

log = logging.getLogger(__name__)

HOST = "https://www.clippercard.com"
USER_AGENT = "clipper-downloader/0.3"

_NA_VALUES = {"N/A", "NONE", ""}
_DATE_FMT = "%m/%d/%Y %H:%M:%S"

# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _to_none_if_na(value: str | None) -> str | None:
    """Return None if value is a sentinel NA string, otherwise return value."""
    if value is None:
        return None
    return None if value.strip() in _NA_VALUES else value


def parse_csv(csv_content: str) -> pd.DataFrame:
    """Parse Clipper CSV content into a normalized DataFrame.

    Args:
        csv_content: Raw CSV string downloaded from clippercard.com.

    Returns:
        DataFrame with columns: account_number, transaction_date, end_datetime,
        start_location, end_location, fare, operator, pass_type, trip_id.
        Returns an empty DataFrame if csv_content is empty.
    """
    if not csv_content or not csv_content.strip():
        return pd.DataFrame(
            columns=[
                "account_number",
                "transaction_date",
                "end_datetime",
                "start_location",
                "end_location",
                "fare",
                "operator",
                "pass_type",
                "trip_id",
            ]
        )

    raw = pd.read_csv(StringIO(csv_content), dtype=str, keep_default_na=False)

    def _parse_dt(series: pd.Series) -> pd.Series:
        return pd.to_datetime(
            series.apply(lambda v: None if v.strip() in _NA_VALUES else v),
            format=_DATE_FMT,
            errors="coerce",
        )

    def _parse_location(series: pd.Series) -> pd.Series:
        result = series.apply(
            lambda v: (
                None if (v is None or str(v).strip() in _NA_VALUES) else str(v).strip()
            )
        )
        assert isinstance(result, pd.Series)
        return result

    df = pd.DataFrame()
    df["account_number"] = raw["ACCOUNT NUMBER"].str.strip()
    df["transaction_date"] = _parse_dt(raw["START DATE/TIME"])
    df["end_datetime"] = _parse_dt(raw["END DATE/TIME"])
    df["start_location"] = _parse_location(raw["START LOCATION"])
    df["end_location"] = _parse_location(raw["END LOCATION"])
    df["fare"] = raw["FARE"].str.replace("$", "", regex=False).str.strip().astype(float)
    df["operator"] = raw["OPERATOR"].str.strip()
    df["pass_type"] = raw["PASS"].apply(
        lambda v: None if v.strip() in _NA_VALUES else v.strip()
    )
    df["trip_id"] = raw["TRIP ID"].str.strip()

    return df


# ---------------------------------------------------------------------------
# Download functions (migrated from pdf/downloader.py)
# ---------------------------------------------------------------------------


def find_csrf_token(html_text: str) -> str:
    """Extract CSRF token from an HTML page."""
    soup = BeautifulSoup(html_text, "html.parser")
    token = soup.find("input", attrs={"name": "_csrf"})
    if not token or not token.get("value"):
        raise RuntimeError("CSRF token not found in HTML")
    return str(token["value"])


def login(session: requests.Session, email: str, password: str) -> requests.Session:
    """Login to clippercard.com using the /web-login flow."""
    resp = session.get(
        f"{HOST}/web-login",
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Could not get login page: {resp.status_code}")
    csrf = find_csrf_token(resp.text)

    data = {
        "_csrf": csrf,
        "username": email,
        "password": password,
        "authFailCount": "0",
        "postLoginUrl": "",
    }
    resp2 = session.post(
        f"{HOST}/dashboard",
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"{HOST}/web-login",
        },
        timeout=30,
    )
    if resp2.status_code not in (200, 302):
        raise RuntimeError(f"Could not login: {resp2.status_code}")

    session.csrf_token = find_csrf_token(resp2.text)  # type: ignore[attr-defined]
    return session


def validate_and_discover(email: str, password: str) -> list[str] | None:
    """Validate Clipper credentials and discover associated card account numbers.

    Tries a 7-day window first, then 30 days if no cards found.
    Returns account_number list on success, or None if auth fails.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        login(session, email, password)
    except Exception:
        return None

    today = date.today()

    # Try 7 days first (fast), then 30 days if empty
    for days in (7, 30):
        start = (today - timedelta(days=days)).isoformat()
        end = today.isoformat()

        try:
            csv_content = download_csv(session, start, end)
        except Exception:
            return []

        if not csv_content:
            continue

        df = parse_csv(csv_content)
        if df.empty:
            continue

        return sorted(df["account_number"].unique().tolist())

    return []


def format_clip_date(date_str: str) -> str:
    """Format a YYYY-MM-DD date string as 'Month Day, Year' for Clipper API."""
    if not date_str:
        return ""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def download_csv(
    session: requests.Session,
    start_date: str,
    end_date: str,
    dry_run: bool = False,
) -> str | None:
    """Download transaction history as CSV from the Clipper API.

    Args:
        session: Authenticated requests Session.
        start_date: Start date in YYYY-MM-DD format, or empty string.
        end_date: End date in YYYY-MM-DD format, or empty string.
        dry_run: If True, print intent but do not make request.

    Returns:
        CSV content as string, or None on dry run.
    """
    if start_date and end_date:
        filter_period = f"{format_clip_date(start_date)} - {format_clip_date(end_date)}"
    else:
        filter_period = "Past 30 Days"

    if dry_run:
        print(f"[DRY RUN] Would download CSV with filter: {filter_period}")
        return None

    csrf_token = getattr(session, "csrf_token", None)
    if not csrf_token:
        raise RuntimeError("No CSRF token available - login may have failed")

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "*/*",
        "X-CSRF-TOKEN": csrf_token,
        "Referer": f"{HOST}/tripHistory",
        "Origin": HOST,
    }

    payload = {
        "filterPeriod": filter_period,
        "filterTA": "All Clipper Cards",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = session.post(
                f"{HOST}/download-trip-history/CSV",
                json=payload,
                headers=headers,
                timeout=60,
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < max_retries - 1:
                wait = 2**attempt * 2
                log.warning(
                    "Connection error on attempt %d/%d: %s. Retrying in %ds...",
                    attempt + 1,
                    max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)
                continue
            raise

        is_server_error = resp.status_code >= 500
        is_transient_404 = resp.status_code == 404 and "50x.html" in resp.text
        if (is_server_error or is_transient_404) and attempt < max_retries - 1:
            wait = 2**attempt * 2
            log.warning(
                "Server error (%d) on attempt %d/%d. Retrying in %ds...",
                resp.status_code,
                attempt + 1,
                max_retries,
                wait,
            )
            time.sleep(wait)
            continue

        break

    if resp.status_code == 404:
        raise RuntimeError(
            "CSV download endpoint returned 404."
            " This is a known Clipper server issue."
            f" Response: {resp.text[:200]}"
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"CSV download failed: {resp.status_code} - {resp.text[:200]}"
        )

    if not resp.text:
        raise RuntimeError(
            "CSV download returned empty content."
            " This appears to be a Clipper server issue."
            " The endpoint exists but is not returning data."
        )

    return resp.text


def _monthly_chunks(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Split a date range into monthly chunks of at most 30 days."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    chunks = []
    while start < end:
        chunk_end = min(start + timedelta(days=30), end)
        chunks.append((start.isoformat(), chunk_end.isoformat()))
        start = chunk_end + timedelta(days=1)
    return chunks


def download_transactions(
    session: requests.Session,
    output_dir: str,
    start_date: str,
    end_date: str,
    dry_run: bool,
) -> list[dict]:
    """Download transactions as CSV and save to file.

    Ranges longer than 30 days are split into monthly chunks to avoid
    server timeouts.

    Returns:
        List of dicts with 'path' and 'content' keys, or empty list on dry run.
    """
    if start_date and end_date:
        chunks = _monthly_chunks(start_date, end_date)
    else:
        chunks = [(start_date, end_date)]

    all_lines: list[str] = []
    header: str | None = None

    for i, (chunk_start, chunk_end) in enumerate(chunks):
        if len(chunks) > 1:
            print(
                f"Downloading chunk {i + 1}/{len(chunks)}: {chunk_start} to {chunk_end}"
            )
        csv_content = download_csv(session, chunk_start, chunk_end, dry_run)

        if dry_run or not csv_content:
            continue

        lines = csv_content.strip().splitlines()
        if header is None:
            header = lines[0]
            all_lines.append(header)
        all_lines.extend(lines[1:])

    if dry_run or not all_lines:
        return []

    combined = "\n".join(all_lines) + "\n"

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"clipper-transactions-{timestamp}.csv")

    with open(filename, "w") as f:
        f.write(combined)

    print(f"Saved CSV: {filename}")
    return [{"path": filename, "content": combined}]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download CSV transaction reports from clippercard.com."
    )
    parser.add_argument("--email", help="Login email (for manual one-off use)")
    parser.add_argument("--password", help="Password (for manual one-off use)")
    parser.add_argument(
        "--output",
        default="downloads",
        help="Output directory for CSV files",
    )
    parser.add_argument(
        "--start",
        dest="start_date",
        default="",
        help="Start date for transaction range (YYYY-MM-DD format, optional)",
    )
    parser.add_argument(
        "--end",
        dest="end_date",
        default="",
        help="End date for transaction range (YYYY-MM-DD format, optional)",
    )
    parser.add_argument(
        "--last-month",
        action="store_true",
        dest="last_month",
        help="Download last month's transactions (overrides start/end dates)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Download the last N days of transactions (overrides start/end dates)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Test run without downloading (validates login only)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        dest="ingest",
        help="After downloading, process and load transactions into the data store",
    )
    parser.add_argument(
        "--ingest-file",
        dest="ingest_file",
        nargs="+",
        help="Ingest one or more existing CSV files into the data store"
        " (skips download)",
    )
    return parser.parse_args()


def _load_accounts_from_db() -> list[dict]:
    """Load accounts from the users table via UserStore."""
    from clippertv.data.user_store import UserStore

    store = UserStore.from_env()
    users = store.get_all_users_with_credentials()
    accounts = []
    for user in users:
        creds = store.decrypt_user_credentials(user)
        if not creds:
            sys.stderr.write(
                f"Warning: could not decrypt credentials for {user.email}\n"
            )
            continue
        accounts.append(
            {
                "name": user.name or user.email,
                "email": creds["username"],
                "password": creds["password"],
            }
        )
    return accounts


def main() -> int:
    """CLI entry point for Clipper CSV downloader."""
    args = _parse_args()

    if args.ingest_file:
        from clippertv.data.turso_store import TursoStore
        from clippertv.ingest.pipeline import ingest as run_ingest

        store = TursoStore()

        for filepath in args.ingest_file:
            print(f"Ingesting {filepath}...")
            with open(filepath) as f:
                csv_content = f.read()
            df = parse_csv(csv_content)
            if df.empty:
                print(f"  No transactions in {filepath}")
                continue
            for acct_num, card_df in df.groupby("account_number"):
                count = run_ingest(
                    card_df,
                    account_number=str(acct_num),
                    user_id=None,
                    store=store,
                )
                print(f"  {count} new transactions for {acct_num}")
        return 0

    if args.email or args.password:
        if not args.email or not args.password:
            sys.stderr.write("Both --email and --password are required\n")
            return 2
        accounts = [
            {
                "name": "manual",
                "email": args.email,
                "password": args.password,
            }
        ]
    else:
        accounts = _load_accounts_from_db()
        if not accounts:
            sys.stderr.write(
                "No accounts with credentials in database.\n"
                "Use --email/--password for manual login.\n"
            )
            return 2

    start_date = args.start_date
    end_date = args.end_date
    if args.last_month:
        today = date.today()
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        start_date = last.replace(day=1).strftime("%Y-%m-%d")
        end_date = last.strftime("%Y-%m-%d")
        print(f"Using last month date range: {start_date} to {end_date}")
    elif args.days > 0:
        today = date.today()
        start_date = (today - timedelta(days=args.days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        print(f"Using last {args.days} days: {start_date} to {end_date}")

    if args.dry_run:
        print("[DRY RUN] Testing login and CSV download parameters...")
    else:
        print("Downloading CSV transaction reports...")

    all_downloaded = []
    for account in accounts:
        name, email, pw = account["name"], account["email"], account["password"]
        if len(accounts) > 1:
            print(f"\n=== Processing account: {name} ({email}) ===")
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        try:
            login(session, email, pw)
            results = download_transactions(
                session, args.output, start_date, end_date, args.dry_run
            )
            all_downloaded.extend(results)
        except Exception as e:
            sys.stderr.write(f"Error for {name}: {e}\n")
            return 1

    if args.ingest and not args.dry_run:
        from clippertv.data.turso_store import TursoStore
        from clippertv.ingest.pipeline import ingest as run_ingest

        store = TursoStore()
        for download in all_downloaded:
            csv_content = download["content"]
            df = parse_csv(csv_content)
            if df.empty:
                print(f"  No transactions in {download['path']}")
                continue
            for acct_num, card_df in df.groupby("account_number"):
                count = run_ingest(
                    card_df,
                    account_number=str(acct_num),
                    user_id=None,
                    store=store,
                )
                print(f"  {count} new transactions for {acct_num}")

    if args.dry_run:
        print("\n[DRY RUN] Test completed successfully.")
    else:
        print(
            f"\nCSV downloads completed for {len(accounts)} user(s). "
            f"Files saved to: {args.output}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
