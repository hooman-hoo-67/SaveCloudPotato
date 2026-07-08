from pathlib import Path
from platformdirs import user_data_dir

APP_NAME = "savecloud"

# Current filesystem schema
SCHEMA_VERSION = 1

# Root directory
SAVECLOUD_HOME = Path(user_data_dir(APP_NAME))

# Installation metadata
INSTALL_METADATA = SAVECLOUD_HOME / "savecloud.json"

# Core directories
LIBRARY_DIR = SAVECLOUD_HOME / "library"
REGISTRY_DIR = SAVECLOUD_HOME / "registry"
DEVICE_DIR = SAVECLOUD_HOME / "device"
CACHE_DIR = SAVECLOUD_HOME / "cache"
LOG_DIR = SAVECLOUD_HOME / "logs"
PROVIDER_DIR = SAVECLOUD_HOME / "providers"

DIRECTORIES = (
    LIBRARY_DIR,
    REGISTRY_DIR,
    DEVICE_DIR,
    CACHE_DIR,
    LOG_DIR,
    PROVIDER_DIR,
)
