"""Operator-based transit categorization for Clipper CSV data."""

import pandas as pd

MUNI_METRO_STATIONS = frozenset({
    "Embarcadero", "Montgomery", "Powell", "Civic Center",
    "Van Ness", "Church", "Castro", "Forest Hill",
    "West Portal", "Balboa Park",
    "Sunset Tunnel East", "Sunset Tunnel West",
    "Duboce/Church", "Duboce/Noe",
    "Carl/Cole", "Carl/Hillway",
    "Judah/9th Ave", "Judah/19th Ave",
    "Taraval/19th Ave", "Taraval/32nd Ave",
    "SF State", "Stonestown", "Parkmerced",
    "Ocean/San Jose", "Ocean/Geneva",
    "4th/King", "4th/Brannan",
    "Sunnydale", "Bayshore/Arleta",
    "3rd/20th", "3rd/Carroll",
})

CABLE_CAR_STOPS = frozenset({
    "Hyde/Beach", "Hyde/Lombard", "Hyde/Greenwich",
    "Hyde/Union", "Hyde/Jackson", "Hyde/California",
    "Powell/Market", "Powell/Mason", "Powell/Hyde",
    "Mason/Washington", "Mason/Jackson",
    "California/Van Ness", "California/Powell",
    "California/Drumm",
})

FERRY_OPERATORS = frozenset({"WETA", "Golden Gate Ferry"})


def categorize(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'category' column based on operator and start_location."""
    df = df.copy()
    df["category"] = df.apply(_categorize_row, axis=1)
    return df


def _categorize_row(row: pd.Series) -> str:
    """Categorize a single transaction row."""
    operator = row.get("operator", "")
    if operator == "Muni":
        return _categorize_muni(row.get("start_location"))
    if operator in FERRY_OPERATORS:
        return "Ferry"
    return operator


def _categorize_muni(start_location: str | None) -> str:
    """Sub-categorize a Muni trip by start location."""
    if not start_location or start_location == "NONE":
        return "Muni Bus"
    if start_location in MUNI_METRO_STATIONS:
        return "Muni Metro"
    if start_location in CABLE_CAR_STOPS:
        return "Cable Car"
    return "Muni Bus"
