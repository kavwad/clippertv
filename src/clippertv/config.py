"""Configuration management for ClipperTV."""

from typing import Dict, List
from pydantic import BaseModel, Field

class TransitCategories(BaseModel):
    """Transit category mappings and configurations."""
    
    # Display categories (for UI)
    display_categories: List[str] = [
        'Muni Bus', 'Muni Metro', 'BART', 'Cable Car',
        'Caltrain', 'Ferry', 'AC Transit', 'SamTrans'
    ]
    
    # Categories used for data submission
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
    
    # Categories for trip tables
    trip_table_categories: List[str] = [
        'Muni Bus', 'Muni Metro', 'BART Entrance', 'Cable Car',
        'Caltrain Entrance', 'Ferry Entrance', 'AC Transit', 'SamTrans'
    ]
    
    # Categories for cost tables
    cost_table_categories: List[str] = [
        'Muni Bus', 'Muni Metro', 'BART Exit', 'Cable Car',
        'Caltrain', 'Ferry', 'AC Transit', 'SamTrans'
    ]
    
    # Color mapping for visualization
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
    
    # App metadata
    app_title: str = "ClipperTV"
    
    # Data storage
    data_bucket: str = "clippertv_data"
    data_file_template: str = "data_{}.csv"  # Format with rider name
    
    # Available riders
    riders: List[str] = ["B", "K"]
    
    # PDF processing
    pdf_table_areas_first_page: List[str] = ["0,500,800,100"]
    pdf_table_areas_other_pages: List[str] = ["0,550,800,90"]
    
    # Transit categories configuration
    transit_categories: TransitCategories = TransitCategories()
    
    # Column configuration for streamlit dataframes
    column_config: Dict = Field(default_factory=dict)
    
    def __init__(self, **data):
        super().__init__(**data)
        self._setup_column_config()
    
    def _setup_column_config(self):
        """Initialize column configuration for Streamlit data displays."""
        import streamlit as st
        
        self.column_config = {
            'Year': st.column_config.NumberColumn(format="%d", width=75),
            'Month': st.column_config.DateColumn(format="MMM YYYY", width=75),
        }
        
        # Add column configs for each transit category
        for category in self.transit_categories.display_categories:
            self.column_config[category] = st.column_config.NumberColumn(format="$%d")


# Create global config instance
config = AppConfig()