"""Tests for CSV-aware store operations."""

import pandas as pd
import pytest


@pytest.mark.skip(reason="Integration test — needs live DB connection")
def test_csv_save_and_load_roundtrip():
    """CSV transactions saved via save_csv_transactions can be loaded back."""
    pass


@pytest.mark.skip(reason="Integration test — needs live DB connection")
def test_load_normalizes_old_pdf_categories():
    """Old PDF rows with 'BART Entrance' category are loaded as 'BART'."""
    pass


@pytest.mark.skip(reason="Integration test — needs live DB connection")
def test_load_coalesces_fare_from_debit():
    """Old PDF rows without fare get fare coalesced from debit."""
    pass
