"""Batch utilities for ingesting Clipper PDF statements."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from clippertv.pdf.extractor import extract_trips_from_pdf, clean_up_extracted_data
from clippertv.pdf.processor import categorize_trips

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


CARD_PATTERNS = [
    "Transaction History For Card",
    "Card Serial Number:",
]


def load_card_mapping(secrets_path: Path = Path(".streamlit/secrets.toml")) -> Dict[str, str]:
    """Return a mapping of card serial numbers to rider IDs."""
    secrets = tomllib.loads(secrets_path.read_text())
    mapping: Dict[str, str] = {}
    rider_accounts = secrets.get("rider_accounts", {})
    for rider, cards in rider_accounts.items():
        for card in cards:
            mapping[str(card)] = rider.upper()
    return mapping


def detect_card_serial(pdf_path: Path) -> Optional[str]:
    """Extract the card serial number from a PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = result.stdout
    for line in text.splitlines():
        for pattern in CARD_PATTERNS:
            if pattern in line:
                serial = line.replace(pattern, "").strip()
                serial = serial.replace(":", "").strip()
                return serial or None
    return None


def extract_pdf_dataframe(pdf_path: Path) -> pd.DataFrame:
    """Extract and normalize transactions from a single PDF."""
    df = extract_trips_from_pdf(str(pdf_path))
    if df.empty:
        return df
    df = clean_up_extracted_data(df)
    df = categorize_trips(df)
    df.insert(0, "source_pdf", str(pdf_path))
    return df


def ingest_pdfs(
    pdf_paths: Iterable[Path],
    card_to_rider: Dict[str, str],
) -> pd.DataFrame:
    """Process multiple PDFs into a normalized DataFrame."""
    records: List[pd.DataFrame] = []

    for pdf_path in pdf_paths:
        serial = detect_card_serial(pdf_path)
        rider = card_to_rider.get(serial or "", "UNKNOWN")

        df = extract_pdf_dataframe(pdf_path)
        if df.empty:
            continue

        df = df.rename(
            columns={
                "Transaction Date": "Transaction Date",
                "Transaction Type": "Transaction Type",
                "Location": "Location",
                "Route": "Route",
                "Product": "Product",
                "Debit": "Debit",
                "Credit": "Credit",
                "Balance": "Balance",
                "Category": "Category",
            }
        )
        df["Card Serial"] = serial
        df["Rider"] = rider
        records.append(df)

    if not records:
        return pd.DataFrame(
            columns=[
                "Rider",
                "Card Serial",
                "Transaction Date",
                "Transaction Type",
                "Location",
                "Route",
                "Product",
                "Debit",
                "Credit",
                "Balance",
                "Category",
                "source_pdf",
            ]
        )

    combined = pd.concat(records, ignore_index=True)
    combined["Transaction Date"] = pd.to_datetime(combined["Transaction Date"], errors="coerce")
    return combined.sort_values("Transaction Date").reset_index(drop=True)
