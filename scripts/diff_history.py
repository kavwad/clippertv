"""Diff transactions between a history PDF-derived CSV and the Turso DB.

Usage:
    uv run python scripts/diff_history.py --rider K --csv tmp/history_k.csv \
        --start 2025-01-01 --end 2025-12-31 [--ignore-manual]
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any, Optional

import pandas as pd

from clippertv.data.turso_store import TursoStore

FMT = "%b %d, %Y %I:%M:%S %p"

HEADERS = [
    "Transaction Date",
    "Transaction Type",
    "Category",
    "Location",
    "Route",
    "Debit",
    "Credit",
    "Balance",
    "Product",
]

TRANSIT_MAP = {
    "BART": "BART",
    "Caltrain": "Caltrain",
    "SF Muni": "Muni Bus",
}


def parse_money(val: str | float | None) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).replace("$", "").replace(",", "")
    s = s.replace("(", "-").replace(")", "")
    try:
        return float(s)
    except Exception:
        return None


def normalize_product(product: str | None) -> Optional[str]:
    if not product:
        return None
    if product.strip() == "Translink E-Cash":
        return "Clipper Cash"
    return product.strip()


def normalize_route(route: str | None) -> Optional[str]:
    if not route or route in {"NONE", "N"}:
        return None
    return route


def classify_muni(location: Optional[str], route: Optional[str]) -> str:
    if location and "bus" in location.lower():
        return "Muni Bus"
    if route and route not in {None, "", "NONE"}:
        return "Muni Bus"
    if route == "MTANONE":
        return "Muni Bus"
    return "Muni Metro"


def map_category_and_type(txn_type: str, participant: str) -> Tuple[str, str]:
    transit = TRANSIT_MAP.get(participant, participant)
    if txn_type == "Entry Tag":
        return f"{transit} Entrance", "entry"
    if txn_type == "Exit Tag":
        return f"{transit} Exit", "exit"
    if txn_type == "Single Journey":
        if participant == "SF Muni":
            return None, "entry"  # decide later based on location/route
        return transit or "Unknown", "entry"
    if txn_type == "Sales Transaction":
        # DB represents loads as entry/Unknown
        return "Unknown", "entry"
    return transit or "Unknown", "entry"


def load_pdf_csv(stem: Path) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    with stem.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = datetime.strptime(row["txn_datetime"], FMT)
            dt = dt.replace(second=0)  # DB stores minute-level precision
            category, ttype = map_category_and_type(
                row["txn_type"], row["participant"]
            )
            debit = None
            credit = None
            if row["txn_type"] == "Sales Transaction":
                credit = parse_money(row["txn_value"])
            else:
                debit = parse_money(row["txn_value"])
            location = row["location"] or None
            route = normalize_route(row["route"])
            if category is None:
                category = classify_muni(location, route)
            rows.append(
                {
                    "Transaction Date": dt,
                    "Transaction Type": ttype,
                    "Category": category,
                    "Location": location,
                    "Route": route,
                    "Debit": debit,
                    "Credit": credit,
                    "Balance": parse_money(row["remaining_value"]),
                    "Product": normalize_product(row["product"]),
                }
            )
    return pd.DataFrame(rows, columns=HEADERS)


def filter_range(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    return df[
        (df["Transaction Date"] >= start)
        & (df["Transaction Date"] <= end)
    ].copy()


def normalize_key(row: pd.Series) -> Tuple[Any, ...]:
    def norm(val: Any) -> Any:
        return None if pd.isna(val) else val

    return (
        row["Transaction Date"],
        row["Transaction Type"],
        row["Category"],
        norm(row.get("Location")),
        norm(row.get("Route")),
        norm(row.get("Debit")),
        norm(row.get("Credit")),
        norm(row.get("Product")),
    )


def diff_sets(
    pdf_df: pd.DataFrame, db_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pdf_df = pdf_df.copy()
    db_df = db_df.copy()

    pdf_df["key"] = pdf_df.apply(normalize_key, axis=1)
    db_df["key"] = db_df.apply(normalize_key, axis=1)

    pdf_keys = set(pdf_df["key"])
    db_keys = set(db_df["key"])

    only_pdf = pdf_df[pdf_df["key"].isin(pdf_keys - db_keys)]
    only_db = db_df[db_df["key"].isin(db_keys - pdf_keys)]

    # For common keys, check balance mismatches
    common_keys = pdf_keys & db_keys
    pdf_common = (
        pdf_df[pdf_df["key"].isin(common_keys)]
        .drop_duplicates(subset=["key"])
        .set_index("key")
    )
    db_common = (
        db_df[db_df["key"].isin(common_keys)]
        .drop_duplicates(subset=["key"])
        .set_index("key")
    )

    pdf_bal = pdf_common["Balance"].to_dict()
    db_bal = db_common["Balance"].to_dict()

    mismatches = []
    for key in common_keys:
        pb = pdf_bal.get(key)
        dbb = db_bal.get(key)
        if pd.isna(pb) and pd.isna(dbb):
            continue
        if pb != dbb:
            row = pdf_common.loc[key].copy()
            row["DB Balance"] = dbb
            mismatches.append(row)
    mismatches_df = (
        pd.DataFrame(mismatches).reset_index(drop=True) if mismatches else pd.DataFrame()
    )

    return only_pdf, only_db, mismatches_df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rider", required=True, help="Rider ID (e.g., K or B)")
    parser.add_argument("--csv", required=True, type=Path, help="CSV from convert_history_pdf")
    parser.add_argument("--start", required=True, type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--ignore-manual",
        action="store_true",
        help="Ignore manual rows from DB in comparison",
    )
    args = parser.parse_args()

    start_dt = pd.to_datetime(args.start)
    end_dt = pd.to_datetime(args.end)

    pdf_df = load_pdf_csv(args.csv)
    pdf_df = filter_range(pdf_df, start_dt, end_dt)

    store = TursoStore()
    db_df = store.load_data(args.rider)
    db_df = db_df[HEADERS].copy()
    db_df["Transaction Date"] = pd.to_datetime(db_df["Transaction Date"]).dt.floor("min")
    db_df = filter_range(db_df, start_dt, end_dt)

    if args.ignore_manual:
        db_df = db_df[db_df["Transaction Type"] != "manual"].copy()

    only_pdf, only_db, mismatches = diff_sets(pdf_df, db_df)

    print(f"PDF rows in range: {len(pdf_df)}")
    print(f"DB rows in range: {len(db_df)} (ignore_manual={args.ignore_manual})")
    print(f"Only in PDF: {len(only_pdf)}")
    print(f"Only in DB: {len(only_db)}")
    print(f"Balance mismatches on common keys: {len(mismatches)}")

    out_dir = Path("tmp/diff")
    out_dir.mkdir(parents=True, exist_ok=True)
    only_pdf_path = out_dir / f"{args.rider}_only_pdf.csv"
    only_db_path = out_dir / f"{args.rider}_only_db.csv"
    mismatch_path = out_dir / f"{args.rider}_balance_mismatches.csv"

    only_pdf.to_csv(only_pdf_path, index=False)
    only_db.to_csv(only_db_path, index=False)
    mismatches.to_csv(mismatch_path, index=False)

    print(f"Wrote: {only_pdf_path}")
    print(f"Wrote: {only_db_path}")
    print(f"Wrote: {mismatch_path}")


if __name__ == "__main__":
    main()
