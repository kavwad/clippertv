#!/usr/bin/env python3
"""CLI script for uploading PDF statements to ClipperTV."""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional
import tomllib

from clippertv.pdf.processor import process_pdf_statements, categorize_trips
from clippertv.pdf.extractor import extract_trips_from_pdf, clean_up_extracted_data


def load_secrets() -> dict:
    """Load secrets from .streamlit/secrets.toml file."""
    secrets_path = Path(".streamlit/secrets.toml")
    if not secrets_path.exists():
        raise FileNotFoundError("Secrets file not found at .streamlit/secrets.toml")

    with open(secrets_path, "rb") as f:
        return tomllib.load(f)


def match_user_and_account_from_filename(filename: str, rider_accounts: dict) -> tuple[Optional[str], Optional[str]]:
    """Match user and account from PDF filename (format: rideHistory_{account}.pdf)."""
    # Extract account number from filename
    for user_id, accounts in rider_accounts.items():
        for account in accounts:
            if account in filename:
                return user_id, account
    
    return None, None


def select_rider_account(user_id: str, rider_accounts: dict) -> str:
    """Select rider account for the user."""
    accounts = rider_accounts.get(user_id, [])
    
    if not accounts:
        raise ValueError(f"No accounts found for user {user_id}")
    
    if len(accounts) == 1:
        return accounts[0]
    
    # Multiple accounts - prompt user to select
    print(f"Multiple accounts found for user {user_id}:")
    for i, account in enumerate(accounts, 1):
        print(f"  {i}. {account}")
    
    while True:
        try:
            choice = input("Select account number: ")
            index = int(choice) - 1
            if 0 <= index < len(accounts):
                return accounts[index]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


class MockStreamlit:
    """Mock Streamlit object to provide secrets access."""
    def __init__(self, secrets: dict):
        self.secrets = secrets


def mock_pdf_file(filepath: str):
    """Create a mock PDF file object for processing."""
    class MockPDFFile:
        def __init__(self, filepath: str):
            self.filepath = filepath
            self.name = os.path.basename(filepath)
        
        def read(self):
            with open(self.filepath, 'rb') as f:
                return f.read()
    
    return MockPDFFile(filepath)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Upload PDF statements to ClipperTV"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to PDF file to upload"
    )
    parser.add_argument(
        "--user",
        help="Override user detection (B or K)"
    )
    parser.add_argument(
        "--account",
        help="Override account selection (numeric string)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test filename matching without uploading"
    )
    
    args = parser.parse_args()
    
    # Validate PDF file exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    try:
        # Load secrets
        secrets = load_secrets()
        rider_accounts = secrets.get("rider_accounts", {})
        
        if not rider_accounts:
            print("Error: No rider accounts configured in secrets.toml")
            sys.exit(1)
        
        # Determine user and account from filename
        user_id = args.user
        account_id = args.account
        
        if not user_id or not account_id:
            detected_user, detected_account = match_user_and_account_from_filename(pdf_path.name, rider_accounts)
            
            if not user_id:
                user_id = detected_user
            if not account_id:
                account_id = detected_account
        
        # Validate we found both user and account
        if not user_id:
            print(f"Error: Could not determine user from filename: {pdf_path.name}")
            print(f"Expected format: rideHistory_{{account}}.pdf")
            sys.exit(1)
        
        if not account_id:
            account_id = select_rider_account(user_id, rider_accounts)
        
        print(f"User: {user_id}")
        print(f"Account: {account_id}")
        print(f"PDF: {pdf_path}")
        
        if args.dry_run:
            print("Dry run mode - extract and display transactions without uploading")
            # Extract and process transactions locally
            df = extract_trips_from_pdf(str(pdf_path))
            df = clean_up_extracted_data(df)
            df = categorize_trips(df)
            if df is None or df.empty:
                print("No transactions found in PDF.")
            else:
                print(df.to_string(index=False))
                print(f"\nTotal transactions: {len(df)}")
            return
        
        print("Uploading PDF...")
        
        # Mock Streamlit for secrets access
        import streamlit as st
        st.secrets = secrets
        
        # Process PDF
        mock_pdf = mock_pdf_file(str(pdf_path))
        result = process_pdf_statements([mock_pdf], user_id)
        
        if result is not None:
            print(f"Successfully processed PDF: {len(result)} transactions imported")
        else:
            print("Error: Failed to process PDF")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
