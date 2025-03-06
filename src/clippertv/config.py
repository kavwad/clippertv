"""Configuration management for ClipperTV."""

import os
from typing import Dict, List, Literal
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

class StorageConfig(BaseModel):
    """Configuration for data storage."""
    
    # Storage type
    storage_type: Literal["gcs", "supabase"] = Field(
        default="gcs",
        description="Storage backend to use"
    )
    
    # Google Cloud Storage
    gcs_bucket: str = "clippertv_data"
    gcs_file_template: str = "data_{}.csv"  # Format with rider name
    
    @property
    def use_supabase(self) -> bool:
        """Check if Supabase storage should be used."""
        # Check environment variable first
        env_storage = os.environ.get("CLIPPERTV_STORAGE", "").lower()
        if env_storage == "supabase":
            return True
        if env_storage == "gcs":
            return False
        
        # Fall back to configured value
        return self.storage_type == "supabase"

class AppConfig(BaseModel):
    """Main application configuration."""
    
    # App metadata
    app_title: str = "ClipperTV"
    
    # Data storage
    storage: StorageConfig = StorageConfig()
    
    # Legacy storage config (for backward compatibility)
    data_bucket: str = Field(default="clippertv_data", 
                           description="Legacy field, use storage.gcs_bucket instead")
    data_file_template: str = Field(default="data_{}.csv", 
                                  description="Legacy field, use storage.gcs_file_template instead")
    
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
        self._sync_legacy_fields()
    
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
    
    def _sync_legacy_fields(self):
        """Synchronize legacy fields with new structure for backward compatibility."""
        # Sync from legacy to new structure
        if self.data_bucket != self.storage.gcs_bucket:
            self.storage.gcs_bucket = self.data_bucket
            
        if self.data_file_template != self.storage.gcs_file_template:
            self.storage.gcs_file_template = self.data_file_template


# Create global config instance
config = AppConfig()