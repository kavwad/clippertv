"""Factory for creating appropriate data store instances."""

from typing import Dict, Any

from clippertv.config import config
from clippertv.data.store import DataStore as GCSDataStore
from clippertv.data.supabase_store import SupabaseStore


def get_data_store(gcs_key: Dict[str, Any] = None):
    """Get the appropriate data store based on configuration.
    
    Args:
        gcs_key: Optional Google Cloud Storage key (for GCS store only)
        
    Returns:
        The appropriate data store instance
    """
    if config.storage.use_supabase:
        # Return Supabase implementation
        return SupabaseStore()
    else:
        # Return GCS implementation
        return GCSDataStore(gcs_key)