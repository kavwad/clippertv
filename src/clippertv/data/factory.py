"""Factory for creating data store instances."""

from functools import lru_cache

from clippertv.data.turso_store import TursoStore


@lru_cache(maxsize=1)
def get_data_store() -> TursoStore:
    """Return a cached TursoStore instance."""
    return TursoStore()
