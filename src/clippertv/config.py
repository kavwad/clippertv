"""Configuration management for ClipperTV."""

from typing import Dict, List

from pydantic import BaseModel, Field


class TransitCategories(BaseModel):
    """Transit category mappings and configurations."""

    display_categories: List[str] = [
        'Muni Bus', 'Muni Metro', 'BART', 'Cable Car',
        'Caltrain', 'Ferry', 'AC Transit', 'SamTrans'
    ]

    submit_categories: Dict[str, str] = {
        'Muni Bus': 'Muni Bus',
        'Muni Metro': 'Muni Metro',
        'BART': 'BART Entrance',
        'Cable Car': 'Cable Car',
        'Caltrain': 'Caltrain Entrance',
        'Ferry': 'Ferry Entrance',
        'AC Transit': 'AC Transit',
        'SamTrans': 'SamTrans'
    }

    trip_table_categories: List[str] = [
        'Muni Bus', 'Muni Metro', 'BART Entrance', 'Cable Car',
        'Caltrain Entrance', 'Ferry Entrance', 'AC Transit', 'SamTrans'
    ]

    cost_table_categories: List[str] = [
        'Muni Bus', 'Muni Metro', 'BART Exit', 'Cable Car',
        'Caltrain', 'Ferry', 'AC Transit', 'SamTrans'
    ]

    color_map: Dict[str, str] = {
        'Muni Bus': '#BA0C2F',
        'Muni Metro': '#FDB813',
        'BART': '#0099CC',
        'Cable Car': '#8B4513',
        'Caltrain': '#6C6C6C',
        'AC Transit': '#00A55E',
        'Ferry': '#4DD0E1',
        'SamTrans': '#D3D3D3'
    }


class AppConfig(BaseModel):
    """Main application configuration."""

    app_title: str = "ClipperTV"
    riders: List[str] = ["B", "K"]
    pdf_table_areas_first_page: List[str] = ["0,500,800,100"]
    pdf_table_areas_other_pages: List[str] = ["0,550,800,90"]
    pdf_local_cache_dir: str = Field(
        default="tmp/pdf-cache",
        description="Local directory for storing downloaded or uploaded PDF statements"
    )
    transit_categories: TransitCategories = TransitCategories()
    column_config: Dict = Field(default_factory=dict)

    def __init__(self, **data):
        """Initialize the configuration instance."""
        super().__init__(**data)
        self._setup_column_config()

    def _setup_column_config(self) -> None:
        """Initialize column configuration for Streamlit data displays."""
        import streamlit as st

        self.column_config = {
            'Year': st.column_config.NumberColumn(format="%d", width=75),
            'Month': st.column_config.DateColumn(format="MMM YYYY", width=75),
        }

        for category in self.transit_categories.display_categories:
            self.column_config[category] = st.column_config.NumberColumn(format="$%d")


config = AppConfig()
