"""
Global filesystem constants for SaveCloud.

This module is the single source of truth for all filesystem paths.
"""

from pathlib import Path
from platformdirs import user_data_dir

APP_NAME = "savecloud"

# Root SaveCloud directory
SAVECLOUD_HOME = Path(user_data_dir(APP_NAME))

# Core directories
LIBRARY_DIR = SAVECLOUD_HOME / "library"
REGISTRY_DIR = SAVECLOUD_HOME / "registry"
DEVICE_DIR = SAVECLOUD_HOME / "device"
CACHE_DIR = SAVECLOUD_HOME / "cache"
LOG_DIR = SAVECLOUD_HOME / "logs"
PROVIDER_DIR = SAVECLOUD_HOME / "providers"

# Every directory SaveCloud manages
DIRECTORIES = (
    LIBRARY_DIR,
    REGISTRY_DIR,
    DEVICE_DIR,
    CACHE_DIR,
    LOG_DIR,
    PROVIDER_DIR,
)
