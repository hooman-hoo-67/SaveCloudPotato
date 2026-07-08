# SaveCloud Filesystem Layout

## Overview

SaveCloud separates synchronized data from device-specific data.

Only data required for cross-device synchronization is synchronized.

Machine-specific information is always stored locally.

---

# Root Directory

Linux

```
~/.local/share/savecloud/
```

Future platforms will use their platform-specific application data directory.

---

# Directory Layout

```
savecloud/

library/
registry/
device/
cache/
logs/
providers/
```

---

# library/

## Purpose

Stores the canonical copy of every managed game's save data.

The Library is synchronized between devices.

Example

```
library/

pokemon-scarlet/

current/

versions/

metadata.json
```

---

# current/

Contains the latest playable save.

Before launching a game, SaveCloud copies the contents of `current/`
into the game's working save folder.

---

# versions/

Stores immutable historical save versions.

Example

```
versions/

2026-07-09T18-23-51/

2026-07-08T14-02-17/

2026-07-07T09-51-12/
```

Versions are never modified after creation.

---

# metadata.json

Contains metadata about the canonical save.

Example Fields

- Current Version
- Last Device
- Last Sync
- Checksums
- Save Format Version

---

# registry/

## Purpose

Stores synchronized information about every managed game.

Each game owns its own registry directory.

Example

```
registry/

pokemon-scarlet/

manifest.json

runtime.json
```

---

# manifest.json

Contains configuration.

Rarely changes.

Example Fields

- Game ID
- Display Name
- Launch Type
- Platform
- Adapter
- Storage Backend
- Backup Enabled
- Sync Enabled

---

# runtime.json

Contains runtime state.

Frequently updated.

Example Fields

- Current Version
- Last Device
- Last Sync
- Sync Status
- Pending Upload
- Last Error

---

# device/

## Purpose

Stores device-specific configuration.

Never synchronized.

Structure

```
device/

desktop/

pokemon-scarlet.json

steamdeck/

pokemon-scarlet.json
```

Example Fields

- Save Path
- Steam Shortcut ID
- ROM Path
- Emulator Path
- Launch Command

---

# cache/

Temporary runtime data.

Never synchronized.

Safe to delete.

---

# logs/

Stores application logs.

Never synchronized.

Examples

- launcher.log
- sync.log
- errors.log

---

# providers/

Stores provider-specific configuration.

Never synchronized.

Examples

- Syncthing
- Google Drive
- Dropbox

---

# Synchronization Rules

## Synchronized

- library/
- registry/

## Never Synchronized

- device/
- cache/
- logs/
- providers/

---

# Save Lifecycle

```
Game Save Folder

↓

Import into Library/current/

↓

Previous Library/current/

↓

Move into Library/versions/

↓

Update metadata

↓

Update runtime.json

↓

Synchronize Library

↓

Other Device

↓

Import into Working Save Folder

↓

Launch Game
```

---

# Design Rules

1. The Library always contains the canonical save.

2. Games only interact with working copies.

3. Device-specific information is never synchronized.

4. Configuration and runtime state are stored separately.

5. Historical versions are immutable.

6. Storage providers never access game save folders directly.

7. Every synchronized save must exist inside the Library before it can be uploaded.
