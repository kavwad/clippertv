"""Convert Clipper transaction history PDFs into structured CSV.

These PDFs split rows across lines and pages, so we stream through all pages,
stitch multi-line cells, and handle page-break splits.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable, Sequence

import camelot

HEADERS: list[str] = [
    "txn_datetime",
    "txn_type",
    "participant",
    "product",
    "location",
    "route",
    "txn_value",
    "remaining_value",
]


def is_header_row(row: Sequence[str]) -> bool:
    joined = " ".join(row).lower()
    if "txn date time" in joined and "txn type" in joined:
        return True
    if "txn value" in joined and "remaining value" in joined:
        return True
    tokens = {
        "txn",
        "date",
        "time",
        "type",
        "participant",
        "product",
        "location",
        "route",
        "value",
        "remaining",
    }
    cells = [cell.lower() for cell in row if cell.strip()]
    return cells and all(cell in tokens for cell in cells)


def is_record_start(cell: str) -> bool:
    return bool(re.match(r"^[A-Za-z]{3} \d{2}, \d{4}", cell.strip()))


def has_data(record: list[list[str]]) -> bool:
    return any(segment for col in record for segment in col)


def clean_cell(text: str, idx: int) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if idx == 0:
        text = re.sub(r":\s+(?=\d)", ":", text)
    if idx == 3:
        text = re.sub(r"E-\s+Cash", "E-Cash", text)
    return text


def parse_pdf(path: Path) -> list[list[str]]:
    tables = camelot.read_pdf(str(path), pages="all", flavor="stream")
    current: list[list[str]] = [[] for _ in HEADERS]
    records: list[list[list[str]]] = []

    for table in tables:
        for row in table.df.values.tolist():
            cells = [cell.strip() for cell in row]
            if not "".join(cells):
                continue
            if is_header_row(cells):
                continue

            if is_record_start(cells[0]):
                if has_data(current):
                    records.append([col[:] for col in current])
                current = [[] for _ in HEADERS]

            for idx, cell in enumerate(cells):
                if cell:
                    current[idx].append(cell)

    if has_data(current):
        records.append([col[:] for col in current])

    cleaned: list[list[str]] = []
    for record in records:
        cleaned_row: list[str] = []
        for idx, col in enumerate(record):
            text = " ".join(col)
            cleaned_row.append(clean_cell(text, idx))
        if cleaned_row[6].count("$") > 1 or cleaned_row[7].count("$") > 1:
            continue
        cleaned.append(cleaned_row)

    return cleaned


def write_csv(records: Iterable[Sequence[str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for row in records:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to Clipper history PDF")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: tmp/<pdf_stem>.csv)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf
    out_path = args.out or Path("tmp") / f"{pdf_path.stem}.csv"

    records = parse_pdf(pdf_path)
    write_csv(records, out_path)

    print(f"Wrote {len(records)} records to {out_path}")


if __name__ == "__main__":
    main()
