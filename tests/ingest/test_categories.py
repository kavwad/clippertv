"""Tests for operator-based transit categorization."""

import pandas as pd
import pytest

from clippertv.ingest.categories import categorize


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to create a DataFrame from row dicts with defaults."""
    defaults = {"operator": "", "start_location": None}
    return pd.DataFrame([{**defaults, **r} for r in rows])


class TestDirectOperatorMapping:
    """Operators that map directly to categories with no sub-classification."""

    def test_bart(self):
        df = _make_df([{"operator": "BART"}])
        assert categorize(df)["category"].iloc[0] == "BART"

    def test_caltrain(self):
        df = _make_df([{"operator": "Caltrain"}])
        assert categorize(df)["category"].iloc[0] == "Caltrain"

    def test_ac_transit(self):
        df = _make_df([{"operator": "AC Transit"}])
        assert categorize(df)["category"].iloc[0] == "AC Transit"

    def test_samtrans(self):
        df = _make_df([{"operator": "SamTrans"}])
        assert categorize(df)["category"].iloc[0] == "SamTrans"

    def test_golden_gate_transit(self):
        df = _make_df([{"operator": "Golden Gate Transit"}])
        assert categorize(df)["category"].iloc[0] == "Golden Gate Transit"

    def test_unknown_operator_passes_through(self):
        df = _make_df([{"operator": "VTA"}])
        assert categorize(df)["category"].iloc[0] == "VTA"


class TestMuniSubCategorization:
    """Muni trips are sub-categorized by start_location."""

    def test_metro_station_west_portal(self):
        df = _make_df([{"operator": "Muni", "start_location": "West Portal"}])
        assert categorize(df)["category"].iloc[0] == "Muni Metro"

    def test_metro_station_embarcadero(self):
        df = _make_df([{"operator": "Muni", "start_location": "Embarcadero"}])
        assert categorize(df)["category"].iloc[0] == "Muni Metro"

    def test_metro_station_castro(self):
        df = _make_df([{"operator": "Muni", "start_location": "Castro"}])
        assert categorize(df)["category"].iloc[0] == "Muni Metro"

    def test_bus_stop_intersection(self):
        df = _make_df([{"operator": "Muni", "start_location": "Haight/Noriega"}])
        assert categorize(df)["category"].iloc[0] == "Muni Bus"

    def test_cable_car_stop(self):
        df = _make_df([{"operator": "Muni", "start_location": "Hyde/Beach"}])
        assert categorize(df)["category"].iloc[0] == "Cable Car"

    def test_none_location_defaults_to_bus(self):
        df = _make_df([{"operator": "Muni", "start_location": None}])
        assert categorize(df)["category"].iloc[0] == "Muni Bus"

    def test_location_none_string_defaults_to_bus(self):
        df = _make_df([{"operator": "Muni", "start_location": "NONE"}])
        assert categorize(df)["category"].iloc[0] == "Muni Bus"


class TestFerryDetection:
    """Ferry operator maps to Ferry category."""

    def test_ferry_operator(self):
        df = _make_df([{"operator": "WETA"}])
        assert categorize(df)["category"].iloc[0] == "Ferry"

    def test_golden_gate_ferry(self):
        df = _make_df([{"operator": "Golden Gate Ferry"}])
        assert categorize(df)["category"].iloc[0] == "Ferry"


class TestMultipleRows:
    """Categorization works across a full DataFrame."""

    def test_mixed_operators(self):
        df = _make_df([
            {"operator": "BART"},
            {"operator": "Muni", "start_location": "Haight/Noriega"},
            {"operator": "Caltrain"},
            {"operator": "Muni", "start_location": "Powell"},
        ])
        result = categorize(df)
        assert list(result["category"]) == ["BART", "Muni Bus", "Caltrain", "Muni Metro"]
