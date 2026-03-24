#!/usr/bin/env python3
"""
Clipper CSV downloader and parser.

Download CSV transaction reports from clippercard.com and parse them into
normalized DataFrames.
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
import tomllib

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
        return series.apply(
            lambda v: None if (v is None or str(v).strip() in _NA_VALUES) else str(v).strip()
        )

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
    return token["value"]


def login(session: requests.Session, email: str, password: str) -> requests.Session:
    """Login to clippercard.com using the /web-login flow."""
    resp = session.get(
        f"{HOST}/web-login",
        headers={"User-Agent": USER_AGENT},
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
    )
    if resp2.status_code not in (200, 302):
        raise RuntimeError(f"Could not login: {resp2.status_code}")

    session.csrf_token = find_csrf_token(resp2.text)
    return session


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

    resp = session.post(
        f"{HOST}/download-trip-history/CSV",
        json=payload,
        headers=headers,
    )

    if resp.status_code == 404:
        raise RuntimeError(
            f"CSV download endpoint returned 404. This is a known Clipper server issue. "
            f"Response: {resp.text[:200]}"
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"CSV download failed: {resp.status_code} - {resp.text[:200]}"
        )

    if not resp.text:
        raise RuntimeError(
            "CSV download returned empty content. This appears to be a Clipper server issue. "
            "The endpoint exists but is not returning data."
        )

    return resp.text


def download_transactions(
    session: requests.Session,
    output_dir: str,
    start_date: str,
    end_date: str,
    dry_run: bool,
) -> list[dict]:
    """Download transactions as CSV and save to file.

    Returns:
        List of dicts with 'path' and 'content' keys, or empty list on dry run.
    """
    csv_content = download_csv(session, start_date, end_date, dry_run)

    if dry_run or not csv_content:
        return []

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"clipper-transactions-{timestamp}.csv")

    with open(filename, "w") as f:
        f.write(csv_content)

    print(f"Saved CSV: {filename}")
    return [{"path": filename, "content": csv_content}]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
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
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Test run without downloading (validates login only)",
    )
    parser.add_argument(
        "--user",
        default="",
        help="Username from config file (e.g., --user=kaveh)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download for all users in config file",
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


def _load_config(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def main() -> int:
    """CLI entry point for Clipper CSV downloader."""
    args = _parse_args()

    if (
        (args.user and args.all)
        or (args.user and (args.email or args.password))
        or (args.all and (args.email or args.password))
    ):
        sys.stderr.write("Cannot use --user, --all, and manual credentials together\n")
        return 2

    if not args.user and not args.all and not args.email and not args.password:
        args.all = True

    users: list[tuple[str, str, str]] = []
    if args.user or args.all:
        try:
            config_data = _load_config(args.config_file)
        except Exception as e:
            sys.stderr.write(f"Error loading config file {args.config_file}: {e}\n")
            return 2
        clipper_cfg = config_data.get("clipper", {})
        cfg_users = clipper_cfg.get("users", {})
        if args.user:
            if args.user not in cfg_users:
                sys.stderr.write(f"User '{args.user}' not found in config file\n")
                sys.stderr.write("Available users: " + " ".join(cfg_users.keys()) + "\n")
                return 2
            u = cfg_users[args.user]
            users.append((args.user, u.get("email", ""), u.get("password", "")))
        else:
            for name, u in cfg_users.items():
                users.append((name, u.get("email", ""), u.get("password", "")))
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

    all_downloaded = []
    for uname, email, pw in users:
        if len(users) > 1:
            print(f"\n=== Processing user: {uname} ({email}) ===")
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        try:
            login(session, email, pw)
            results = download_transactions(
                session, args.output, start_date, end_date, args.dry_run
            )
            all_downloaded.extend(results)
        except Exception as e:
            sys.stderr.write(f"Error for user {uname}: {e}\n")
            return 1

    if args.ingest and not args.dry_run:
        from clippertv.data.factory import get_data_store
        from clippertv.ingest.pipeline import ingest as run_ingest

        store = get_data_store()
        for download in all_downloaded:
            csv_content = download["content"]
            df = parse_csv(csv_content)
            if df.empty:
                print(f"  No transactions in {download['path']}")
                continue
            for account_number, card_df in df.groupby("account_number"):
                # Use account_number as rider_id for now.
                # Full card->rider->user lookup via clipper_cards table is
                # deferred to the scheduler task (when multi-user is wired up).
                rider_id = str(account_number)
                count = run_ingest(
                    card_df, rider_id=rider_id, user_id=None, store=store
                )
                print(f"  {count} new transactions for rider {rider_id}")

    if args.dry_run:
        print("\n[DRY RUN] Test completed successfully.")
    else:
        print(
            f"\nCSV downloads completed for {len(users)} user(s). "
            f"Files saved to: {args.output}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
