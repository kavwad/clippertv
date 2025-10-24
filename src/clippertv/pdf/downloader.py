#!/usr/bin/env python3
"""
Clipper PDF Downloader: download PDF transaction reports for one or more users via ClipperWeb.
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, date, timedelta

import requests
from bs4 import BeautifulSoup
import tomllib

from clippertv.pdf.processor import process_pdf_statements

HOST = "https://www.clippercard.com"
USER_AGENT = "clipper-pdf-downloader/0.1"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download PDF transaction reports from ClipperWeb."
    )
    parser.add_argument("--email", help="Login email (optional if using --user or --all)")
    parser.add_argument("--password", help="Password (optional if using --user or --all)")
    parser.add_argument(
        "--output",
        default="pdfs",
        help="Output directory for PDF files",
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
        help="Test run without downloading PDFs (avoids API limits)"
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
        help="After downloading PDFs, process and load transactions into the data store",
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
    resp = session.get(
        f"{HOST}/ClipperWeb/login.html",
        headers={"User-Agent": USER_AGENT},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Could not get login page: {resp.status_code}")
    csrf = find_csrf_token(resp.text)
    data = {"_csrf": csrf, "email": email, "password": password}
    resp2 = session.post(
        f"{HOST}/ClipperWeb/account",
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"{HOST}/ClipperWeb/login.html",
        },
    )
    if resp2.status_code not in (200, 302):
        raise RuntimeError(f"Could not login: {resp2.status_code}")
    return session


def get_cards(session):
    resp = session.get(
        f"{HOST}/ClipperWeb/account.html",
        headers={"User-Agent": USER_AGENT},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Could not get account page: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = []
    for span in soup.find_all("span", class_="d-inline-block"):
        text = span.get_text(strip=True)
        parts = text.split(" - ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            cards.append({"serial": parts[0], "nickname": parts[1]})
    return cards


def format_clip_date(date_str):
    if not date_str:
        return ""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def download_pdfs(session, output_dir, start_date, end_date, dry_run):
    clip_start = format_clip_date(start_date)
    clip_end = format_clip_date(end_date)
    resp = session.get(
        f"{HOST}/ClipperWeb/account.html",
        headers={"User-Agent": USER_AGENT},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Could not refresh account page: {resp.status_code}")
    csrf = find_csrf_token(resp.text)
    cards = get_cards(session)
    saved_files = []
    for card in cards:
        if dry_run:
            print(
                f"[DRY RUN] Would download PDF for card {card['serial']} ({card['nickname']}) "
                f"with date range: {start_date or 'default'} to {end_date or 'default'}"
            )
            continue
        data = {
            "_csrf": csrf,
            "cardNumber": card['serial'],
            "cardNickName": card['nickname'],
            "rhStartDate": clip_start,
            "startDateValue": clip_start,
            "startDate": clip_start,
            "rhEndDate": clip_end,
            "endDateValue": clip_end,
            "endDate": clip_end,
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/pdf",
            "Referer": f"{HOST}/ClipperWeb/account.html",
        }
        resp2 = session.post(
            f"{HOST}/ClipperWeb/view/transactionHistory.pdf",
            data=data,
            headers=headers,
        )
        if resp2.status_code != 200:
            raise RuntimeError(f"Bad status for card {card['serial']}: {resp2.status_code}")
        ctype = resp2.headers.get("Content-Type", "")
        content = resp2.content
        if not content:
            print(
                f"No PDF returned for card {card['serial']} ({card['nickname']}); skipping."
            )
            continue
        if not ctype.startswith("application/pdf"):
            if content.startswith(b"%PDF"):
                print(
                    f"Warning: Unexpected content type '{ctype}' for card {card['serial']}; "
                    "continuing because response appears to be a PDF."
                )
            else:
                raise RuntimeError(
                    f"Bad content type for card {card['serial']}: {ctype}"
                )
        if not content or not content.lstrip().startswith(b"%PDF"):
            raise RuntimeError(
                f"Invalid PDF content for card {card['serial']}: missing PDF header"
            )

        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(
            output_dir, f"clipper-transactions-{card['serial']}.pdf"
        )
        with open(filename, "wb") as f:
            f.write(content)
        print(f"Saved PDF: {filename} (Card: {card['nickname']})")
        saved_files.append({"path": filename, "card": card})

    return saved_files


def group_pdfs_by_rider(saved_files, rider_accounts):
    """Group downloaded PDFs by rider identifier based on account mapping."""
    files_by_rider = defaultdict(list)
    unmatched = []

    for item in saved_files:
        card_serial = str(item["card"]["serial"])
        rider = None
        for rider_id, accounts in rider_accounts.items():
            if card_serial in {str(acc) for acc in accounts}:
                rider = rider_id
                break
        if rider:
            files_by_rider[rider].append(item["path"])
        else:
            unmatched.append(card_serial)

    return files_by_rider, unmatched


def process_downloaded_pdfs(saved_files, rider_accounts):
    """Process downloaded PDFs and load transactions into the data store."""
    if not saved_files:
        return

    if not rider_accounts:
        raise RuntimeError(
            "Cannot process PDFs without rider account mapping in config (rider_accounts section)."
        )

    files_by_rider, unmatched = group_pdfs_by_rider(saved_files, rider_accounts)

    if unmatched:
        print(
            f"Warning: No rider mapping found for card(s): {', '.join(unmatched)} "
            "- skipping these PDFs."
        )

    if not files_by_rider:
        print("No PDFs matched configured rider accounts; nothing to process.")
        return

    for rider_id, pdf_paths in files_by_rider.items():
        print(f"Processing {len(pdf_paths)} PDF(s) for rider {rider_id}...")
        result = process_pdf_statements(pdf_paths, rider_id)
        if result is None or result.empty:
            print(f" - No transactions extracted for rider {rider_id}.")
        else:
            print(f" - Processed {len(result)} transactions for rider {rider_id}.")


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
        print("[DRY RUN] Testing PDF download parameters...")
    else:
        print("Downloading PDF transaction reports...")

    all_saved_files = []

    for idx, (uname, email, pw) in enumerate(users):
        if len(users) > 1:
            print(f"\n=== Processing user: {uname} ({email}) ===")
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        try:
            login(session, email, pw)
            saved_files = download_pdfs(session, args.output, start_date, end_date, args.dry_run)
            all_saved_files.extend(saved_files)
        except Exception as e:
            sys.stderr.write(f"Error for user {uname}: {e}\n")
            return 1

    if args.ingest and not args.dry_run:
        if not config_data:
            try:
                config_data = load_config(args.config_file)
            except Exception as e:
                sys.stderr.write(
                    f"Error loading config file {args.config_file} for processing: {e}\n"
                )
                return 1
        clipper_cfg = config_data.get("clipper", {})
        rider_accounts = clipper_cfg.get("rider_accounts", {})
        try:
            process_downloaded_pdfs(all_saved_files, rider_accounts)
        except Exception as e:
            sys.stderr.write(f"Post-processing failed: {e}\n")
            return 1

    if args.dry_run:
        print("\n[DRY RUN] Test completed successfully.")
    else:
        print(f"\nPDF downloads completed for {len(users)} user(s). Files saved to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
