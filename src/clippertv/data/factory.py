"""Factory for creating appropriate data store instances."""

from functools import lru_cache
from typing import Dict, Any

from clippertv.config import config
from clippertv.data.gcs_store import DataStore as GCSDataStore
from clippertv.data.turso_store import TursoStore


@lru_cache(maxsize=1)
def _get_turso_store() -> TursoStore:
    """Return a cached TursoStore instance."""
    return TursoStore()


def get_data_store(gcs_key: Dict[str, Any] = None):
    """Get the appropriate data store based on configuration.

    Args:
        gcs_key: Optional Google Cloud Storage key (for GCS store only)

    Returns:
        The appropriate data store instance
    """
    if config.storage.use_turso:
        # Return cached Turso implementation to avoid repeated init
        return _get_turso_store()
    else:
        # Return GCS implementation
        return GCSDataStore(gcs_key)
