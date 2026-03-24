"""Tests for Clipper CSV parsing."""

import pandas as pd
import pytest

from clippertv.ingest.clipper import parse_csv

SAMPLE_CSV = '''"ACCOUNT NUMBER","END DATE/TIME","END LOCATION","FARE","OPERATOR","PASS","START DATE/TIME","START LOCATION","TRIP ID"
"100005510894","N/A","N/A","$2.85","Muni","Cash Value ","02/28/2026 23:45:19","Haight/Noriega","11052564"
"100005510894","02/28/2026 22:00:43","16th Street / Mission","$5.35","BART","Cash Value ","02/28/2026 21:16:16","Fruitvale","11047705"
"100005510894","N/A","N/A","$0.00","Muni","N/A","02/22/2026 18:41:36","NONE","10003757"
'''


class TestParseCSV:
    """Test CSV content parsing into normalized DataFrame."""

    def test_column_names(self):
        df = parse_csv(SAMPLE_CSV)
        expected = {
            "account_number", "transaction_date", "end_datetime",
            "start_location", "end_location", "fare", "operator",
            "pass_type", "trip_id",
        }
        assert set(df.columns) == expected

    def test_row_count(self):
        df = parse_csv(SAMPLE_CSV)
        assert len(df) == 3

    def test_fare_parsed_as_float(self):
        df = parse_csv(SAMPLE_CSV)
        assert df.iloc[0]["fare"] == 2.85
        assert df.iloc[1]["fare"] == 5.35

    def test_zero_fare(self):
        df = parse_csv(SAMPLE_CSV)
        assert df.iloc[2]["fare"] == 0.0

    def test_na_end_datetime_is_none(self):
        df = parse_csv(SAMPLE_CSV)
        assert pd.isna(df.iloc[0]["end_datetime"])

    def test_valid_end_datetime_parsed(self):
        df = parse_csv(SAMPLE_CSV)
        assert pd.notna(df.iloc[1]["end_datetime"])

    def test_na_end_location_is_none(self):
        df = parse_csv(SAMPLE_CSV)
        assert pd.isna(df.iloc[0]["end_location"])

    def test_valid_end_location(self):
        df = parse_csv(SAMPLE_CSV)
        assert df.iloc[1]["end_location"] == "16th Street / Mission"

    def test_none_start_location_is_null(self):
        df = parse_csv(SAMPLE_CSV)
        assert pd.isna(df.iloc[2]["start_location"])

    def test_pass_type_stripped(self):
        df = parse_csv(SAMPLE_CSV)
        assert df.iloc[0]["pass_type"] == "Cash Value"

    def test_na_pass_type(self):
        df = parse_csv(SAMPLE_CSV)
        assert pd.isna(df.iloc[2]["pass_type"])

    def test_trip_id_is_string(self):
        df = parse_csv(SAMPLE_CSV)
        assert df.iloc[0]["trip_id"] == "11052564"

    def test_transaction_date_is_datetime(self):
        df = parse_csv(SAMPLE_CSV)
        assert isinstance(df.iloc[0]["transaction_date"], pd.Timestamp)

    def test_account_number_preserved(self):
        df = parse_csv(SAMPLE_CSV)
        assert df.iloc[0]["account_number"] == "100005510894"

    def test_empty_csv_returns_empty_df(self):
        df = parse_csv("")
        assert len(df) == 0
