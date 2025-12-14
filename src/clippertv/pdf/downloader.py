#!/usr/bin/env python3
"""
Clipper CSV Downloader: Download CSV transaction reports from clippercard.com.
"""
import argparse
import csv
import os
import sys
from datetime import datetime, date, timedelta
from io import StringIO

import requests
from bs4 import BeautifulSoup
import tomllib

HOST = "https://www.clippercard.com"
USER_AGENT = "clipper-downloader/0.2"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download CSV transaction reports from clippercard.com."
    )
    parser.add_argument("--email", help="Login email (optional if using --user or --all)")
    parser.add_argument("--password", help="Password (optional if using --user or --all)")
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
        "--dry-run", action="store_true", dest="dry_run",
        help="Test run without downloading (validates login only)"
    )
    parser.add_argument(
        "--user", default="", help="Username from config file (e.g., --user=kaveh)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Download for all users in config file"
    )
    parser.add_argument(
        "--config",
        default=".streamlit/secrets.toml",
        dest="config_file",
        help="Path to config file (TOML)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        dest="ingest",
        help="After downloading, process and load transactions into the data store",
    )
    return parser.parse_args()


def load_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def find_csrf_token(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    token = soup.find("input", attrs={"name": "_csrf"})
    if not token or not token.get("value"):
        raise RuntimeError("CSRF token not found in HTML")
    return token["value"]


def login(session, email, password):
    """Login to clippercard.com using the new /web-login flow."""
    # 1. GET /web-login and extract _csrf
    resp = session.get(
        f"{HOST}/web-login",
        headers={"User-Agent": USER_AGENT},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Could not get login page: {resp.status_code}")
    csrf = find_csrf_token(resp.text)

    # 2. POST /dashboard with form data
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
    )
    if resp2.status_code not in (200, 302):
        raise RuntimeError(f"Could not login: {resp2.status_code}")

    # 3. Extract new CSRF token from dashboard response for API calls
    session.csrf_token = find_csrf_token(resp2.text)
    return session


def format_clip_date(date_str):
    if not date_str:
        return ""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def download_csv(session, start_date, end_date, dry_run=False):
    """Download transaction history as CSV from the new API."""
    # Format date range as "Month Day, Year - Month Day, Year"
    if start_date and end_date:
        filter_period = f"{format_clip_date(start_date)} - {format_clip_date(end_date)}"
    else:
        filter_period = "Past 30 Days"

    if dry_run:
        print(f"[DRY RUN] Would download CSV with filter: {filter_period}")
        return None

    # Use CSRF token from login
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

    resp = session.post(
        f"{HOST}/download-trip-history/CSV",
        json=payload,
        headers=headers,
    )

    if resp.status_code == 404:
        # Known server-side issue - endpoint not yet available
        raise RuntimeError(
            f"CSV download endpoint returned 404. This is a known Clipper server issue. "
            f"Response: {resp.text[:200]}"
        )
    if resp.status_code != 200:
        raise RuntimeError(f"CSV download failed: {resp.status_code} - {resp.text[:200]}")

    if not resp.text:
        # Server returns 200 but empty content - another server-side issue
        raise RuntimeError(
            "CSV download returned empty content. This appears to be a Clipper server issue. "
            "The endpoint exists but is not returning data."
        )

    return resp.text  # CSV content as string


def parse_csv_transactions(csv_content: str) -> list[dict]:
    """Parse CSV content into transaction records."""
    if not csv_content:
        return []
    if csv_content.strip().startswith("{"):  # JSON error response
        raise RuntimeError(f"Invalid CSV response (got JSON): {csv_content[:200]}")

    reader = csv.DictReader(StringIO(csv_content))
    return list(reader)


def download_transactions(session, output_dir, start_date, end_date, dry_run):
    """Download transactions as CSV and save to file."""
    csv_content = download_csv(session, start_date, end_date, dry_run)

    if dry_run or not csv_content:
        return []

    # Save CSV file
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"clipper-transactions-{timestamp}.csv")

    with open(filename, "w") as f:
        f.write(csv_content)

    print(f"Saved CSV: {filename}")
    return [{"path": filename, "content": csv_content}]


def main():
    args = parse_args()
    if (
        (args.user and args.all)
        or (args.user and (args.email or args.password))
        or (args.all and (args.email or args.password))
    ):
        sys.stderr.write(
            "Cannot use --user, --all, and manual credentials together\n"
        )
        return 2

    if not args.user and not args.all and not args.email and not args.password:
        args.all = True

    users = []
    config_data = {}
    if args.user or args.all:
        try:
            config_data = load_config(args.config_file)
        except Exception as e:
            sys.stderr.write(f"Error loading config file {args.config_file}: {e}\n")
            return 2
        clipper_cfg = config_data.get("clipper", {})
        cfg_users = clipper_cfg.get('users', {})
        if args.user:
            if args.user not in cfg_users:
                sys.stderr.write(f"User '{args.user}' not found in config file\n")
                sys.stderr.write("Available users: "+" ".join(cfg_users.keys())+"\n")
                return 2
            u = cfg_users[args.user]
            users.append((args.user, u.get('email', ''), u.get('password', '')))
        else:
            for name, u in cfg_users.items():
                users.append((name, u.get('email', ''), u.get('password', '')))
    else:
        if not args.email or not args.password:
            sys.stderr.write("Please provide credentials\n")
            sys.stderr.write(
                f"Usage: {sys.argv[0]} [--user=username] [--all] OR "
                "[--email=email --password=password] [options]\n"
            )
            return 2
        users.append(("manual", args.email, args.password))

    start_date = args.start_date
    end_date = args.end_date
    if args.last_month:
        today = date.today()
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        start_date = last.replace(day=1).strftime("%Y-%m-%d")
        end_date = last.strftime("%Y-%m-%d")
        print(f"Using last month date range: {start_date} to {end_date}")

    if args.dry_run:
        print("[DRY RUN] Testing login and CSV download parameters...")
    else:
        print("Downloading CSV transaction reports...")

    for uname, email, pw in users:
        if len(users) > 1:
            print(f"\n=== Processing user: {uname} ({email}) ===")
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        try:
            login(session, email, pw)
            download_transactions(session, args.output, start_date, end_date, args.dry_run)
        except Exception as e:
            sys.stderr.write(f"Error for user {uname}: {e}\n")
            return 1

    if args.ingest and not args.dry_run:
        # TODO: CSV ingestion not yet implemented - processor.py expects PDFs
        print(
            "Warning: --ingest is not yet supported for CSV downloads. "
            "The CSV file has been saved but not processed into the database."
        )

    if args.dry_run:
        print("\n[DRY RUN] Test completed successfully.")
    else:
        print(f"\nCSV downloads completed for {len(users)} user(s). Files saved to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
