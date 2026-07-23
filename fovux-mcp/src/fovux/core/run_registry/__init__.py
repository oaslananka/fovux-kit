"""Internal SQLite run-registry implementation boundaries."""

from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.facade import RunRegistry

__all__ = ["RegistryDatabase", "RunRegistry"]
