# SaveCloud Filesystem Layout

## Overview

SaveCloud separates synchronized data from device-specific data.

Only data required for cross-device synchronization is stored in the synchronized library.

Machine-specific information is stored locally and is never synchronized.

---

# Root Directory

Linux

~/.local/share/savecloud/

Future platforms may use their platform-specific application data directory.

---

# Directory Layout

~/.local/share/savecloud/

├── library/
├── registry/
├── device/
├── cache/
├── logs/
├── providers/

---

# library/

Purpose

Stores the canonical copy of every managed game's save data.

This directory is synchronized between devices.

Example

library/

pokemon-scarlet/

persona-5/

zelda-totk/

---

# library/<game-id>/

Each registered game owns its own library folder.

Example

pokemon-scarlet/

current/

versions/

metadata.json

---

# current/

Purpose

Contains the latest canonical save.

This folder is copied into the game's working save directory before launch.

Example

current/

save.dat

slot1.sav

config.bin

---

# versions/

Purpose

Stores historical save versions.

Versions are immutable.

Example

versions/

2026-07-09T18-23-51/

2026-07-08T14-02-17/

2026-07-07T09-51-12/

---

# metadata.json

Purpose

Stores metadata describing the current save.

Contains

- Current Version
- Last Device
- Last Sync
- Checksums
- Save Format Version

Example

metadata.json

---

# registry/

Purpose

Stores the global registry of every managed game.

Registry entries are synchronized between devices.

The registry never stores machine-specific paths.

Example

registry/

pokemon-scarlet.json

persona-5.json

---

# device/

Purpose

Stores machine-specific configuration.

Never synchronized.

Contains

- Save paths
- Steam shortcut IDs
- ROM paths
- Emulator locations
- Launch commands

Example

device/

desktop.json

steamdeck.json

---

# cache/

Purpose

Temporary runtime files.

Never synchronized.

May contain

- Download cache
- Temporary copies
- Hash cache

Can be safely deleted.

---

# logs/

Purpose

Stores runtime logs.

Never synchronized.

Example

launcher.log

sync.log

errors.log

---

# providers/

Purpose

Stores configuration for storage backends.

Never synchronized.

Examples

Syncthing API information

Google Drive credentials

Dropbox configuration

---

# Synchronization Rules

Synchronized

library/

registry/

Never Synchronized

device/

cache/

logs/

providers/

---

# Save Lifecycle

Game Save Folder

↓

Import into Library/current/

↓

Previous Library/current/

↓

Move into versions/

↓

Update metadata

↓

Synchronize library/

↓

Other Device

↓

Import into Working Save Folder

↓

Launch Game

---

# Design Rules

1. The library always contains the canonical save.

2. Games only access working copies.

3. Device-specific information is never synchronized.

4. Historical versions are immutable.

5. Storage providers never access game save folders directly.

6. SaveCloud is responsible for all imports and exports.

7. Every synchronized save must exist inside the library.
